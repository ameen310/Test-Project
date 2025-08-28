# app.py
"""
Single-file Streamlit + SQLite e-commerce demo (Nike-style).
Features:
- SQLite DB creation + seeding (auto)
- Register / Login (passwords hashed + salt)
- Shop: search, category, sort, pagination
- Wishlist, Reviews (1-5), Ratings
- Cart + Checkout (orders, order_items), stock decrement
- Orders listing with line items
- Profile (change password + logout)
- Admin dashboard: metrics + product CRUD
All interactive widgets have unique keys to avoid duplicate-element errors.
"""

import streamlit as st
import sqlite3
from contextlib import contextmanager
from datetime import datetime
import hashlib, os
from math import ceil
from typing import Any, Dict, List, Optional, Tuple

# --------------------------
# Configuration
# --------------------------
DB_FILE = "nike_store_singlefile.db"
PAGE_SIZE = 6

# --------------------------
# DB helpers
# --------------------------
def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hashed, salt

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        # users
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        # products
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
        # orders
        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        # order_items
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
        # reviews
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
        # wishlist
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

def seed_products_and_admin():
    with get_conn() as conn:
        c = conn.cursor()
        # seed products if none
        c.execute("SELECT COUNT(*) FROM products")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            items = [
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
            """, items)
        # seed admin user if none
        c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            pwd_hash, salt = _hash_password("admin123")
            c.execute("""
                INSERT INTO users(username, password_hash, password_salt, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", pwd_hash, salt, 1, now))
        conn.commit()

# --------------------------
# Backend functions
# --------------------------
def register_user(username: str, password: str) -> Tuple[bool, str]:
    if not username or not password:
        return False, "Username & password are required."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
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
            return True, "Registration successful — you can now log in."
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
        return False, "New password must be at least 6 characters."
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash, password_salt FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        if not row:
            return False, "User not found."
        old_hash, _ = _hash_password(old_password, row["password_salt"])
        if old_hash != row["password_hash"]:
            return False, "Old password is incorrect."
        new_hash, new_salt = _hash_password(new_password)
        c.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (new_hash, new_salt, user_id))
        conn.commit()
        return True, "Password updated."

# Products listing
def list_products(search: str = "", category: str = "", price_min: float = None, price_max: float = None,
                  sort_by: str = "newest", page: int = 1, page_size: int = PAGE_SIZE):
    where = []
    params: List[Any] = []
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
        return False, "Rating must be between 1 and 5."
    with get_conn() as conn:
        c = conn.cursor()
        now = datetime.utcnow().isoformat()
        try:
            c.execute("""
                INSERT INTO reviews(user_id, product_id, rating, comment, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, product_id, rating, comment, now))
        except sqlite3.IntegrityError:
            # update existing
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
def place_order(user_id, cart_items: List[Dict[str, Any]]):
    """
    cart_items: list of dicts {id, name, price, quantity}
    Returns (ok, msg, order_id)
    """
    if not cart_items:
        return False, "Cart is empty.", None
    with get_conn() as conn:
        try:
            c = conn.cursor()
            # check stock
            for it in cart_items:
                c.execute("SELECT stock FROM products WHERE id=?", (it["id"],))
                row = c.fetchone()
                if not row or row["stock"] < it["quantity"]:
                    return False, f"Not enough stock for {it['name']}.", None
            total = sum(it["price"] * it["quantity"] for it in cart_items)
            now = datetime.utcnow().isoformat()
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

# Admin metrics
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

# --------------------------
# Initialize DB + seed
# --------------------------
init_db()
seed_products_and_admin()

# --------------------------
# Streamlit UI
# --------------------------
st.set_page_config(page_title="Nike-Style Store", page_icon="👟", layout="wide")

# small CSS
st.markdown("""
<style>
.card { background: #fff; border-radius:12px; padding:12px; box-shadow:0 6px 18px rgba(0,0,0,0.06); margin-bottom:12px; }
.header-row { display:flex; align-items:center; justify-content:space-between; }
.price { font-weight:800; font-size:18px; }
.muted { color: #6b7280; }
</style>
""", unsafe_allow_html=True)

# session defaults
if "user" not in st.session_state: st.session_state.user = None
if "cart" not in st.session_state: st.session_state.cart = []  # list of dicts {id,name,price,quantity}
if "active_review_pid" not in st.session_state: st.session_state.active_review_pid = None
if "admin_mode" not in st.session_state: st.session_state.admin_mode = "Add"

# helpers for UI
def logout_local():
    st.session_state.user = None
    st.session_state.cart = []
    st.session_state.active_review_pid = None

def add_to_cart_local(pid:int, name:str, price:float, qty:int):
    for it in st.session_state.cart:
        if it["id"] == pid:
            it["quantity"] += qty
            return
    st.session_state.cart.append({"id": pid, "name": name, "price": price, "quantity": qty})

def stars(r: float) -> str:
    filled = int(round(r))
    return "★"*filled + "☆"*(5-filled)

# --- Authentication UI ---
def auth_ui():
    st.title("👟 Nike-Style Store")
    st.write("Sign in or create an account to begin shopping.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Login")
        login_user = st.text_input("Username", key="login_user_key")
        login_pass = st.text_input("Password", type="password", key="login_pass_key")
        if st.button("Login", key="login_btn_key"):
            ok, user = authenticate(login_user, login_pass)
            if ok:
                st.session_state.user = user
                st.success(f"Welcome back, {user['username']}!")
            else:
                st.error("Invalid credentials.")
    with c2:
        st.subheader("Register")
        reg_user = st.text_input("New username", key="reg_user_key")
        reg_pass = st.text_input("New password", type="password", key="reg_pass_key")
        if st.button("Create account", key="reg_btn_key"):
            ok, msg = register_user(reg_user, reg_pass)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

# --- Shop Tab ---
def shop_tab():
    st.header("Shop")
    min_p, max_p = product_min_max_price()
    c1, c2, c3, c4 = st.columns([3,1,2,1])
    with c1:
        search = st.text_input("Search products", key="search_key")
    with c2:
        cats = product_categories()
        cat = st.selectbox("Category", cats, key="cat_key")
    with c3:
        price_range = st.slider("Price range", float(min_p), float(max_p) if max_p>0 else 500.0,
                                (float(min_p), float(max_p) if max_p>0 else 500.0), key="price_key")
    with c4:
        sort_by = st.selectbox("Sort", ["newest", "price_asc", "price_desc", "rating_desc"], key="sort_key")

    page = st.number_input("Page", min_value=1, value=1, step=1, key="page_key")
    products, total = list_products(search=search, category=cat, price_min=price_range[0],
                                    price_max=price_range[1], sort_by=sort_by, page=page, page_size=PAGE_SIZE)
    total_pages = max(1, ceil(total / PAGE_SIZE))
    st.caption(f"Showing page {page}/{total_pages} — {total} items")

    # grid rows
    for i in range(0, len(products), 3):
        cols = st.columns(3)
        for j, p in enumerate(products[i:i+3]):
            with cols[j]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.image(p["image"], use_column_width=True)
                st.markdown(f"**{p['name']}**")
                st.markdown(f"<div class='price'>${p['price']:.2f}</div>", unsafe_allow_html=True)
                if p["category"]:
                    st.caption(f"{p['category']}")
                st.write(stars(p["avg_rating"] or 0) + f"  ({int(p['review_count'] or 0)})", unsafe_allow_html=True)
                st.caption(p["description"] or "")
                qty_key = f"qty_{p['id']}"
                st.number_input("Qty", min_value=1, max_value=max(1, int(p["stock"])), value=1, key=qty_key)
                if st.button("Add to cart", key=f"addcart_{p['id']}"):
                    qty = int(st.session_state[qty_key])
                    add_to_cart_local(p["id"], p["name"], float(p["price"]), qty)
                    st.success(f"Added {qty} × {p['name']} to cart.")
                if st.button("Add to wishlist", key=f"wish_{p['id']}"):
                    ok, msg = add_wishlist(st.session_state.user["id"], p["id"])
                    st.success(msg) if ok else st.error(msg)
                if st.button("Write review", key=f"rev_{p['id']}"):
                    st.session_state.active_review_pid = p["id"]
                st.markdown("</div>", unsafe_allow_html=True)

# --- Wishlist Tab ---
def wishlist_tab():
    st.header("Wishlist")
    items = get_wishlist(st.session_state.user["id"])
    if not items:
        st.info("Your wishlist is empty.")
        return
    for i in range(0, len(items), 3):
        cols = st.columns(3)
        for j, p in enumerate(items[i:i+3]):
            with cols[j]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.image(p["image"], use_column_width=True)
                st.markdown(f"**{p['name']}**")
                st.markdown(f"<div class='price'>${p['price']:.2f}</div>", unsafe_allow_html=True)
                st.caption(p["category"] or "")
                if st.button("Add to cart", key=f"wl_add_{p['id']}"):
                    add_to_cart_local(p["id"], p["name"], float(p["price"]), 1)
                    st.success("Added to cart.")
                if st.button("Remove", key=f"wl_remove_{p['id']}"):
                    ok, msg = remove_wishlist(st.session_state.user["id"], p["id"])
                    st.success(msg)
                st.markdown("</div>", unsafe_allow_html=True)

# --- Reviews tab (active for a product) ---
def review_flow(pid:int):
    st.header("Write a Review")
    st.caption(f"Product id: {pid}")
    rating = st.slider("Rating", 1, 5, 5, key=f"rev_rating_{pid}")
    comment = st.text_area("Comment", key=f"rev_comment_{pid}")
    if st.button("Save review", key=f"save_rev_{pid}"):
        ok, msg = add_review(st.session_state.user["id"], pid, rating, comment)
        if ok:
            st.success(msg)
            st.session_state.active_review_pid = None
        else:
            st.error(msg)
    st.divider()
    st.subheader("Recent Reviews")
    for r in get_reviews(pid):
        st.markdown(f"**{r['username']}** — {stars(r['rating'])}")
        if r["comment"]:
            st.caption(r["comment"])

# --- Cart & Checkout ---
def cart_tab():
    st.header("Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return
    total = 0.0
    # show cart with quantity controls
    for idx, it in enumerate(list(st.session_state.cart)):
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        with c1:
            st.write(it["name"])
        with c2:
            qty_key = f"cart_qty_{idx}"
            st.number_input("Qty", min_value=1, value=int(it["quantity"]), key=qty_key)
        with c3:
            price_line = it["price"] * st.session_state[qty_key]
            st.write(f"${price_line:.2f}")
        with c4:
            if st.button("Remove", key=f"cart_rm_{idx}"):
                st.session_state.cart.pop(idx)
                st.experimental_rerun()
        # update quantity
        it["quantity"] = int(st.session_state[qty_key])
        total += it["price"] * it["quantity"]
    st.subheader(f"Total: ${total:.2f}")
    if st.button("Clear cart", key="clear_cart_btn"):
        st.session_state.cart = []
        st.success("Cart cleared.")
    if st.button("Checkout", key="checkout_btn"):
        ok, msg, order_id = place_order(st.session_state.user["id"], st.session_state.cart)
        if ok:
            st.success(f"{msg} (Order #{order_id})")
            st.balloons()
            st.session_state.cart = []
        else:
            st.error(msg)

# --- Orders ---
def orders_tab():
    st.header("Orders")
    orders = list_orders(st.session_state.user["id"])
    if not orders:
        st.info("No orders yet.")
        return
    for o in orders:
        with st.expander(f"Order #{o['id']} — {o['created_at']} — ${o['total']:.2f}"):
            for it in order_items(o["id"]):
                c1, c2 = st.columns([1,4])
                with c1:
                    st.image(it["image"], width=80)
                with c2:
                    st.write(f"**{it['name']}**")
                    st.caption(f"Qty: {it['quantity']} — ${it['price_each']:.2f} each")

# --- Profile ---
def profile_tab():
    st.header("Profile")
    st.write(f"Username: **{st.session_state.user['username']}**")
    st.subheader("Change password")
    old = st.text_input("Old password", type="password", key="chg_old")
    new = st.text_input("New password", type="password", key="chg_new")
    if st.button("Change password", key="chg_btn"):
        ok, msg = change_password(st.session_state.user["id"], old, new)
        st.success(msg) if ok else st.error(msg)
    if st.button("Logout", key="logout_profile_btn"):
        logout_local()
        st.experimental_rerun()

# --- Admin ---
def admin_tab():
    if not st.session_state.user.get("is_admin"):
        st.warning("Admin only area.")
        return
    st.header("Admin Dashboard")
    m = admin_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users", m["users"], key="adm_users_metric")
    c2.metric("Orders", m["orders"], key="adm_orders_metric")
    c3.metric("Revenue ($)", float(m["revenue"]), key="adm_revenue_metric")
    c4.metric("Products", m["products"], key="adm_products_metric")
    if m["low_stock"]:
        st.subheader("Low stock")
        for row in m["low_stock"]:
            st.write(f"{row['name']}: {row['stock']} left")
    st.divider()
    st.subheader("Manage Products")
    mode = st.selectbox("Mode", ["Add", "Update", "Delete"], key="admin_mode_key")
    products_all, _ = list_products(page=1, page_size=9999)
    current = None
    if mode in ("Update", "Delete"):
        opts = {f"#{p['id']} {p['name']}": p for p in products_all}
        sel = st.selectbox("Select product", list(opts.keys()), key="admin_select_key")
        current = opts[sel]
    name = st.text_input("Name", value=current["name"] if current else "", key="admin_name_key")
    price = st.number_input("Price", min_value=0.0, value=float(current["price"]) if current else 100.0, key="admin_price_key")
    image = st.text_input("Image URL", value=current["image"] if current else "", key="admin_image_key")
    category = st.text_input("Category", value=current["category"] if current else "Casual", key="admin_cat_key")
    desc = st.text_area("Description", value=current["description"] if current else "", key="admin_desc_key")
    stock = st.number_input("Stock", min_value=0, value=int(current["stock"]) if current else 10, key="admin_stock_key")
    if st.button("Submit", key="admin_submit_key"):
        if mode == "Add":
            ok, msg = add_product(name, price, image, category, desc, stock)
            st.success(msg) if ok else st.error(msg)
        elif mode == "Update":
            ok, msg = update_product(current["id"], name, price, image, category, desc, stock)
            st.success(msg) if ok else st.error(msg)
        elif mode == "Delete":
            ok, msg = delete_product(current["id"])
            st.success(msg) if ok else st.error(msg)

# Router
def router():
    if st.session_state.active_review_pid:
        review_flow(st.session_state.active_review_pid)
        return
    tabs = st.tabs(["Shop", "Cart", "Orders", "Wishlist", "Profile"] + (["Admin"] if st.session_state.user.get("is_admin") else []))
    with tabs[0]:
        shop_tab()
    with tabs[1]:
        cart_tab()
    with tabs[2]:
        orders_tab()
    with tabs[3]:
        wishlist_tab()
    with tabs[4]:
        profile_tab()
    if st.session_state.user.get("is_admin"):
        with tabs[5]:
            admin_tab()

# Entry point
if st.session_state.user is None:
    auth_ui()
else:
    top_left, top_right = st.columns([4,1])
    with top_left:
        st.title(f"Hello, {st.session_state.user['username']} 👋")
        st.caption("Browse, wishlist, review, and shop your favorite kicks.")
    with top_right:
        if st.button("Logout", key="logout_top_btn"):
            logout_local()
            st.experimental_rerun()
    router()
