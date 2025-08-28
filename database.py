# database.py
import sqlite3
from contextlib import contextmanager
from datetime import datetime
import hashlib
import os
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = "nike_store.db"

def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hashed, salt

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT,
            category TEXT,
            description TEXT,
            stock INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_each REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        conn.commit()

def seed_products():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM products")
        if c.fetchone()[0] > 0:
            return
        now = datetime.utcnow().isoformat()
        products = [
            ("Air Max 270", 150, "https://images.unsplash.com/photo-1606813903134-45c28b953b3f", "Running",
             "Breathable mesh with bold Air cushioning.", 25, now),
            ("Jordan Retro", 200, "https://images.unsplash.com/photo-1542291026-7eec264c27ff", "Basketball",
             "Iconic style meets modern support.", 18, now),
            ("Blazer Mid '77", 120, "https://images.unsplash.com/photo-1595950653171-47c33e5f1d6e", "Casual",
             "Vintage vibes with everyday comfort.", 30, now),
            ("Pegasus Trail 4", 140, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?ixlib=rb-4.0.3", "Trail",
             "Grip and glide for off-road miles.", 15, now),
            ("Metcon 9", 130, "https://images.unsplash.com/photo-1600180758890-6b94519a8ba6", "Training",
             "Stable platform for heavy lifts.", 22, now),
            ("ZoomX Vaporfly", 250, "https://images.unsplash.com/photo-1519741497674-611481863552", "Racing",
             "Featherweight speed with propulsive foam.", 10, now),
        ]
        c.executemany("""
            INSERT INTO products(name, price, image, category, description, stock, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, products)
        conn.commit()

def seed_admin():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            pwd_hash, salt = _hash_password("admin123")
            c.execute("""
                INSERT INTO users(username, password_hash, password_salt, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", pwd_hash, salt, 1, now))
            conn.commit()

# Users
def register_user(username: str, password: str) -> Tuple[bool, str]:
    if not username or not password:
        return False, "Username and password required."
    if len(username) < 3:
        return False, "Username must be >= 3 chars."
    if len(password) < 6:
        return False, "Password must be >= 6 chars."
    try:
        with get_conn() as conn:
            c = conn.cursor()
            pwd_hash, salt = _hash_password(password)
            now = datetime.utcnow().isoformat()
            c.execute("""
                INSERT INTO users(username, password_hash, password_salt, is_admin, created_at)
                VALUES (?, ?, ?, 0, ?)
            """, (username.strip(), pwd_hash, salt, now))
            conn.commit()
            return True, "Registration successful."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, f"Error: {e}"

def authenticate(username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username.strip(),))
        row = c.fetchone()
        if not row:
            return False, None
        stored_hash = row["password_hash"]
        salt = row["password_salt"]
        test_hash, _ = _hash_password(password, salt)
        if test_hash == stored_hash:
            return True, dict(row)
        return False, None

def change_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
    if len(new_password) < 6:
        return False, "New password must be >= 6 chars."
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash, password_salt FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        if not row:
            return False, "User not found."
        old_hash, _ = _hash_password(old_password, row["password_salt"])
        if old_hash != row["password_hash"]:
            return False, "Old password incorrect."
        new_hash, new_salt = _hash_password(new_password)
        c.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (new_hash, new_salt, user_id))
        conn.commit()
        return True, "Password updated."

# Products & listing
def list_products(search: str = "", category: str = "", price_min: float = None, price_max: float = None,
                  sort_by: str = "newest", page: int = 1, page_size: int = 6):
    where = []
    params = []
    if search:
        where.append("LOWER(name) LIKE ?")
        params.append(f"%{search.lower()}%")
    if category and category != "All":
        where.append("category = ?")
        params.append(category)
    if price_min is not None:
        where.append("price >= ?"); params.append(price_min)
    if price_max is not None:
        where.append("price <= ?"); params.append(price_max)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    if sort_by == "price_asc":
        order_sql = "ORDER BY price ASC"
    elif sort_by == "price_desc":
        order_sql = "ORDER BY price DESC"
    elif sort_by == "rating_desc":
        order_sql = "ORDER BY (SELECT COALESCE(AVG(rating),0) FROM reviews r WHERE r.product_id=products.id) DESC"
    else:
        order_sql = "ORDER BY datetime(created_at) DESC"
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM products {where_sql}", params)
        total = c.fetchone()[0]
        offset = (page - 1) * page_size
        c.execute(f"""
            SELECT p.*,
            (SELECT COALESCE(AVG(rating),0) FROM reviews r WHERE r.product_id = p.id) AS avg_rating,
            (SELECT COUNT(*) FROM reviews r2 WHERE r2.product_id = p.id) AS review_count
            FROM products p
            {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
        """, (*params, page_size, offset))
        rows = c.fetchall()
        return rows, total

def product_min_max_price():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT MIN(price), MAX(price) FROM products")
        mn, mx = c.fetchone()
        return float(mn or 0.0), float(mx or 0.0)

def product_categories():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT COALESCE(category,'Uncategorized') FROM products")
        cats = [r[0] for r in c.fetchall()]
        cats.sort()
        return ["All"] + cats

def add_product(name, price, image, category, description, stock):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO products(name, price, image, category, description, stock, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, price, image, category, description, stock, now))
        conn.commit()
        return True, "Product added."

def update_product(pid, name, price, image, category, description, stock):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE products SET name=?, price=?, image=?, category=?, description=?, stock=?
            WHERE id=?
        """, (name, price, image, category, description, stock, pid))
        conn.commit()
        return True, "Product updated."

def delete_product(pid):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
        return True, "Product deleted."

# Wishlist & reviews
def add_wishlist(user_id, product_id):
    try:
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO wishlist(user_id, product_id, created_at) VALUES (?, ?, ?)",
                      (user_id, product_id, datetime.utcnow().isoformat()))
            conn.commit()
            return True, "Added to wishlist."
    except Exception as e:
        return False, f"Error: {e}"

def remove_wishlist(user_id, product_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?", (user_id, product_id))
        conn.commit()
        return True, "Removed from wishlist."

def get_wishlist(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT p.*,
            (SELECT COALESCE(AVG(rating),0) FROM reviews r WHERE r.product_id=p.id) AS avg_rating
            FROM wishlist w JOIN products p ON p.id = w.product_id
            WHERE w.user_id=?
            ORDER BY datetime(w.created_at) DESC
        """, (user_id,))
        return c.fetchall()

def add_review(user_id, product_id, rating, comment):
    if rating < 1 or rating > 5:
        return False, "Rating 1-5 required."
    with get_conn() as conn:
        c = conn.cursor()
        now = datetime.utcnow().isoformat()
        try:
            c.execute("""
                INSERT INTO reviews(user_id, product_id, rating, comment, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, product_id, rating, comment, now))
        except sqlite3.IntegrityError:
            c.execute("""
                UPDATE reviews SET rating=?, comment=?, created_at=?
                WHERE user_id=? AND product_id=?
            """, (rating, comment, now, user_id, product_id))
        conn.commit()
        return True, "Review saved."

def get_reviews(product_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT r.*, u.username FROM reviews r
            JOIN users u ON u.id = r.user_id
            WHERE r.product_id=?
            ORDER BY datetime(r.created_at) DESC
        """, (product_id,))
        return c.fetchall()

# Orders & checkout
def place_order(user_id, cart_items):
    if not cart_items: return False, "Cart empty.", None
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        try:
            c = conn.cursor()
            for it in cart_items:
                c.execute("SELECT stock FROM products WHERE id=?", (it["id"],))
                row = c.fetchone()
                if not row or row["stock"] < it["quantity"]:
                    return False, f"Not enough stock for {it['name']}.", None
            total = sum(it["price"] * it["quantity"] for it in cart_items)
            c.execute("INSERT INTO orders(user_id, created_at, total) VALUES (?, ?, ?)", (user_id, now, total))
            order_id = c.lastrowid
            for it in cart_items:
                c.execute("""
                    INSERT INTO order_items(order_id, product_id, quantity, price_each)
                    VALUES (?, ?, ?, ?)
                """, (order_id, it["id"], it["quantity"], it["price"]))
                c.execute("UPDATE products SET stock = stock - ? WHERE id=?", (it["quantity"], it["id"]))
            conn.commit()
            return True, "Order placed.", order_id
        except Exception as e:
            conn.rollback()
            return False, f"Error placing order: {e}", None

def list_orders(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY datetime(created_at) DESC", (user_id,))
        return c.fetchall()

def order_items(order_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT oi.*, p.name, p.image
            FROM order_items oi JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id=?
        """, (order_id,))
        return c.fetchall()

def admin_metrics():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users"); users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM orders"); orders = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders"); revenue = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM products"); products = c.fetchone()[0]
        c.execute("SELECT id, name, stock FROM products WHERE stock <= 5 ORDER BY stock ASC")
        low_stock = c.fetchall()
        return {"users": users, "orders": orders, "revenue": revenue, "products": products, "low_stock": low_stock}

# initialize
init_db()
seed_products()
seed_admin()
