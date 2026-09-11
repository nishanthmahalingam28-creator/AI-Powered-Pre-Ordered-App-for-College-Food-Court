import os
import sqlite3
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "food_court_local.db")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer',
    is_active INTEGER NOT NULL DEFAULT 1,
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
    payment_status TEXT NOT NULL DEFAULT 'paid',
    payment_method TEXT NOT NULL DEFAULT 'Campus Wallet',
    pickup_otp TEXT NOT NULL,
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
    method TEXT NOT NULL DEFAULT 'Campus Wallet',
    amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'successful',
    transaction_ref TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    code TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'signup',
    expires_at TIMESTAMP NOT NULL,
    is_verified INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DEFAULT_STALLS = [
    (1, "YPR", "ypr", 2, "Fresh authentic South Indian hot meals, dosas, and parottas", "South Indian", 1),
    (2, "Campus Kitchen", "campus-kitchen", 3, "Homestyle healthy combo meals, curries, and rotis", "North & South", 1),
    (3, "German Cafe", "german-cafe", 4, "Crispy burgers, cheesy sandwiches, fries, and cold brews", "Fast Food", 1),
    (4, "Royal Kitchen", "royal-kitchen", 5, "Special Biryanis, fried rice, noodles, and chicken delights", "Biryani & Chinese", 1),
    (5, "Mario", "mario", 6, "Fresh fruit juices, shakes, smoothies, and quick pastries", "Beverages & Juices", 1),
    (6, "Saaral", "saaral", 7, "Traditional snacks, tea, filter coffee, samosas, and evening bites", "Snacks & Cafe", 1),
]

DEFAULT_USERS = [
    (1, "admin@kpriet.ac.in", generate_password_hash("admin123"), "admin", 1),
    (2, "ypr@kpriet.ac.in", generate_password_hash("vendor123"), "vendor", 1),
    (3, "campus@kpriet.ac.in", generate_password_hash("vendor123"), "vendor", 1),
    (4, "german@kpriet.ac.in", generate_password_hash("vendor123"), "vendor", 1),
    (5, "royal@kpriet.ac.in", generate_password_hash("vendor123"), "vendor", 1),
    (6, "mario@kpriet.ac.in", generate_password_hash("vendor123"), "vendor", 1),
    (7, "saaral@kpriet.ac.in", generate_password_hash("vendor123"), "vendor", 1),
    (8, "student@kpriet.ac.in", generate_password_hash("password123"), "customer", 1),
]

DEFAULT_MENU = [
    (1, 1, "Crispy Ghee Podi Dosa", "Golden crispy dosa roasted in pure ghee and spiced podi with coconut chutney", 65.00, "Main Course", 30, 1),
    (2, 1, "Special South Indian Meals", "Steamed rice, sambar, rasam, kootu, poriyal, curd, and appalam", 90.00, "Main Course", 25, 1),
    (3, 1, "Egg Parotta (2 Pcs)", "Layered flaky parotta served with rich salna and onion raita", 70.00, "Main Course", 20, 1),
    (4, 2, "Paneer Butter Masala Combo", "Rich paneer gravy served with 3 butter rotis and jeera rice", 110.00, "Main Course", 25, 1),
    (5, 2, "Dal Makhani Rice Bowl", "Slow-cooked black lentils in creamy butter sauce over fragrant basmati", 85.00, "Main Course", 20, 1),
    (6, 2, "Aloo Paratha with Curd", "Stuffed spiced potato paratha served with fresh curd and pickle", 55.00, "Breakfast", 35, 1),
    (7, 3, "Crispy Veg Supreme Burger", "Herbed potato-corn patty with melted cheese, lettuce, and secret sauce", 75.00, "Fast Food", 20, 1),
    (8, 3, "Peri Peri Loaded Fries", "Golden french fries seasoned with spicy peri-peri dust and cheese mayo", 60.00, "Snacks", 40, 1),
    (9, 3, "Grilled Chicken Sandwich", "Toasted triple-layer sandwich with shredded chicken, mayo, and herbs", 90.00, "Fast Food", 15, 1),
    (10, 4, "Royal Chicken Dum Biryani", "Aromatic seeraga samba rice cooked with tender chicken pieces and spices", 140.00, "Main Course", 35, 1),
    (11, 4, "Schezwan Veg Fried Rice", "Wok-tossed basmati rice with crunchy vegetables in spicy schezwan sauce", 90.00, "Chinese", 25, 1),
    (12, 4, "Chicken Noodles", "Hakka noodles tossed with egg, shredded chicken, and spring onions", 110.00, "Chinese", 20, 1),
    (13, 5, "Fresh Mango Alphonso Shake", "Thick chilled shake made with ripe Alphonso mangoes and vanilla ice cream", 60.00, "Beverages", 25, 1),
    (14, 5, "Cold Coffee with Cream", "Blended robust espresso with cold milk and whipped cream crown", 50.00, "Beverages", 30, 1),
    (15, 5, "Chocolate Lava Pastry", "Warm gooey molten chocolate cake dusted with powdered sugar", 55.00, "Desserts", 15, 1),
    (16, 6, "Filter Coffee (Special Degree)", "Freshly brewed Kumbakonam style decoction milk coffee", 25.00, "Beverages", 50, 1),
    (17, 6, "Hot Samosa (2 Pcs) & Chutney", "Crisp triangular pastry stuffed with spiced potato and peas", 30.00, "Snacks", 45, 1),
    (18, 6, "Masala Tea", "Strong hand-brewed ginger cardamom milk tea", 20.00, "Beverages", 60, 1),
]


def init_sqlite():
    print(f"Initializing SQLite database at: {SQLITE_PATH}")
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.executescript(SQLITE_SCHEMA)

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

        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_sql = f.read()
            with conn.cursor() as cur:
                for statement in seed_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        cur.execute(stmt)
            print("MySQL seed executed successfully.")

        conn.close()
        print("MySQL database initialized and seeded successfully.")
        return True
    except Exception as e:
        print(f"MySQL initialization skipped/failed: {e}")
        return False


if __name__ == "__main__":
    mysql_ok = init_mysql()
    init_sqlite()
    print("\nDatabase initialization complete.")
