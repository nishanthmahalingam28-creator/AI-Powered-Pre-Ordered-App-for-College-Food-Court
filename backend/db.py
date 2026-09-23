import os
import re
import sqlite3
import logging
import urllib.parse
import queue
import threading
from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("food_court.db")

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "food_court_local.db")

# Reuse a small number of MySQL connections instead of creating a new TCP/TLS
# connection for every query. This is especially important when Render and
# Aiven are in different network locations.
MYSQL_POOL_SIZE = max(1, min(int(os.getenv("DB_POOL_SIZE", "8")), 10))
_mysql_pool = None
_mysql_pool_lock = threading.Lock()


class DatabaseConnectionError(Exception):
    """Raised when a database connection cannot be established or is unavailable."""
    pass


class DatabaseError(Exception):
    """Raised when an error occurs during database query execution."""
    pass


def is_production():
    """Returns True if the application is running in production mode."""
    flask_env = os.getenv("FLASK_ENV", "production").lower()
    return flask_env not in ("development", "dev", "test", "testing")


def _safe_int(val, default):
    try:
        return int(val) if val is not None and str(val).strip() else default
    except (ValueError, TypeError):
        return default


def get_mysql_config():
    """
    Extracts MySQL connection parameters from DATABASE_URL or individual DB_* variables.
    Never exposes passwords in logs.
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url and db_url.startswith(("mysql://", "mysql+pymysql://")):
        parsed = urllib.parse.urlparse(db_url)
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": parsed.username or "root",
            "password": parsed.password or "",
            "database": parsed.path.lstrip("/") if parsed.path else "food_court_db",
            "connect_timeout": _safe_int(os.getenv("DB_TIMEOUT"), 5),
        }

    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": _safe_int(os.getenv("DB_PORT"), 3306),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "food_court_db"),
        "connect_timeout": _safe_int(os.getenv("DB_TIMEOUT"), 5),
    }


def get_mysql_connection():
    """Creates a new MySQL connection. Prefer pooled_mysql_connection() for queries."""
    config = get_mysql_config()
    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        cursorclass=DictCursor,
        autocommit=True,
        charset="utf8mb4",
        connect_timeout=config["connect_timeout"],
    )


def _get_mysql_pool():
    global _mysql_pool
    if _mysql_pool is None:
        with _mysql_pool_lock:
            if _mysql_pool is None:
                _mysql_pool = queue.LifoQueue(maxsize=MYSQL_POOL_SIZE)
    return _mysql_pool


def get_pooled_mysql_connection():
    """Gets a reusable MySQL connection without an extra ping round-trip."""
    pool = _get_mysql_pool()
    try:
        return pool.get_nowait()
    except queue.Empty:
        return get_mysql_connection()


def release_mysql_connection(conn, reset_transaction=False):
    """Returns a MySQL connection to the pool."""
    if conn is None:
        return
    try:
        # Individual DB.query/execute calls already run with autocommit=True.
        # Only transaction contexts need the autocommit reset before reuse.
        if reset_transaction:
            conn.rollback()
            conn.autocommit(True)
        _get_mysql_pool().put_nowait(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def get_sqlite_connection():
    """Creates a connection to the local development SQLite database."""
    if is_production():
        raise DatabaseConnectionError("FATAL: SQLite connection attempted in production mode.")
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db_connection():
    """
    Retrieves an active database connection adhering to environment safety rules:

    PRODUCTION:
    - MySQL must be explicitly configured and operational.
    - If MySQL connection fails, logs safe diagnostic information and raises DatabaseConnectionError.
    - NEVER silently switches or falls back to SQLite.

    DEVELOPMENT:
    - If USE_SQLITE is set, uses local SQLite database.
    - Otherwise attempts MySQL. If MySQL is unavailable, logs a clear warning and falls back to SQLite.
    """
    if is_production():
        config = get_mysql_config()
        if not config["host"] or not config["database"]:
            logger.critical("PRODUCTION DATABASE FAILURE: Missing required DB_HOST or DB_NAME.")
            raise DatabaseConnectionError("Production database service unavailable: Missing database configuration.")
        try:
            return ("mysql", get_pooled_mysql_connection())
        except Exception as e:
            logger.critical(
                "PRODUCTION DATABASE FAILURE: Unable to connect to MySQL at %s:%s/%s "
                "(Error: %s: %s). SQLite fallback is strictly prohibited in production.",
                config["host"],
                config["port"],
                config["database"],
                type(e).__name__,
                str(e),
            )
            raise DatabaseConnectionError(
                "Production database service unavailable. Please verify MySQL configuration."
            ) from None

    # DEVELOPMENT MODE
    if os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes"):
        return ("sqlite", get_sqlite_connection())

    try:
        return ("mysql", get_mysql_connection())
    except Exception as e:
        config = get_mysql_config()
        logger.warning(
            "DEVELOPMENT NOTICE: MySQL connection at %s:%s/%s failed (%s). "
            "Using development SQLite database (%s). "
            "Note: SQLite fallback is strictly prohibited in production.",
            config["host"], config["port"], config["database"], type(e).__name__, SQLITE_PATH
        )
        return ("sqlite", get_sqlite_connection())


class TransactionContext:
    """Scoped transaction context for ACID atomic operations across MySQL and SQLite."""

    def __init__(self, db_type, conn):
        self.db_type = db_type
        self.conn = conn

    def query(self, sql, params=()):
        if self.db_type == "mysql":
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        else:
            sqlite_sql = sql.replace("%s", "?")
            cur = self.conn.cursor()
            try:
                cur.execute(sqlite_sql, params)
                return [dict(row) for row in cur.fetchall()]
            finally:
                cur.close()

    def get_one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def get_all(self, sql, params=()):
        return self.query(sql, params)

    def execute(self, sql, params=()):
        if self.db_type == "mysql":
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.lastrowid
        else:
            sqlite_sql = sql.replace("%s", "?")
            cur = self.conn.cursor()
            try:
                cur.execute(sqlite_sql, params)
                return cur.lastrowid
            finally:
                cur.close()

    def execute_update(self, sql, params=()):
        """Returns the number of rows affected by UPDATE or DELETE."""
        if self.db_type == "mysql":
            with self.conn.cursor() as cur:
                return cur.execute(sql, params)
        else:
            sqlite_sql = sql.replace("%s", "?")
            cur = self.conn.cursor()
            try:
                cur.execute(sqlite_sql, params)
                return cur.rowcount
            finally:
                cur.close()


class DB:
    """Unified Database Helper for executing queries across MySQL and SQLite."""

    @classmethod
    @contextmanager
    def transaction(cls):
        """Context manager providing an atomic ACID transaction with auto-commit and rollback."""
        db_type, conn = get_db_connection()
        if db_type == "mysql":
            conn.autocommit(False)
        else:
            conn.execute("BEGIN IMMEDIATE")
        try:
            tx = TransactionContext(db_type, conn)
            yield tx
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception as rb_err:
                logger.error("Transaction rollback failed: %s", type(rb_err).__name__)
            raise
        finally:
            if db_type == "mysql":
                release_mysql_connection(conn, reset_transaction=True)
            else:
                try:
                    conn.close()
                except Exception:
                    pass

    @staticmethod
    def query(sql, params=()):
        db_type, conn = get_db_connection()
        try:
            if db_type == "mysql":
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
            else:
                sqlite_sql = sql.replace("%s", "?")
                cur = conn.cursor()
                try:
                    cur.execute(sqlite_sql, params)
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
                finally:
                    cur.close()
        finally:
            if db_type == "mysql":
                release_mysql_connection(conn)
            else:
                conn.close()

    @staticmethod
    def query_many(queries):
        """Execute several read-only queries on one pooled connection."""
        db_type, conn = get_db_connection()
        try:
            results = []
            for sql, params in queries:
                if db_type == "mysql":
                    with conn.cursor() as cur:
                        cur.execute(sql, params)
                        results.append(cur.fetchall())
                else:
                    sqlite_sql = sql.replace("%s", "?")
                    cur = conn.cursor()
                    try:
                        cur.execute(sqlite_sql, params)
                        results.append([dict(row) for row in cur.fetchall()])
                    finally:
                        cur.close()
            return results
        finally:
            if db_type == "mysql":
                release_mysql_connection(conn)
            else:
                conn.close()

    @staticmethod
    def get_one(sql, params=()):
        rows = DB.query(sql, params)
        return rows[0] if rows else None

    @staticmethod
    def get_all(sql, params=()):
        return DB.query(sql, params)

    @staticmethod
    def execute(sql, params=()):
        db_type, conn = get_db_connection()
        try:
            if db_type == "mysql":
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.lastrowid
            else:
                sqlite_sql = sql.replace("%s", "?")
                cur = conn.cursor()
                try:
                    cur.execute(sqlite_sql, params)
                    conn.commit()
                    return cur.lastrowid
                finally:
                    cur.close()
        finally:
            if db_type == "mysql":
                release_mysql_connection(conn)
            else:
                conn.close()

    @staticmethod
    def execute_update(sql, params=()):
        """Executes an UPDATE/DELETE and returns affected row count."""
        db_type, conn = get_db_connection()
        try:
            if db_type == "mysql":
                with conn.cursor() as cur:
                    return cur.execute(sql, params)
            else:
                sqlite_sql = sql.replace("%s", "?")
                cur = conn.cursor()
                try:
                    cur.execute(sqlite_sql, params)
                    conn.commit()
                    return cur.rowcount
                finally:
                    cur.close()
        finally:
            if db_type == "mysql":
                release_mysql_connection(conn)
            else:
                conn.close()

    @staticmethod
    def execute_script(script, db_type=None):
        if db_type is None:
            db_type, conn = get_db_connection()
        else:
            conn = get_sqlite_connection() if db_type == "sqlite" else get_mysql_connection()
        try:
            if db_type == "mysql":
                with conn.cursor() as cur:
                    for statement in script.split(";"):
                        stmt = statement.strip()
                        if stmt:
                            cur.execute(stmt)
            else:
                conn.executescript(script)
                conn.commit()
        finally:
            if db_type == "mysql":
                release_mysql_connection(conn)
            else:
                conn.close()
