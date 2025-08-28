# app.py
"""
Single-file Streamlit e-commerce demo (A → Z).
- Safe DB path (Streamlit Cloud friendly)
- Tables created IF NOT EXISTS (no destructive ops)
- Seeds sample data only when empty
- Auth (hashed password + salt), register/login
- Products: list, detail, add-to-cart
- Wishlist, Reviews, Orders, Admin CRUD & metrics
- Release calendar & basic store locator
All widget keys are unique.
"""

import streamlit as st
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib, os, time
from math import ceil
from typing import Any, Dict, List, Optional, Tuple

# --------------------------
# DB PATH (Streamlit Cloud safe)
# --------------------------
def choose_db_path(filename: str = "nike_store.db") -> str:
    # Prefer /mnt/data on Streamlit Cloud (writable)
    if os.path.isdir("/mnt/data") and os.access("/mnt/data", os.W_OK):
        return os.path.join("/mnt/data", filename)
    # Otherwise use same directory as script
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)

DB_PATH = choose_db_path("nike_store.db")

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
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass

def init_db():
    """Create tables only if they don't exist."""
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
            images TEXT,
            category TEXT,
            description TEXT,
            stock INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, product_id)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, product_id)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            total REAL NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_each REAL NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS releases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            product_id INTEGER,
            drop_datetime TEXT NOT NULL,
            description TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, city TEXT, address TEXT, phone TEXT, lat REAL, lon REAL
        )""")
        conn.commit()

def seed_if_empty():
    with get_conn() as conn:
        c = conn.cursor()
        # seed products
        c.execute("SELECT COUNT(*) FROM products")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            products = [
                ("Air Max 270", 150, "https://images.unsplash.com/photo-1606813903134-45c28b953b3f",
                 "https://images.unsplash.com/photo-1606813903134-45c28b953b3f",
                 "Running", "Breathable mesh with bold Air cushioning.", 25, now),
                ("Jordan Retro", 200, "https://images.unsplash.com/photo-1542291026-7eec264c27ff",
                 "https://images.unsplash.com/photo-1542291026-7eec264c27ff",
                 "Basketball", "Iconic style meets modern support.", 18, now),
                ("Blazer Mid '77", 120, "https://images.unsplash.com/photo-1595950653171-47c33e5f1d6e",
                 "https://images.unsplash.com/photo-1595950653171-47c33e5f1d6e",
                 "Casual", "Vintage vibes with everyday comfort.", 30, now),
                ("ZoomX Vaporfly", 250, "https://images.unsplash.com/photo-1519741497674-611481863552",
                 "https://images.unsplash.com/photo-1519741497674-611481863552",
                 "Racing", "Featherweight speed with propulsive foam.", 10, now),
            ]
            c.executemany("""INSERT INTO products(name,price,image,images,category,description,stock,created_at)
                             VALUES (?,?,?,?,?,?,?,?)""", products)
        # seed admin
        c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            h, s = _hash_password("admin123")
            c.execute("INSERT INTO users(username,password_hash,password_salt,is_admin,created_at) VALUES (?,?,?,?,?)",
                      ("admin", h, s, 1, now))
        # seed releases
        c.execute("SELECT COUNT(*) FROM releases")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow()
            drops = [
                ("Air Max Holiday Drop", 1, (now + timedelta(days=2)).isoformat(), "Limited colors."),
                ("Jordan Retro OG", 2, (now + timedelta(days=5, hours=4)).isoformat(), "Retro pack release."),
            ]
            c.executemany("INSERT INTO releases(title,product_id,drop_datetime,description) VALUES (?,?,?,?)", drops)
        # seed stores
        c.execute("SELECT COUNT(*) FROM stores")
        if c.fetchone()[0] == 0:
            stores = [
                ("Nike Flagship NYC","New York","650 Broadway","(212)555-0100",40.7249,-73.9940),
                ("Nike Downtown LA","Los Angeles","800 S Grand Ave","(213)555-0199",34.0407,-118.2468),
                ("Nike The Loop","Chicago","201 N State St","(312)555-0123",41.8837,-87.6278),
            ]
            c.executemany("INSERT INTO stores(name,city,address,phone,lat,lon) VALUES (?,?,?,?,?,?)", stores)
        conn.commit()

# --------------------------
# Backend functions
# --------------------------
def register_user(username: str, password: str) -> Tuple[bool,str]:
    if not username or not password:
        return False, "Username & password required."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    with get_conn() as conn:
        try:
            c = conn.cursor()
            h, s = _hash_password(password)
            now = datetime.utcnow().isoformat()
            c.execute("INSERT INTO users(username,password_hash,password_salt,is_admin,created_at) VALUES (?,?,?,?,?)",
                      (username.strip(),h,s,0,now))
            conn.commit()
            return True, "Registered successfully."
        except sqlite3.IntegrityError:
            return False, "Username already exists."
        except Exception as e:
            return False, str(e)

def authenticate(username: str, password: str) -> Tuple[bool, Optional[Dict[str,Any]]]:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username.strip(),))
        row = c.fetchone()
        if not row:
            return False, None
        h_test, _ = _hash_password(password, row["password_salt"])
        if h_test == row["password_hash"]:
            return True, dict(row)
        return False, None

def change_password(user_id:int, old_pw:str, new_pw:str) -> Tuple[bool,str]:
    if len(new_pw) < 6:
        return False, "New password too short."
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash,password_salt FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        if not row:
            return False, "User not found."
        h_old, _ = _hash_password(old_pw, row["password_salt"])
        if h_old != row["password_hash"]:
            return False, "Old password incorrect."
        h_new, s_new = _hash_password(new_pw)
        c.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (h_new,s_new,user_id))
        conn.commit()
        return True, "Password updated."

# Products
def list_products(search:str="", category:str="", price_min:float=None, price_max:float=None,
                  sort_by:str="newest", page:int=1, page_size:int=6):
    where, params = [], []
    if search:
        where.append("LOWER(name) LIKE ?")
        params.append(f"%{search.lower()}%")
    if category and category != "All":
        where.append("category = ?"); params.append(category)
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
        offset = (page-1)*page_size
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
        mn,mx = c.fetchone()
        return float(mn or 0.0), float(mx or 0.0)

def product_categories():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT COALESCE(category,'Uncategorized') FROM products")
        cats = [r[0] for r in c.fetchall()]
        cats.sort()
        return ["All"] + cats

def get_product(pid:int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM products WHERE id=?", (pid,))
        return c.fetchone()

def add_product(name,price,image,images,category,desc,stock):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO products(name,price,image,images,category,description,stock,created_at)
                     VALUES (?,?,?,?,?,?,?,?)""", (name,price,image,images,category,desc,stock,now))
        conn.commit(); return True,"Added"

def update_product(pid,name,price,image,images,category,desc,stock):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""UPDATE products SET name=?,price=?,image=?,images=?,category=?,description=?,stock=? WHERE id=?""",
                  (name,price,image,images,category,desc,stock,pid))
        conn.commit(); return True,"Updated"

def delete_product(pid):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit(); return True,"Deleted"

# Wishlist & reviews & orders
def add_wishlist(user_id, product_id):
    try:
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO wishlist(user_id, product_id, created_at) VALUES (?,?,?)",
                      (user_id, product_id, datetime.utcnow().isoformat()))
            conn.commit(); return True, "Added to wishlist."
    except Exception as e:
        return False, str(e)

def remove_wishlist(user_id, product_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?", (user_id, product_id))
        conn.commit(); return True, "Removed from wishlist."

def get_wishlist(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""SELECT p.*,
                     (SELECT COALESCE(AVG(rating),0) FROM reviews r WHERE r.product_id=p.id) AS avg_rating
                     FROM wishlist w JOIN products p ON p.id = w.product_id
                     WHERE w.user_id=?
                     ORDER BY datetime(w.created_at) DESC""", (user_id,))
        return c.fetchall()

def add_review(user_id, product_id, rating, comment):
    if rating < 1 or rating > 5:
        return False, "Rating 1-5"
    with get_conn() as conn:
        c = conn.cursor()
        now = datetime.utcnow().isoformat()
        try:
            c.execute("INSERT INTO reviews(user_id,product_id,rating,comment,created_at) VALUES (?,?,?,?,?)",
                      (user_id, product_id, rating, comment, now))
        except sqlite3.IntegrityError:
            c.execute("UPDATE reviews SET rating=?, comment=?, created_at=? WHERE user_id=? AND product_id=?",
                      (rating, comment, now, user_id, product_id))
        conn.commit(); return True, "Review saved."

def get_reviews(product_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT r.*, u.username FROM reviews r JOIN users u ON u.id = r.user_id WHERE r.product_id=? ORDER BY datetime(r.created_at) DESC", (product_id,))
        return c.fetchall()

def place_order(user_id, cart_items: List[Dict[str,Any]]):
    if not cart_items:
        return False, "Cart empty.", None
    with get_conn() as conn:
        try:
            c = conn.cursor()
            for it in cart_items:
                c.execute("SELECT stock FROM products WHERE id=?", (it["id"],))
                row = c.fetchone()
                if not row or row["stock"] < it["quantity"]:
                    return False, f"Not enough stock for {it['name']}.", None
            total = sum(it["price"]*it["quantity"] for it in cart_items)
            now = datetime.utcnow().isoformat()
            c.execute("INSERT INTO orders(user_id, created_at, total) VALUES (?,?,?)", (user_id, now, total))
            order_id = c.lastrowid
            for it in cart_items:
                c.execute("INSERT INTO order_items(order_id,product_id,quantity,price_each) VALUES (?,?,?,?)",
                          (order_id, it["id"], it["quantity"], it["price"]))
                c.execute("UPDATE products SET stock = stock - ? WHERE id=?", (it["quantity"], it["id"]))
            conn.commit()
            return True, "Order placed.", order_id
        except Exception as e:
            conn.rollback()
            return False, str(e), None

def list_orders(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY datetime(created_at) DESC", (user_id,))
        return c.fetchall()

def order_items(order_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT oi.*, p.name, p.image FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.order_id=?", (order_id,))
        return c.fetchall()

def list_releases():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT r.*, p.name as product_name FROM releases r LEFT JOIN products p ON p.id=r.product_id ORDER BY datetime(drop_datetime) ASC")
        return c.fetchall()

def search_stores(city_query=""):
    with get_conn() as conn:
        c = conn.cursor()
        if city_query:
            c.execute("SELECT * FROM stores WHERE LOWER(city) LIKE ? ORDER BY city", (f"%{city_query.lower()}%",))
        else:
            c.execute("SELECT * FROM stores ORDER BY city")
        return c.fetchall()

def admin_metrics():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users"); users = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM orders"); orders = int(c.fetchone()[0] or 0)
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders"); revenue = float(c.fetchone()[0] or 0.0)
        c.execute("SELECT COUNT(*) FROM products"); products = int(c.fetchone()[0] or 0)
        c.execute("SELECT id, name, stock FROM products WHERE stock <= 5 ORDER BY stock ASC")
        low_stock = [ {"id": int(r["id"]), "name": str(r["name"]), "stock": int(r["stock"])} for r in c.fetchall() ]
        return {"users": users, "orders": orders, "revenue": revenue, "products": products, "low_stock": low_stock}

# --------------------------
# UI (Streamlit)
# --------------------------
st.set_page_config(page_title="Nike-Style Store (A→Z)", page_icon="👟", layout="wide")
st.markdown("""<style>
.card{background:#fff;border-radius:10px;padding:12px;box-shadow:0 6px 18px rgba(0,0,0,0.06);margin-bottom:12px}
.small{color:#6b7280;font-size:13px}
.price{font-weight:800;font-size:18px}
</style>""", unsafe_allow_html=True)

# Session defaults
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []
if "view_product" not in st.session_state:
    st.session_state.view_product = None
if "hero_index" not in st.session_state:
    st.session_state.hero_index = 0
if "hero_autoplay" not in st.session_state:
    st.session_state.hero_autoplay = False

# small helpers
def logout_local():
    st.session_state.user = None
    st.session_state.cart = []
    st.session_state.view_product = None

def add_to_cart_local(pid:int, name:str, price:float, qty:int):
    for it in st.session_state.cart:
        if it["id"] == pid:
            it["quantity"] += qty
            return
    st.session_state.cart.append({"id": pid, "name": name, "price": price, "quantity": qty})

def stars(avg):
    filled = int(round(avg)) if avg is not None else 0
    return "★"*filled + "☆"*(5-filled)

# Initialize DB & seed (safe)
try:
    init_db()
    seed_if_empty()
except Exception as e:
    st.error(f"Database error when initializing: {e}")
    st.stop()

# Top bar / hero
def hero_block():
    prods, _ = list_products(page=1, page_size=10)
    imgs = [p["image"] for p in prods if p["image"]]
    titles = [p["name"] for p in prods]
    if not imgs:
        st.image("https://via.placeholder.com/1200x360?text=Shop+Now", use_column_width=True)
        return
    idx = st.session_state.hero_index % len(imgs)
    cols = st.columns([1,6,1])
    with cols[1]:
        st.image(imgs[idx], use_column_width=True)
        st.markdown(f"### {titles[idx]}")
        c1,c2,c3 = st.columns([1,1,6])
        with c1:
            if st.button("◀ Prev", key="hero_prev"):
                st.session_state.hero_index = (st.session_state.hero_index - 1) % len(imgs)
        with c2:
            if st.button("Next ▶", key="hero_next"):
                st.session_state.hero_index = (st.session_state.hero_index + 1) % len(imgs)
        with c3:
            autoplay = st.checkbox("Autoplay", value=st.session_state.hero_autoplay, key="hero_auto")
            st.session_state.hero_autoplay = autoplay
    if st.session_state.hero_autoplay:
        st.session_state.hero_index = (st.session_state.hero_index + 1) % len(imgs)
        time.sleep(0.6)
        st.experimental_rerun()

# Authentication UI
def auth_ui():
    st.header("Welcome — Login or Register")
    left,right = st.columns(2)
    with left:
        st.subheader("Login")
        lu = st.text_input("Username", key="login_username")
        lp = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="login_btn"):
            ok,user = authenticate(lu, lp)
            if ok:
                st.session_state.user = user
                st.success(f"Welcome back, {user['username']}!")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials.")
    with right:
        st.subheader("Register")
        ru = st.text_input("Choose username", key="reg_username")
        rp = st.text_input("Choose password", type="password", key="reg_password")
        if st.button("Register", key="reg_btn"):
            ok,msg = register_user(ru, rp)
            st.success(msg) if ok else st.error(msg)

# Shop UI
def shop_ui():
    st.header("Shop")
    min_p,max_p = product_min_max_price()
    c1,c2,c3,c4 = st.columns([3,1,2,1])
    with c1:
        q = st.text_input("Search products", key="search_q")
    with c2:
        cats = product_categories()
        cat = st.selectbox("Category", cats, key="cat_q")
    with c3:
        price_range = st.slider("Price range", float(min_p), float(max_p) if max_p>0 else 500.0,
                                (float(min_p), float(max_p) if max_p>0 else 500.0), key="price_q")
    with c4:
        sort_by = st.selectbox("Sort", ["newest","price_asc","price_desc","rating_desc"], key="sort_q")
    page = st.number_input("Page", min_value=1, value=1, step=1, key="page_q")
    prods, total = list_products(search=q, category=cat, price_min=price_range[0], price_max=price_range[1],
                                 sort_by=sort_by, page=page, page_size=6)
    total_pages = max(1, ceil(total/6))
    st.caption(f"Showing page {page}/{total_pages} — {total} items")
    for i in range(0, len(prods), 3):
        cols = st.columns(3)
        for j,p in enumerate(prods[i:i+3]):
            with cols[j]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.image(p["image"], use_column_width=True)
                st.markdown(f"**{p['name']}**")
                st.markdown(f"<div class='price'>${p['price']:.2f}</div>", unsafe_allow_html=True)
                st.write(stars(p["avg_rating"] or 0) + f" ({int(p['review_count'] or 0)})")
                st.caption(p["category"] or "")
                st.caption(p["description"] or "")
                qty_key = f"qty_grid_{p['id']}"
                st.number_input("Qty", min_value=1, max_value=max(1,int(p["stock"])), value=1, key=qty_key)
                if st.button("Add to Cart", key=f"add_grid_{p['id']}"):
                    qv = int(st.session_state[qty_key])
                    add_to_cart_local(p["id"], p["name"], float(p["price"]), qv)
                    st.success(f"Added {qv} × {p['name']} to cart.")
                if st.button("View", key=f"view_{p['id']}"):
                    st.session_state.view_product = p["id"]
                if st.button("Wishlist", key=f"wish_{p['id']}"):
                    ok,msg = add_wishlist(st.session_state.user["id"], p["id"])
                    st.success(msg) if ok else st.error(msg)
                st.markdown("</div>", unsafe_allow_html=True)

# Product detail
def product_detail(pid:int):
    p = get_product(pid)
    if not p:
        st.error("Product not found.")
        return
    images = []
    if p["images"]:
        images = [u.strip() for u in p["images"].split(",") if u.strip()]
    if not images and p["image"]:
        images = [p["image"]]
    colL,colR = st.columns([2,3])
    with colL:
        for img in images:
            st.image(img, use_column_width=True)
    with colR:
        st.markdown(f"## {p['name']}")
        st.markdown(f"<div class='price'>${p['price']:.2f}</div>", unsafe_allow_html=True)
        st.write(p["description"] or "")
        st.caption(f"Category: {p['category'] or 'Uncategorized'} • Stock: {p['stock']}")
        qty_key = f"qty_det_{pid}"
        st.number_input("Quantity", min_value=1, max_value=max(1,int(p["stock"])), value=1, key=qty_key)
        if st.button("Add to Cart (detail)", key=f"add_det_{pid}"):
            q = int(st.session_state[qty_key])
            add_to_cart_local(pid, p["name"], float(p["price"]), q)
            st.success("Added to cart.")
        if st.button("Add to Wishlist (detail)", key=f"wish_det_{pid}"):
            ok,msg = add_wishlist(st.session_state.user["id"], pid)
            st.success(msg) if ok else st.error(msg)
    st.divider()
    st.subheader("Reviews")
    revs = get_reviews(pid)
    if not revs:
        st.info("No reviews yet.")
    else:
        for r in revs:
            st.markdown(f"**{r['username']}** — {stars(r['rating'])}")
            if r["comment"]:
                st.caption(r["comment"])
    st.divider()
    st.subheader("Write / Update your review")
    rkey = f"rate_{pid}"; ckey = f"comm_{pid}"
    rating = st.slider("Rating",1,5,5, key=rkey)
    comment = st.text_area("Comment", key=ckey)
    if st.button("Save review", key=f"save_rev_{pid}"):
        ok,msg = add_review(st.session_state.user["id"], pid, rating, comment)
        st.success(msg) if ok else st.error(msg)

# Cart & checkout (mock)
def cart_ui():
    st.header("Cart & Checkout")
    if not st.session_state.cart:
        st.info("Cart is empty.")
        return
    total = 0.0
    for idx,it in enumerate(list(st.session_state.cart)):
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        with c1: st.write(it["name"])
        with c2:
            qk = f"cart_qty_{idx}"
            st.number_input("Qty", min_value=1, value=int(it["quantity"]), key=qk)
        with c3:
            line = it["price"] * int(st.session_state[qk])
            st.write(f"${line:.2f}")
        with c4:
            if st.button("Remove", key=f"cart_rm_{idx}"):
                st.session_state.cart.pop(idx); st.experimental_rerun()
        it["quantity"] = int(st.session_state[qk])
        total += it["price"] * it["quantity"]
    st.subheader(f"Total: ${total:.2f}")

    st.markdown("### Mock Payment")
    name = st.text_input("Name on card", key="pay_name")
    number = st.text_input("Card number (mock)", key="pay_num")
    if st.button("Place Order", key="place_order"):
        ok,msg,oid = place_order(st.session_state.user["id"], st.session_state.cart)
        if ok:
            st.success(f"{msg} (Order #{oid})")
            st.balloons()
            st.session_state.cart = []
        else:
            st.error(msg)

# Orders
def orders_ui():
    st.header("Your Orders")
    orders = list_orders(st.session_state.user["id"])
    if not orders:
        st.info("No orders yet.")
        return
    for o in orders:
        with st.expander(f"Order #{o['id']} — {o['created_at']} — ${o['total']:.2f}"):
            its = order_items(o["id"])
            for it in its:
                c1,c2 = st.columns([1,4])
                with c1: st.image(it["image"], width=80)
                with c2:
                    st.write(f"**{it['name']}**")
                    st.caption(f"Qty: {it['quantity']} — ${it['price_each']:.2f} each")

# Releases
def releases_ui():
    st.header("Release Calendar")
    rels = list_releases()
    if not rels:
        st.info("No releases scheduled.")
        return
    for r in rels:
        dt = datetime.fromisoformat(r["drop_datetime"])
        now = datetime.utcnow()
        delta = dt - now
        upcoming = delta.total_seconds() > 0
        c1,c2 = st.columns([4,1])
        with c1:
            st.markdown(f"**{r['title']}** — {r['product_name'] or 'Product'}")
            st.caption(r["description"] or "")
            st.write(f"Drop (UTC): {dt.strftime('%Y-%m-%d %H:%M')}")
        with c2:
            if upcoming:
                days = delta.days; hours = delta.seconds//3600; mins = (delta.seconds%3600)//60
                st.markdown(f"**{days}d {hours}h {mins}m**")
                if st.button("Remind (mock)", key=f"remind_{r['id']}"):
                    st.success("Reminder set (mock).")
            else:
                st.markdown("**Dropped**")

# Store locator
def stores_ui():
    st.header("Store Locator")
    q = st.text_input("Search city", key="store_q")
    res = search_stores(q)
    if not res:
        st.info("No stores found.")
        return
    for s in res:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"**{s['name']}** — {s['city']}")
        st.caption(s["address"])
        st.write(f"Phone: {s['phone']}")
        st.markdown("</div>", unsafe_allow_html=True)

# Profile
def profile_ui():
    st.header("Profile")
    st.write(f"Username: **{st.session_state.user['username']}**")
    old = st.text_input("Old password", type="password", key="chg_old")
    new = st.text_input("New password", type="password", key="chg_new")
    if st.button("Change password", key="chg_btn"):
        ok,msg = change_password(st.session_state.user["id"], old, new)
        st.success(msg) if ok else st.error(msg)
    if st.button("Logout", key="logout_profile"):
        logout_local(); st.experimental_rerun()

# Admin UI
def admin_ui():
    if not st.session_state.user.get("is_admin"):
        st.warning("Admin only.")
        return
    st.header("Admin Dashboard")
    m = admin_metrics()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Users", m["users"], key="adm_users")
    c2.metric("Orders", m["orders"], key="adm_orders")
    c3.metric("Revenue ($)", f"${m['revenue']:.2f}", key="adm_revenue")
    c4.metric("Products", m["products"], key="adm_products")
    if m["low_stock"]:
        st.subheader("Low stock")
        for it in m["low_stock"]:
            st.write(f"{it['name']}: {it['stock']} left")
    st.divider()
    st.subheader("Product CRUD")
    mode = st.selectbox("Mode", ["Add","Update","Delete"], key="admin_mode")
    products_all, _ = list_products(page=1, page_size=9999)
    current = None
    if mode in ("Update","Delete"):
        opts = {f"#{p['id']} {p['name']}": p for p in products_all}
        sel = st.selectbox("Select product", list(opts.keys()), key="admin_select")
        current = opts[sel]
    name = st.text_input("Name", value=current["name"] if current else "", key="admin_name")
    price = st.number_input("Price", min_value=0.0, value=float(current["price"]) if current else 100.0, key="admin_price")
    image = st.text_input("Image URL", value=current["image"] if current else "", key="admin_image")
    images = st.text_input("Extra images (comma)", value=current["images"] if current else "", key="admin_images")
    category = st.text_input("Category", value=current["category"] if current else "Casual", key="admin_cat")
    desc = st.text_area("Description", value=current["description"] if current else "", key="admin_desc")
    stock = st.number_input("Stock", min_value=0, value=int(current["stock"]) if current else 10, key="admin_stock")
    if st.button("Submit", key="admin_submit"):
        if mode=="Add":
            ok,msg = add_product(name, price, image, images, category, desc, stock)
            st.success(msg) if ok else st.error(msg)
        elif mode=="Update":
            ok,msg = update_product(current["id"], name, price, image, images, category, desc, stock)
            st.success(msg) if ok else st.error(msg)
        elif mode=="Delete":
            ok,msg = delete_product(current["id"])
            st.success(msg) if ok else st.error(msg)

# Router
def main():
    st.title("Nike-Style Store (A → Z)")
    hero_block()
    if not st.session_state.user:
        auth_ui(); return
    # nav
    tabs = ["Shop","Releases","Stores","Cart","Orders","Profile"]
    if st.session_state.user.get("is_admin"):
        tabs.append("Admin")
    choice = st.sidebar.radio("Navigate", tabs, index=0, key="nav_main")
    st.sidebar.markdown("---")
    st.sidebar.write(f"Signed in: **{st.session_state.user['username']}**")
    st.sidebar.write(f"Cart: {sum(it['quantity'] for it in st.session_state.cart)} items")
    if st.sidebar.button("Logout", key="logout_side"):
        logout_local(); st.experimental_rerun()
    # view product takes precedence
    if st.session_state.view_product:
        product_detail(st.session_state.view_product)
        if st.button("Back to shop", key="back_to_shop"):
            st.session_state.view_product = None
        return
    if choice == "Shop": shop_ui()
    elif choice == "Releases": releases_ui()
    elif choice == "Stores": stores_ui()
    elif choice == "Cart": cart_ui()
    elif choice == "Orders": orders_ui()
    elif choice == "Profile": profile_ui()
    elif choice == "Admin": admin_ui()

# Run app
main()
