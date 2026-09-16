import os
import re
import sqlite3
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "food_court_local.db")


def is_mysql_configured():
    # If explicitly forced to sqlite or password empty and not tested
    return os.getenv("USE_SQLITE", "").lower() not in {"1", "true", "yes"}


def get_mysql_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "food_court_db"),
        cursorclass=DictCursor,
        autocommit=True,
        charset="utf8mb4",
    )


def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db_connection():
    """
    Attempts to connect to MySQL. If MySQL is unavailable (or credentials denied),
    gracefully falls back to SQLite for seamless local execution.
    """
    if is_mysql_configured():
        try:
            return ("mysql", get_mysql_connection())
        except Exception as e:
            # Fallback to local SQLite database
            pass
    return ("sqlite", get_sqlite_connection())


from contextlib import contextmanager


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
            cur.execute(sqlite_sql, params)
            return [dict(row) for row in cur.fetchall()]

    def get_one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        if self.db_type == "mysql":
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.lastrowid
        else:
            sqlite_sql = sql.replace("%s", "?")
            cur = self.conn.cursor()
            cur.execute(sqlite_sql, params)
            return cur.lastrowid

    def execute_update(self, sql, params=()):
        """Returns the number of rows affected by UPDATE or DELETE."""
        if self.db_type == "mysql":
            with self.conn.cursor() as cur:
                return cur.execute(sql, params)
        else:
            sqlite_sql = sql.replace("%s", "?")
            cur = self.conn.cursor()
            cur.execute(sqlite_sql, params)
            return cur.rowcount


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
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def query(sql, params=()):
        db_type, conn = get_db_connection()
        try:
            if db_type == "mysql":
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
            else:
                # Convert %s to ? for SQLite
                sqlite_sql = sql.replace("%s", "?")
                cur = conn.cursor()
                cur.execute(sqlite_sql, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_one(sql, params=()):
        rows = DB.query(sql, params)
        return rows[0] if rows else None

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
                cur.execute(sqlite_sql, params)
                conn.commit()
                return cur.lastrowid
        finally:
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
                cur.execute(sqlite_sql, params)
                conn.commit()
                return cur.rowcount
        finally:
            conn.close()

    @staticmethod
    def execute_script(script, db_type=None):
        if db_type is None:
            db_type, _ = get_db_connection()
        # Used by init_db.py
