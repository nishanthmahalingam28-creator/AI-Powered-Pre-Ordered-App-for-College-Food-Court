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
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    UNIQUE (order_id)
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
    meal_period TEXT NOT NULL DEFAULT 'lunch',
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
    meal_period TEXT NOT NULL DEFAULT 'lunch',
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

CREATE TABLE IF NOT EXISTS contact_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    read_at TIMESTAMP NULL,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    order_id INTEGER,
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
    _safe_add_column("orders", "pickup_at", "TIMESTAMP NULL")
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
    _safe_add_column("morning_surveys", "plans_to_eat", "INTEGER NOT NULL DEFAULT 1")
    _safe_add_column("menu_items", "meal_period", "TEXT NOT NULL DEFAULT 'lunch'")
    _safe_add_column("order_items", "meal_period", "TEXT NOT NULL DEFAULT 'lunch'")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            employee_code TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            role_title TEXT NOT NULL DEFAULT 'Kitchen Staff',
            salary_type TEXT NOT NULL DEFAULT 'monthly',
            salary_amount REAL NOT NULL DEFAULT 0,
            joining_date DATE,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(shop_id, employee_code),
            FOREIGN KEY(shop_id) REFERENCES shops(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS worker_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            attendance_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'present',
            check_in TIME,
            check_out TIME,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(worker_id, attendance_date),
            FOREIGN KEY(worker_id) REFERENCES workers(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS worker_salary_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            salary_month DATE NOT NULL,
            base_salary REAL NOT NULL DEFAULT 0,
            attendance_days REAL NOT NULL DEFAULT 0,
            paid_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            paid_on DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(worker_id, salary_month),
            FOREIGN KEY(worker_id) REFERENCES workers(id) ON DELETE CASCADE
        )
    """)


    # Preserve the current production workflow: YPR is the existing Admin-created shop.
    # Future shops created through the Admin API are explicitly marked created_by_admin=1.
    try:
        cur.execute("UPDATE shops SET created_by_admin = 1 WHERE LOWER(name) = 'ypr'")
    except Exception:
        pass

    cur.executemany("INSERT OR REPLACE INTO users (id, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?)", DEFAULT_USERS)
    cur.execute("INSERT OR REPLACE INTO customer_profiles (id, user_id, customer_type, full_name, identifier, mobile) VALUES (1, 8, 'student', 'KPR Student', '21CS042', '9876543210')")
    cur.executemany("INSERT OR REPLACE INTO shops (id, name, slug, owner_user_id, description, category, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)", DEFAULT_STALLS)
    cur.executemany("INSERT OR REPLACE INTO menu_items (id, shop_id, name, description, price, category, quantity, is_available) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", DEFAULT_MENU)
    cur.execute("UPDATE menu_items SET meal_period = 'breakfast' WHERE LOWER(category) = 'breakfast'")

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

        # Production-safe migrations for existing MySQL databases.
        # CREATE TABLE IF NOT EXISTS does not add new columns to an existing table,
        # so explicitly migrate the shops table before the Admin-created-shop endpoint is used.
        with conn.cursor() as cur:
            # MySQL 8.4 does not support IF NOT EXISTS for ALTER TABLE ... ADD COLUMN.
            # Check INFORMATION_SCHEMA first so this migration is safe for both new and
            # existing production databases.
            cur.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'shops'
                  AND COLUMN_NAME = 'created_by_admin'
            """, (db_name,))
            column_exists = int(cur.fetchone()[0] or 0) > 0
            if not column_exists:
                cur.execute("""
                    ALTER TABLE shops
                    ADD COLUMN created_by_admin TINYINT(1) NOT NULL DEFAULT 0
                """)
                print("MySQL migration: added shops.created_by_admin.")
            else:
                print("MySQL migration: shops.created_by_admin already exists.")

            # Menu meal-period migration for Breakfast/Lunch/Dinner sections.
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'menu_items' AND COLUMN_NAME = 'meal_period'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE menu_items ADD COLUMN meal_period ENUM('breakfast','lunch','dinner') NOT NULL DEFAULT 'lunch'")
                print("MySQL migration: added menu_items.meal_period.")
            cur.execute("UPDATE menu_items SET meal_period = 'breakfast' WHERE LOWER(category) = 'breakfast'")

            # Order-item meal-period migration for immutable sales analytics.
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'order_items' AND COLUMN_NAME = 'meal_period'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE order_items ADD COLUMN meal_period ENUM('breakfast','lunch','dinner') NOT NULL DEFAULT 'lunch'")
                print("MySQL migration: added order_items.meal_period.")
            cur.execute("""
                UPDATE order_items oi
                INNER JOIN menu_items mi ON mi.id = oi.menu_item_id
                SET oi.meal_period = mi.meal_period
                WHERE oi.menu_item_id IS NOT NULL
            """)

            # Customer-selected pickup date/time migration.
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'orders' AND COLUMN_NAME = 'pickup_at'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE orders ADD COLUMN pickup_at DATETIME NULL AFTER pickup_otp")
                print("MySQL migration: added orders.pickup_at.")

            # Customer morning survey migration
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'morning_surveys' AND COLUMN_NAME = 'plans_to_eat'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE morning_surveys ADD COLUMN plans_to_eat TINYINT(1) NOT NULL DEFAULT 1")
                print("MySQL migration: added morning_surveys.plans_to_eat.")

            # Temporary customer account migration.
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = 'is_temporary'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE users ADD COLUMN is_temporary TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active")
                print("MySQL migration: added users.is_temporary.")

            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = 'account_expires_at'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE users ADD COLUMN account_expires_at DATETIME NULL AFTER is_temporary")
                print("MySQL migration: added users.account_expires_at.")

            # Contact Reports migration for existing production databases.
            # Older deployments may already have contact_messages without the newer
            # read/resolution timestamp columns.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contact_messages (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(120) NOT NULL,
                    email VARCHAR(180) NOT NULL,
                    subject VARCHAR(180) NOT NULL,
                    message TEXT NOT NULL,
                    status ENUM('new','read','resolved') NOT NULL DEFAULT 'new',
                    read_at DATETIME NULL,
                    resolved_at DATETIME NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_contact_status_created (status, created_at),
                    INDEX idx_contact_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            contact_columns = {
                "read_at": "DATETIME NULL",
                "resolved_at": "DATETIME NULL",
            }
            for column_name, definition in contact_columns.items():
                cur.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = 'contact_messages'
                      AND COLUMN_NAME = %s
                """, (db_name, column_name))
                if int(cur.fetchone()[0] or 0) == 0:
                    cur.execute(f"ALTER TABLE contact_messages ADD COLUMN {column_name} {definition}")
                    print(f"MySQL migration: added contact_messages.{column_name}.")

            # Ensure status supports all Contact Reports workflow states.
            cur.execute("""
                SELECT COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'contact_messages'
                  AND COLUMN_NAME = 'status'
            """, (db_name,))
            status_row = cur.fetchone()
            if status_row and "resolved" not in str(status_row[0]).lower():
                cur.execute("""
                    ALTER TABLE contact_messages
                    MODIFY COLUMN status ENUM('new','read','resolved') NOT NULL DEFAULT 'new'
                """)
                print("MySQL migration: updated contact_messages.status workflow.")

            # Performance indexes for the most frequent customer/vendor API queries.
            # Check INFORMATION_SCHEMA first so this migration is safe for existing databases.
            performance_indexes = [
                ("menu_items", "idx_menu_shop_availability", "ALTER TABLE menu_items ADD INDEX idx_menu_shop_availability (shop_id, is_available, quantity)"),
                ("orders", "idx_order_shop_status_payment", "ALTER TABLE orders ADD INDEX idx_order_shop_status_payment (shop_id, order_status, payment_status)"),
                ("orders", "idx_order_customer_status", "ALTER TABLE orders ADD INDEX idx_order_customer_status (customer_id, order_status, created_at)"),
                ("order_items", "idx_order_item_order", "ALTER TABLE order_items ADD INDEX idx_order_item_order (order_id)"),
                ("order_items", "idx_order_item_menu", "ALTER TABLE order_items ADD INDEX idx_order_item_menu (menu_item_id)")
            ]
            for table_name, index_name, alter_sql in performance_indexes:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = %s
                      AND INDEX_NAME = %s
                """, (db_name, table_name, index_name))
                if int(cur.fetchone()[0] or 0) == 0:
                    cur.execute(alter_sql)
                    print(f"MySQL migration: added {index_name}.")
            
            # Expenses migration for databases created before order-linked food expenses.
            # CREATE TABLE IF NOT EXISTS does not modify an existing expenses table.
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'expenses' AND COLUMN_NAME = 'order_id'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE expenses ADD COLUMN order_id INT UNSIGNED NULL AFTER user_id")
                print("MySQL migration: added expenses.order_id.")

            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'expenses' AND COLUMN_NAME = 'updated_at'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE expenses ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
                print("MySQL migration: added expenses.updated_at.")

            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'expenses' AND INDEX_NAME = 'uq_expense_order'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE expenses ADD UNIQUE KEY uq_expense_order (order_id)")
                print("MySQL migration: added expenses.uq_expense_order.")

            # Vendor worker management, attendance, and salary tables.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    shop_id INT UNSIGNED NOT NULL,
                    employee_code VARCHAR(50) NOT NULL,
                    full_name VARCHAR(150) NOT NULL,
                    phone VARCHAR(20) NULL,
                    role_title VARCHAR(100) NOT NULL DEFAULT 'Kitchen Staff',
                    salary_type ENUM('monthly','daily') NOT NULL DEFAULT 'monthly',
                    salary_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    joining_date DATE NULL,
                    status ENUM('active','inactive') NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_worker_shop FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
                    UNIQUE KEY uq_worker_shop_code (shop_id, employee_code),
                    INDEX idx_worker_shop_status (shop_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS worker_attendance (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    worker_id INT UNSIGNED NOT NULL,
                    attendance_date DATE NOT NULL,
                    status ENUM('present','absent','half_day','leave') NOT NULL DEFAULT 'present',
                    check_in TIME NULL,
                    check_out TIME NULL,
                    notes VARCHAR(255) NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_attendance_worker FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
                    UNIQUE KEY uq_worker_attendance_date (worker_id, attendance_date),
                    INDEX idx_attendance_date (attendance_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS worker_salary_payments (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    worker_id INT UNSIGNED NOT NULL,
                    salary_month DATE NOT NULL,
                    base_salary DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    attendance_days DECIMAL(6,2) NOT NULL DEFAULT 0.00,
                    paid_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    status ENUM('pending','paid') NOT NULL DEFAULT 'pending',
                    paid_on DATE NULL,
                    notes VARCHAR(255) NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_salary_worker FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
                    UNIQUE KEY uq_worker_salary_month (worker_id, salary_month),
                    INDEX idx_salary_month (salary_month)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Daily vendor survey tables are created by schema.sql above; this CREATE IF NOT EXISTS
            # is retained here for databases initialized before the new schema was deployed.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vendor_daily_surveys (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    vendor_user_id INT UNSIGNED NOT NULL,
                    shop_id INT UNSIGNED NOT NULL,
                    survey_date DATE NOT NULL,
                    is_serving_today TINYINT(1) NOT NULL DEFAULT 1,
                    breakfast_start TIME NOT NULL DEFAULT '06:00:00',
                    breakfast_end TIME NOT NULL DEFAULT '10:00:00',
                    lunch_start TIME NOT NULL DEFAULT '10:30:00',
                    lunch_end TIME NOT NULL DEFAULT '15:00:00',
                    dinner_start TIME NOT NULL DEFAULT '17:00:00',
                    dinner_end TIME NOT NULL DEFAULT '21:00:00',
                    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_vendor_daily_survey_user FOREIGN KEY (vendor_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT fk_vendor_daily_survey_shop FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
                    UNIQUE KEY uq_vendor_daily_survey_date (vendor_user_id, survey_date),
                    UNIQUE KEY uq_shop_daily_survey_date (shop_id, survey_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # Existing production databases need the new vendor-configurable Food Survey windows.
            survey_time_columns = {
                "breakfast_start": "TIME NOT NULL DEFAULT '06:00:00'",
                "breakfast_end": "TIME NOT NULL DEFAULT '10:00:00'",
                "lunch_start": "TIME NOT NULL DEFAULT '10:30:00'",
                "lunch_end": "TIME NOT NULL DEFAULT '15:00:00'",
                "dinner_start": "TIME NOT NULL DEFAULT '17:00:00'",
                "dinner_end": "TIME NOT NULL DEFAULT '21:00:00'",
            }
            for column_name, definition in survey_time_columns.items():
                cur.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'vendor_daily_surveys'
                      AND COLUMN_NAME = %s
                """, (db_name, column_name))
                if int(cur.fetchone()[0] or 0) == 0:
                    cur.execute(f"ALTER TABLE vendor_daily_surveys ADD COLUMN {column_name} {definition}")
                    print(f"MySQL migration: added Food Survey time column {column_name}.")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS vendor_daily_menu_items (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    survey_id INT UNSIGNED NOT NULL,
                    shop_id INT UNSIGNED NOT NULL,
                    menu_item_id INT UNSIGNED NOT NULL,
                    meal_period VARCHAR(20) NOT NULL,
                    item_name VARCHAR(150) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    quantity INT NOT NULL DEFAULT 0,
                    is_available TINYINT(1) NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_vendor_daily_menu_survey FOREIGN KEY (survey_id) REFERENCES vendor_daily_surveys(id) ON DELETE CASCADE,
                    CONSTRAINT fk_vendor_daily_menu_shop FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
                    CONSTRAINT fk_vendor_daily_menu_item FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE,
                    UNIQUE KEY uq_vendor_daily_menu_slot (survey_id, menu_item_id, meal_period),
                    INDEX idx_vendor_daily_menu_shop_date (shop_id, meal_period),
                    INDEX idx_vendor_daily_menu_item (menu_item_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Existing production databases may have vendor_daily_menu_items from an older
            # Food Survey version without meal_period. Migrate that table before creating/
            # backfilling morning_survey_votes, because the vote migration depends on d.meal_period.
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'vendor_daily_menu_items'
                  AND COLUMN_NAME = 'meal_period'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("""
                    ALTER TABLE vendor_daily_menu_items
                    ADD COLUMN meal_period VARCHAR(20) NULL DEFAULT 'lunch' AFTER menu_item_id
                """)
                print("MySQL migration: added vendor daily menu meal_period column.")

            # Backfill old daily-menu rows from the master menu item when possible.
            cur.execute("""
                UPDATE vendor_daily_menu_items d
                INNER JOIN menu_items m ON m.id = d.menu_item_id
                SET d.meal_period = COALESCE(NULLIF(m.meal_period, ''), 'lunch')
                WHERE d.meal_period IS NULL OR d.meal_period = ''
            """)
            cur.execute("""
                UPDATE vendor_daily_menu_items
                SET meal_period = 'lunch'
                WHERE meal_period IS NULL OR meal_period = ''
            """)
            cur.execute("""
                ALTER TABLE vendor_daily_menu_items
                MODIFY COLUMN meal_period VARCHAR(20) NOT NULL DEFAULT 'lunch'
            """)

            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'vendor_daily_menu_items'
                  AND INDEX_NAME = 'uq_vendor_daily_menu_slot'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("""
                    ALTER TABLE vendor_daily_menu_items
                    ADD UNIQUE KEY uq_vendor_daily_menu_slot (survey_id, menu_item_id, meal_period)
                """)

            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'vendor_daily_menu_items'
                  AND INDEX_NAME = 'idx_vendor_daily_menu_shop_date'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("""
                    ALTER TABLE vendor_daily_menu_items
                    ADD INDEX idx_vendor_daily_menu_shop_date (shop_id, meal_period)
                """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS morning_survey_votes (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    survey_id INT UNSIGNED NOT NULL,
                    menu_item_id INT UNSIGNED NOT NULL,
                    student_user_id INT UNSIGNED NOT NULL,
                    meal_period VARCHAR(20) NOT NULL,
                    voted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_msv_survey FOREIGN KEY (survey_id) REFERENCES vendor_daily_surveys(id) ON DELETE CASCADE,
                    CONSTRAINT fk_msv_menu FOREIGN KEY (menu_item_id) REFERENCES vendor_daily_menu_items(id) ON DELETE CASCADE,
                    CONSTRAINT fk_msv_student FOREIGN KEY (student_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY uq_msv_student_survey_item (survey_id, student_user_id, meal_period, menu_item_id),
                    INDEX idx_msv_item (survey_id, menu_item_id),
                    INDEX idx_msv_meal (survey_id, meal_period)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Food Survey votes: one submission per student per meal period,
            # while allowing multiple food choices inside that submission.
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'morning_survey_votes'
                  AND COLUMN_NAME = 'meal_period'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("ALTER TABLE morning_survey_votes ADD COLUMN meal_period VARCHAR(20) NULL AFTER student_user_id")
                print("MySQL migration: added Food Survey meal_period column.")

            # Backfill existing votes from the daily-menu row they reference.
            cur.execute("""
                UPDATE morning_survey_votes v
                INNER JOIN vendor_daily_menu_items d ON d.id = v.menu_item_id
                SET v.meal_period = d.meal_period
                WHERE v.meal_period IS NULL OR v.meal_period = ''
            """)
            cur.execute("ALTER TABLE morning_survey_votes MODIFY COLUMN meal_period VARCHAR(20) NOT NULL")

            # Remove legacy uniqueness rules and replace them with per-meal rules.
            for index_name in ("uq_msv_student_survey", "uq_msv_student_survey_item"):
                cur.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'morning_survey_votes'
                      AND INDEX_NAME = %s
                """, (db_name, index_name))
                if int(cur.fetchone()[0] or 0) > 0:
                    cur.execute(f"ALTER TABLE morning_survey_votes DROP INDEX {index_name}")

            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'morning_survey_votes'
                  AND INDEX_NAME = 'uq_msv_student_survey_item'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("""
                    ALTER TABLE morning_survey_votes
                    ADD UNIQUE KEY uq_msv_student_survey_item (survey_id, student_user_id, meal_period, menu_item_id)
                """)
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'morning_survey_votes'
                  AND INDEX_NAME = 'idx_msv_meal'
            """, (db_name,))
            if int(cur.fetchone()[0] or 0) == 0:
                cur.execute("""
                    ALTER TABLE morning_survey_votes
                    ADD INDEX idx_msv_meal (survey_id, meal_period)
                """)
            print("MySQL migration: Food Survey now supports one submission per student per meal.")

            # Preserve the existing production YPR shop as Admin-created.
            cur.execute("UPDATE shops SET created_by_admin = 1 WHERE LOWER(name) = 'ypr'")

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

