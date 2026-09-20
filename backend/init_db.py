import os
import sqlite3
import pymysql
from dotenv import load_dotenv
from security import hash_password

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "food_court_local.db")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer',
    is_active INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    customer_type TEXT NOT NULL DEFAULT 'student',
    full_name TEXT NOT NULL,
    identifier TEXT,
    mobile TEXT,
    wallet_balance REAL NOT NULL DEFAULT 500.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    owner_user_id INTEGER,
    description TEXT,
    category TEXT DEFAULT 'Multi-Cuisine',
    image_url TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    operational_status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    category TEXT NOT NULL DEFAULT 'Main Course',
    quantity INTEGER NOT NULL DEFAULT 0,
    is_available INTEGER NOT NULL DEFAULT 1,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_reference TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    shop_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    order_status TEXT NOT NULL DEFAULT 'pending',
    payment_status TEXT NOT NULL DEFAULT 'pending',
    payment_method TEXT NOT NULL DEFAULT 'Campus Wallet',
    pickup_otp TEXT NOT NULL,
    payment_time TIMESTAMP NULL,
    preparing_time TIMESTAMP NULL,
    ready_time TIMESTAMP NULL,
    completed_time TIMESTAMP NULL,
    cancellation_time TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    menu_item_id INTEGER,
    item_name TEXT NOT NULL,
    unit_price REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    subtotal REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    customer_id INTEGER,
    provider TEXT NOT NULL DEFAULT 'razorpay',
    method TEXT NOT NULL DEFAULT 'Campus Wallet',
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'pending',
    transaction_ref TEXT NOT NULL UNIQUE,
    gateway_order_id TEXT,
    gateway_payment_id TEXT,
    gateway_token TEXT,
    failure_reason TEXT,
    paid_at TIMESTAMP,
    refunded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    code TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'signup',
    expires_at TIMESTAMP NOT NULL,
    is_verified INTEGER NOT NULL DEFAULT 0,
    is_consumed INTEGER NOT NULL DEFAULT 0,
    verified_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    order_id INTEGER NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    delivery_status TEXT NOT NULL DEFAULT 'delivered',
    delivered_at TIMESTAMP NULL,
    failure_reason TEXT NULL,
    read_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    menu_item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE,
    UNIQUE (user_id, menu_item_id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    expense_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    source TEXT NOT NULL,
    description TEXT NOT NULL,
    income_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    amount_limit REAL NOT NULL,
    period TEXT NOT NULL DEFAULT 'monthly',
    start_date TEXT,
    end_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS financial_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    target_amount REAL NOT NULL,
    current_amount REAL NOT NULL DEFAULT 0.00,
    target_date TEXT,
    category TEXT DEFAULT 'Dining',
    status TEXT NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    is_used INTEGER NOT NULL DEFAULT 0,
    used_at TIMESTAMP NULL,
    ip_address TEXT NULL,
    user_agent TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS morning_surveys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    survey_date TEXT NOT NULL,
    meal_preference TEXT NOT NULL,
    hunger_level TEXT NOT NULL,
    dietary_preference TEXT NOT NULL DEFAULT 'any',
    meal_type TEXT NOT NULL DEFAULT 'breakfast',
    mood_energy TEXT,
    food_restrictions TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, survey_date)
);

CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_expense_user ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_expense_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_income_user ON income(user_id);
CREATE INDEX IF NOT EXISTS idx_income_date ON income(income_date);
CREATE INDEX IF NOT EXISTS idx_budget_user ON budgets(user_id);
CREATE INDEX IF NOT EXISTS idx_budget_category ON budgets(category);
CREATE INDEX IF NOT EXISTS idx_goal_user ON financial_goals(user_id);
CREATE INDEX IF NOT EXISTS idx_goal_status ON financial_goals(status);
CREATE INDEX IF NOT EXISTS idx_pwd_reset_token ON password_resets(token_hash);
CREATE INDEX IF NOT EXISTS idx_pwd_reset_user ON password_resets(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_user_unread ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notification_user_created ON notifications(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notification_order ON notifications(order_id);
CREATE INDEX IF NOT EXISTS idx_notification_type ON notifications(type);
CREATE INDEX IF NOT EXISTS idx_survey_user ON morning_surveys(user_id);
CREATE INDEX IF NOT EXISTS idx_survey_date ON morning_surveys(survey_date);
"""

DEFAULT_STALLS = [
    (1, "YPR", "ypr", 2, "Fresh authentic South Indian hot meals, dosas, and parottas", "Food", 1),
    (2, "Campus Kitchen", "campus-kitchen", 3, "Homestyle healthy combo meals, curries, and rotis", "Food", 1),
    (3, "German Cafe", "german-cafe", 4, "Crispy burgers, cheesy sandwiches, fries, and cold brews", "Food", 1),
    (4, "Royal Kitchen", "royal-kitchen", 5, "Special Biryanis, fried rice, noodles, and chicken delights", "Food", 1),
    (5, "Mario", "mario", 6, "Fresh fruit juices, shakes, smoothies, and quick pastries", "Juice & Maggi", 1),
    (6, "Saaral", "saaral", 7, "Traditional snacks, tea, filter coffee, samosas, and evening bites", "Snacks & Cakes", 1),
]

DEFAULT_USERS = [
    (1, "admin@kpriet.ac.in", hash_password("admin123"), "admin", 1),
    (2, "ypr@kpriet.ac.in", hash_password("vendor123"), "vendor", 1),
    (3, "campus@kpriet.ac.in", hash_password("vendor123"), "vendor", 1),
    (4, "german@kpriet.ac.in", hash_password("vendor123"), "vendor", 1),
    (5, "royal@kpriet.ac.in", hash_password("vendor123"), "vendor", 1),
    (6, "mario@kpriet.ac.in", hash_password("vendor123"), "vendor", 1),
    (7, "saaral@kpriet.ac.in", hash_password("vendor123"), "vendor", 1),
    (8, "student@kpriet.ac.in", hash_password("password123"), "customer", 1),
]

DEFAULT_MENU = [
    # YPR (Offerings: Food)
    (1, 1, "Crispy Ghee Podi Dosa", "Golden crispy dosa roasted in pure ghee and spiced podi with coconut chutney", 65.00, "Food", 30, 1),
    (2, 1, "Special South Indian Meals", "Steamed rice, sambar, rasam, kootu, poriyal, curd, and appalam", 90.00, "Food", 25, 1),
    (3, 1, "Egg Parotta (2 Pcs)", "Layered flaky parotta served with rich salna and onion raita", 70.00, "Food", 20, 1),

    # Campus Kitchen (Dev Seed Stall)
    (4, 2, "Paneer Butter Masala Combo", "Rich paneer gravy served with 3 butter rotis and jeera rice", 110.00, "Food", 25, 1),
    (5, 2, "Dal Makhani Rice Bowl", "Slow-cooked black lentils in creamy butter sauce over fragrant basmati", 85.00, "Food", 20, 1),
    (6, 2, "Aloo Paratha with Curd", "Stuffed spiced potato paratha served with fresh curd and pickle", 55.00, "Food", 35, 1),

    # German Cafe (Offerings: Food)
    (7, 3, "Crispy Veg Supreme Burger", "Herbed potato-corn patty with melted cheese, lettuce, and secret sauce", 75.00, "Food", 20, 1),
    (8, 3, "Peri Peri Loaded Fries", "Golden french fries seasoned with spicy peri-peri dust and cheese mayo", 60.00, "Food", 40, 1),
    (9, 3, "Grilled Chicken Sandwich", "Toasted triple-layer sandwich with shredded chicken, mayo, and herbs", 90.00, "Food", 15, 1),

    # Royal Kitchen (Offerings: Food, Tea, Snacks)
    (10, 4, "Royal Chicken Dum Biryani", "Aromatic seeraga samba rice cooked with tender chicken pieces and spices", 140.00, "Food", 35, 1),
    (11, 4, "Schezwan Veg Fried Rice", "Wok-tossed basmati rice with crunchy vegetables in spicy schezwan sauce", 90.00, "Food", 25, 1),
    (12, 4, "Royal Masala Chai", "Aromatic spiced milk tea brewed with crushed cardamom and ginger", 20.00, "Tea", 50, 1),
    (13, 4, "Crispy Chicken Cutlet", "Crisp spiced chicken patty served with mint chutney", 50.00, "Snacks", 25, 1),

    # Mario (Offerings: Juice, Maggi)
    (14, 5, "Fresh Mango Alphonso Shake", "Thick chilled shake made with ripe Alphonso mangoes and vanilla ice cream", 60.00, "Juice", 25, 1),
    (15, 5, "Fresh Sweet Lime Juice", "Freshly pressed sweet lime citrus cooler with mint sprig", 45.00, "Juice", 30, 1),
    (16, 5, "Classic Veg Masala Maggi", "Wok-tossed noodles with diced vegetables and authentic tastemaker masala", 40.00, "Maggi", 35, 1),
    (17, 5, "Cheese Butter Maggi", "Double spiced Maggi topped with melted butter and generous grated cheese", 55.00, "Maggi", 25, 1),

    # Saaral (Offerings: Snacks, Cakes)
    (18, 6, "Hot Samosa (2 Pcs) & Chutney", "Crisp triangular pastry stuffed with spiced potato and peas", 30.00, "Snacks", 45, 1),
    (19, 6, "Crispy Onion Pakoda", "Deep fried crunchy onion fritters with green chili and curry leaves", 35.00, "Snacks", 40, 1),
    (20, 6, "Chocolate Truffle Cake Slice", "Rich moist dark chocolate sponge layered with Dutch chocolate ganache", 65.00, "Cakes", 20, 1),
    (21, 6, "Red Velvet Cupcake", "Velvety crimson sponge topped with vanilla cream cheese frosting", 45.00, "Cakes", 25, 1),
]


def init_sqlite():
    print(f"Initializing SQLite database at: {SQLITE_PATH}")
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.executescript(SQLITE_SCHEMA)

    # Ensure schema migrations on pre-existing tables
    def _safe_add_column(table, col, col_def):
        try:
            cur.execute(f"PRAGMA table_info({table})")
            existing_cols = [r[1] for r in cur.fetchall()]
            if col not in existing_cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        except Exception as err:
            pass

    _safe_add_column("otp_codes", "is_consumed", "INTEGER NOT NULL DEFAULT 0")
    _safe_add_column("otp_codes", "verified_at", "TIMESTAMP NULL")
    _safe_add_column("customer_profiles", "wallet_balance", "REAL NOT NULL DEFAULT 500.00")
    _safe_add_column("orders", "payment_time", "TIMESTAMP NULL")
    _safe_add_column("orders", "preparing_time", "TIMESTAMP NULL")
    _safe_add_column("orders", "ready_time", "TIMESTAMP NULL")
    _safe_add_column("orders", "completed_time", "TIMESTAMP NULL")
    _safe_add_column("orders", "cancellation_time", "TIMESTAMP NULL")
    _safe_add_column("payments", "gateway_token", "TEXT NULL")
    _safe_add_column("payments", "customer_id", "INTEGER NULL")
    _safe_add_column("payments", "provider", "TEXT NOT NULL DEFAULT 'razorpay'")
    _safe_add_column("payments", "currency", "TEXT NOT NULL DEFAULT 'INR'")
    _safe_add_column("payments", "gateway_order_id", "TEXT NULL")
    _safe_add_column("payments", "gateway_payment_id", "TEXT NULL")
    _safe_add_column("payments", "failure_reason", "TEXT NULL")
    _safe_add_column("payments", "paid_at", "TIMESTAMP NULL")
    _safe_add_column("payments", "refunded_at", "TIMESTAMP NULL")
    _safe_add_column("payments", "updated_at", "TIMESTAMP NULL")
    _safe_add_column("shops", "operational_status", "TEXT NOT NULL DEFAULT 'OPEN'")
    _safe_add_column("shops", "created_by_admin", "TINYINT(1) NOT NULL DEFAULT 0")

    cur.executemany("INSERT OR REPLACE INTO users (id, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?)", DEFAULT_USERS)
    cur.execute("INSERT OR REPLACE INTO customer_profiles (id, user_id, customer_type, full_name, identifier, mobile) VALUES (1, 8, 'student', 'KPR Student', '21CS042', '9876543210')")
    cur.executemany("INSERT OR REPLACE INTO shops (id, name, slug, owner_user_id, description, category, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)", DEFAULT_STALLS)
    cur.executemany("INSERT OR REPLACE INTO menu_items (id, shop_id, name, description, price, category, quantity, is_available) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", DEFAULT_MENU)

    conn.commit()
    conn.close()
    print("SQLite database initialized and seeded successfully.")


def init_mysql():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "food_court_db")

    print(f"Attempting to initialize MySQL database '{db_name}' at {host}:{port} as user '{user}'...")
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.close()

        conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db_name, autocommit=True)
        schema_path = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
        seed_path = os.path.join(os.path.dirname(__file__), "..", "database", "seed.sql")

        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            with conn.cursor() as cur:
                for statement in schema_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        cur.execute(stmt)
            print("MySQL schema executed successfully.")

        # Seed data handling: Only seed in development mode or when explicitly opted in
        flask_env = os.getenv("FLASK_ENV", "development").lower()
        is_prod = flask_env in ("production", "prod")
        allow_seed = (not is_prod) or (os.getenv("SEED_DEMO_DATA", "0").lower() in ("1", "true", "yes"))

        if os.path.exists(seed_path):
            if allow_seed:
                with open(seed_path, "r", encoding="utf-8") as f:
                    seed_sql = f.read()
                with conn.cursor() as cur:
                    for statement in seed_sql.split(";"):
                        stmt = statement.strip()
                        if stmt:
                            cur.execute(stmt)
                print("MySQL seed executed successfully.")
            else:
                print("SECURITY NOTICE: Development seed credentials skipped in production mode. (Use SEED_DEMO_DATA=1 to override).")

        conn.close()
        print("MySQL database initialization complete.")
        return True
    except Exception as e:
        print(f"MySQL initialization skipped/failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    flask_env = os.getenv("FLASK_ENV", "development").lower()
    is_prod = flask_env in ("production", "prod")

    mysql_ok = init_mysql()
    if is_prod:
        if not mysql_ok:
            print("CRITICAL: MySQL database initialization failed in production mode. Aborting startup.", file=sys.stderr)
            sys.exit(1)
        print("\nProduction MySQL database initialization complete.")
    else:
        if not mysql_ok or os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes"):
            init_sqlite()
        print("\nDevelopment database initialization complete.")

