# app.py
"""
Single-file Nike-style Streamlit app (A → Z).
Features:
- SQLite backend (auto-init + seeding)
- Auth (register/login) with hashed passwords
- Shop: hero carousel, product grid, filters, pagination, product detail
- Wishlist, Reviews (1-5), Ratings
- Release calendar with countdown
- Store locator (sample stores)
- Cart & Checkout with mock payment form -> orders
- Admin dashboard: product CRUD + metrics
- All widget keys unique to avoid DuplicateElementId
"""

import streamlit as st
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib, os, time, csv, io
from math import ceil
from typing import Any, Dict, List, Optional, Tuple

# ---------------- CONFIG ----------------
DB_FILE = "nike_store_full.db"
PAGE_SIZE = 6

# ---------------- HELPERS & DB ----------------
def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = os.urandom(16).hex()
    return hashlib.sha256((salt + password).encode()).hexdigest(), salt

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
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        # products
        c.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT,
            images TEXT,           -- comma-separated image URLs (optional)
            category TEXT,
            description TEXT,
            stock INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        # reviews
        c.execute("""CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, product_id)
        )""")
        # wishlist
        c.execute("""CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, product_id)
        )""")
        # orders + items
        c.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_each REAL NOT NULL
        )""")
        # release calendar
        c.execute("""CREATE TABLE IF NOT EXISTS releases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            product_id INTEGER,
            drop_datetime TEXT NOT NULL,
            description TEXT
        )""")
        # stores
        c.execute("""CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, city TEXT, address TEXT, phone TEXT, lat REAL, lon REAL
        )""")
        conn.commit()

def seed_data():
    with get_conn() as conn:
        c = conn.cursor()
        # products
        c.execute("SELECT COUNT(*) FROM products")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            products = [
                ("Air Max 270", 150, "https://images.unsplash.com/photo-1606813903134-45c28b953b3f",
                 "https://images.unsplash.com/photo-1606813903134-45c28b953b3f,https://images.unsplash.com/photo-1552345382-6e9b8d6f6b2b",
                 "Running", "Breathable mesh with bold Air cushioning.", 25, now),
                ("Jordan Retro", 200, "https://images.unsplash.com/photo-1542291026-7eec264c27ff",
                 "https://images.unsplash.com/photo-1542291026-7eec264c27ff", "Basketball", "Iconic style meets modern support.", 18, now),
                ("Blazer Mid '77", 120, "https://images.unsplash.com/photo-1595950653171-47c33e5f1d6e",
                 "https://images.unsplash.com/photo-1595950653171-47c33e5f1d6e", "Casual", "Vintage vibes with everyday comfort.", 30, now),
                ("ZoomX Vaporfly", 250, "https://images.unsplash.com/photo-1519741497674-611481863552",
                 "https://images.unsplash.com/photo-1519741497674-611481863552", "Racing", "Featherweight speed and propulsive foam.", 10, now),
            ]
            c.executemany("""INSERT INTO products(name, price, image, images, category, description, stock, created_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", products)
        # admin user
        c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            h, s = _hash_password("admin123")
            c.execute("INSERT INTO users(username,password_hash,password_salt,is_admin,created_at) VALUES (?,?,?,?,?)",
                      ("admin", h, s, 1, now))
        # releases sample
        c.execute("SELECT COUNT(*) FROM releases")
        if c.fetchone()[0] == 0:
            now = datetime.utcnow()
            drops = [
                ("Air Max Holiday Drop", 1, (now + timedelta(days=2)).isoformat(), "Limited colors."),
                ("Jordan Retro OG", 2, (now + timedelta(days=5, hours=4)).isoformat(), "Retro pack release."),
            ]
            c.executemany("INSERT INTO releases(title,product_id,drop_datetime,description) VALUES (?,?,?,?)", drops)
        # stores sample
        c.execute("SELECT COUNT(*) FROM stores")
        if c.fetchone()[0] == 0:
            stores = [
                ("Nike Flagship NYC","New York","650 Broadway","(212)555-0100",40.7249,-73.9940),
                ("Nike Downtown LA","Los Angeles","800 S Grand Ave","(213)555-0199",34.0407,-118.2468),
                ("Nike The Loop","Chicago","201 N State St","(312)555-0123",41.8837,-87.6278),
            ]
            c.executemany("INSERT INTO stores(name,city,address,phone,lat,lon) VALUES (?,?,?,?,?,?)", stores)
        conn.commit()

# Basic DB ops (users/products/reviews/wishlist/orders/releases/stores)
def register_user(username: str, password: str) -> Tuple[bool,str]:
    if not username or not password: return False, "Username & password required."
    if len(username) < 3: return False, "Username must be >=3 chars."
    if len(password) < 6: return False, "Password must be >=6 chars."
    try:
        with get_conn() as conn:
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
        if not row: return False, None
        h_test, _ = _hash_password(password, row["password_salt"])
        if h_test == row["password_hash"]:
            return True, dict(row)
        return False, None

def change_password(user_id:int, old_pw:str, new_pw:str) -> Tuple[bool,str]:
    if len(new_pw) < 6: return False, "Password must be >=6 chars."
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash,password_salt FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        if not row: return False, "User not found."
        h_old, _ = _hash_password(old_pw, row["password_salt"])
        if h_old != row["password_hash"]: return False, "Old password incorrect."
        h_new, s_new = _hash_password(new_pw)
        c.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (h_new,s_new,user_id))
        conn.commit()
        return True, "Password updated."

# Product listing + helpers
def list_products(search:str="", category:str="", price_min:float=None, price_max:float=None,
                  sort_by:str="newest", page:int=1, page_size:int=PAGE_SIZE):
    where, params = [], []
    if search: where.append("LOWER(name) LIKE ?"); params.append(f"%{search.lower()}%")
    if category and category != "All": where.append("category = ?"); params.append(category)
    if price_min is not None: where.append("price >= ?"); params.append(price_min)
    if price_max is not None: where.append("price <= ?"); params.append(price_max)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    if sort_by == "price_asc": order_sql = "ORDER BY price ASC"
    elif sort_by == "price_desc": order_sql = "ORDER BY price DESC"
    elif sort_by == "rating_desc": order_sql = "ORDER BY (SELECT COALESCE(AVG(rating),0) FROM reviews r WHERE r.product_id=products.id) DESC"
    else: order_sql = "ORDER BY datetime(created_at) DESC"
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

# wishlist/reviews/orders/releases/stores
def add_wishlist(user_id, product_id):
    try:
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO wishlist(user_id,product_id,created_at) VALUES (?,?,?)",
                      (user_id, product_id, datetime.utcnow().isoformat()))
            conn.commit(); return True, "Added to wishlist"
    except Exception as e: return False,str(e)

def remove_wishlist(user_id, product_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?", (user_id, product_id))
        conn.commit(); return True, "Removed from wishlist"

def get_wishlist(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""SELECT p.*,(SELECT COALESCE(AVG(rating),0) FROM reviews r WHERE r.product_id=p.id) AS avg_rating
                     FROM wishlist w JOIN products p ON p.id=w.product_id WHERE w.user_id=? ORDER BY datetime(w.created_at) DESC""", (user_id,))
        return c.fetchall()

def add_review(user_id, product_id, rating, comment):
    if rating<1 or rating>5: return False,"Rating 1-5"
    with get_conn() as conn:
        c=conn.cursor(); now=datetime.utcnow().isoformat()
        try:
            c.execute("INSERT INTO reviews(user_id,product_id,rating,comment,created_at) VALUES (?,?,?,?,?)",
                      (user_id,product_id,rating,comment,now))
        except sqlite3.IntegrityError:
            c.execute("UPDATE reviews SET rating=?,comment=?,created_at=? WHERE user_id=? AND product_id=?",
                      (rating,comment,now,user_id,product_id))
        conn.commit(); return True,"Review saved"

def get_reviews(product_id):
    with get_conn() as conn:
        c=conn.cursor()
        c.execute("SELECT r.*, u.username FROM reviews r JOIN users u ON u.id=r.user_id WHERE r.product_id=? ORDER BY datetime(r.created_at) DESC", (product_id,))
        return c.fetchall()

def place_order(user_id, cart_items):
    if not cart_items: return False,"Cart empty",None
    with get_conn() as conn:
        try:
            c=conn.cursor()
            # stock check
            for it in cart_items:
                c.execute("SELECT stock FROM products WHERE id=?", (it["id"],))
                row = c.fetchone()
                if not row or row["stock"] < it["quantity"]:
                    return False, f"Not enough stock for {it['name']}", None
            total = sum(it["price"]*it["quantity"] for it in cart_items)
            now = datetime.utcnow().isoformat()
            c.execute("INSERT INTO orders(user_id,created_at,total) VALUES (?,?,?)", (user_id,now,total))
            oid = c.lastrowid
            for it in cart_items:
                c.execute("INSERT INTO order_items(order_id,product_id,quantity,price_each) VALUES (?,?,?,?)",
                          (oid,it["id"],it["quantity"],it["price"]))
                c.execute("UPDATE products SET stock=stock-? WHERE id=?", (it["quantity"],it["id"]))
            conn.commit(); return True,"Order placed", oid
        except Exception as e:
            conn.rollback(); return False,str(e),None

def list_orders(user_id):
    with get_conn() as conn:
        c=conn.cursor()
        c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY datetime(created_at) DESC", (user_id,))
        return c.fetchall()

def order_items(order_id):
    with get_conn() as conn:
        c=conn.cursor()
        c.execute("SELECT oi.*, p.name, p.image FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?", (order_id,))
        return c.fetchall()

def add_release(title,product_id,drop_dt,description):
    with get_conn() as conn:
        c=conn.cursor()
        c.execute("INSERT INTO releases(title,product_id,drop_datetime,description) VALUES (?,?,?,?)", (title,product_id,drop_dt,description))
        conn.commit(); return True,"Added"

def list_releases():
    with get_conn() as conn:
        c=conn.cursor()
        c.execute("SELECT r.*, p.name as product_name FROM releases r LEFT JOIN products p ON p.id=r.product_id ORDER BY datetime(drop_datetime) ASC")
        return c.fetchall()

def add_store(name,city,address,phone,lat,lon):
    with get_conn() as conn:
        c=conn.cursor()
        c.execute("INSERT INTO stores(name,city,address,phone,lat,lon) VALUES (?,?,?,?,?,?)", (name,city,address,phone,lat,lon))
        conn.commit(); return True,"Added"

def search_stores(city_query=""):
    with get_conn() as conn:
        c=conn.cursor()
        if city_query:
            c.execute("SELECT * FROM stores WHERE LOWER(city) LIKE ? ORDER BY city", (f"%{city_query.lower()}%",))
        else:
            c.execute("SELECT * FROM stores ORDER BY city")
        return c.fetchall()

def admin_metrics():
    with get_conn() as conn:
        c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM users"); users=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM orders"); orders=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders"); revenue=c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM products"); products=c.fetchone()[0]
        c.execute("SELECT id,name,stock FROM products WHERE stock<=5 ORDER BY stock ASC"); low = c.fetchall()
        return {"users":users,"orders":orders,"revenue":revenue,"products":products,"low_stock":low}

# Initialize DB and seed
init_db(); seed_data()

# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="Nike-Style Store (full)", page_icon="👟", layout="wide")

# small CSS for polish
st.markdown("""
<style>
.card { background:#fff; border-radius:10px; padding:12px; box-shadow:0 6px 18px rgba(0,0,0,0.06); margin-bottom:12px;}
.header { display:flex; align-items:center; justify-content:space-between; }
.hero { border-radius:12px; overflow:hidden; margin-bottom:18px; }
.hero img { width:100%; height:360px; object-fit:cover; border-radius:8px;}
.badge { display:inline-block; padding:6px 10px; border-radius:999px; background:#111; color:#fff; font-weight:700;}
.price { font-weight:800; font-size:18px; }
.muted { color:#6b7280; }
.small { font-size:13px; color:#6b7280;}
</style>
""", unsafe_allow_html=True)

# session defaults & UI helpers
if "user" not in st.session_state: st.session_state.user = None
if "cart" not in st.session_state: st.session_state.cart = []  # list of dicts {id,name,price,quantity}
if "view_product" not in st.session_state: st.session_state.view_product = None
if "hero_index" not in st.session_state: st.session_state.hero_index = 0
if "hero_autoplay" not in st.session_state: st.session_state.hero_autoplay = False

def logout():
    st.session_state.user = None
    st.session_state.cart = []
    st.session_state.view_product = None

def add_to_cart(pid,name,price,qty):
    for it in st.session_state.cart:
        if it["id"] == pid:
            it["quantity"] += qty; return
    st.session_state.cart.append({"id":pid,"name":name,"price":price,"quantity":qty})

def stars(avg):
    filled = int(round(avg))
    return "★"*filled + "☆"*(5-filled)

# ---------- HERO carousel ----------
def hero_block():
    # simple hero images from top products
    products, _ = list_products(page=1,page_size=10)
    hero_images = [p["image"] for p in products]
    hero_titles = [p["name"] for p in products]
    n = len(hero_images)
    if n == 0:
        st.markdown("<div class='hero'><img src='https://via.placeholder.com/1400x360?text=Shop' /></div>", unsafe_allow_html=True)
        return
    idx = st.session_state.hero_index % n
    col1, col2, col3 = st.columns([1,8,1])
    with col2:
        st.markdown(f"<div class='hero'><img src='{hero_images[idx]}'></div>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='margin-top:6px'>{hero_titles[idx]}</h2>")
        c1,c2,c3 = st.columns([1,1,6])
        with c1:
            if st.button("◀ Prev", key=f"hero_prev"):
                st.session_state.hero_index = (st.session_state.hero_index - 1) % n
        with c2:
            if st.button("Next ▶", key=f"hero_next"):
                st.session_state.hero_index = (st.session_state.hero_index + 1) % n
        with c3:
            autoplay = st.checkbox("Autoplay", value=st.session_state.hero_autoplay, key="hero_autoplay_key")
            st.session_state.hero_autoplay = autoplay
    # autoplay (non-blocking approach — set to advance on rerun)
    if st.session_state.hero_autoplay:
        # advance index but avoid blocking — we trigger a rerun after tiny sleep
        st.session_state.hero_index = (st.session_state.hero_index + 1) % n
        time.sleep(0.6)
        st.experimental_rerun()

# ---------- Top navigation / header ----------
def top_bar():
    col_left, col_mid, col_right = st.columns([1,3,1])
    with col_left:
        st.markdown("<h1 style='margin:0'>Nike-Style Store</h1>", unsafe_allow_html=True)
    with col_mid:
        st.markdown("<div class='small muted'>Minimal demo — Streamlit + SQLite</div>", unsafe_allow_html=True)
    with col_right:
        if st.session_state.user:
            st.markdown(f"<div style='text-align:right'>Hello, <strong>{st.session_state.user['username']}</strong></div>", unsafe_allow_html=True)

# ---------- Authentication UI ----------
def auth_ui():
    st.header("Welcome — Login or Register")
    left,right = st.columns(2)
    with left:
        st.subheader("Login")
        lu = st.text_input("Username", key="login_user")
        lp = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", key="btn_login"):
            ok, user = authenticate(lu, lp)
            if ok:
                st.session_state.user = user
                st.success("Logged in.")
            else:
                st.error("Invalid credentials.")
    with right:
        st.subheader("Register")
        ru = st.text_input("New username", key="reg_user")
        rp = st.text_input("New password", type="password", key="reg_pass")
        if st.button("Register", key="btn_register"):
            ok,msg = register_user(ru,rp)
            if ok: st.success(msg)
            else: st.error(msg)

# ---------- Shop list & product detail ----------
def shop_ui():
    st.header("Shop")
    # filters & search
    min_p, max_p = product_min_max_price()
    c1,c2,c3,c4 = st.columns([3,1,2,1])
    with c1:
        search = st.text_input("Search", key="search_q")
    with c2:
        cats = product_categories()
        cat = st.selectbox("Category", cats, key="cat_sel")
    with c3:
        price_range = st.slider("Price", float(min_p), float(max_p) if max_p>0 else 500.0,
                                (float(min_p), float(max_p) if max_p>0 else 500.0), key="price_rng")
    with c4:
        sort_by = st.selectbox("Sort", ["newest","price_asc","price_desc","rating_desc"], key="sort_sel")
    page = st.number_input("Page", min_value=1, value=1, step=1, key="page_num")
    prods, total = list_products(search=search, category=cat, price_min=price_range[0], price_max=price_range[1],
                                 sort_by=sort_by, page=page, page_size=PAGE_SIZE)
    total_pages = max(1, ceil(total/PAGE_SIZE))
    st.caption(f"Page {page}/{total_pages} — {total} results")

    # product grid
    for i in range(0, len(prods), 3):
        cols = st.columns(3)
        for j,p in enumerate(prods[i:i+3]):
            with cols[j]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                # image
                st.image(p["image"], use_column_width=True)
                st.markdown(f"**{p['name']}**")
                st.markdown(f"<div class='price'>${p['price']:.2f}</div>", unsafe_allow_html=True)
                st.write(stars(p["avg_rating"] or 0) + f"  ({int(p['review_count'] or 0)})")
                st.caption(p["category"] or "")
                st.caption(p["description"] or "")
                qty_key = f"qty_grid_{p['id']}"
                st.number_input("Qty", min_value=1, max_value=max(1,int(p["stock"])), value=1, key=qty_key)
                if st.button("Add to Cart", key=f"add_grid_{p['id']}"):
                    q = int(st.session_state[qty_key])
                    add_to_cart(p["id"], p["name"], float(p["price"]), q)
                    st.success(f"Added {q} × {p['name']} to cart.")
                if st.button("View Product", key=f"view_grid_{p['id']}"):
                    st.session_state.view_product = p["id"]
                st.markdown("</div>", unsafe_allow_html=True)

def product_detail_ui(pid:int):
    p = get_product(pid)
    if not p:
        st.error("Product not found.")
        st.button("Back to shop", key=f"back_to_shop_{pid}", on_click=lambda: st.session_state.update({"view_product":None}))
        return
    # layout: left images, right details
    colL,colR = st.columns([2,3])
    with colL:
        # show main + additional images
        images = []
        if p["images"]:
            images = [u.strip() for u in p["images"].split(",") if u.strip()]
        if not images and p["image"]:
            images = [p["image"]]
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
            add_to_cart(pid,p["name"],float(p["price"]),q)
            st.success("Added to cart.")
        if st.button("Add to Wishlist", key=f"wish_det_{pid}"):
            ok,msg = add_wishlist(st.session_state.user["id"], pid)
            st.success(msg) if ok else st.error(msg)
    st.divider()
    st.subheader("Reviews")
    revs = get_reviews(pid)
    if not revs:
        st.info("No reviews yet. Be the first!")
    else:
        for r in revs:
            st.markdown(f"**{r['username']}** — {stars(r['rating'])}")
            if r["comment"]:
                st.caption(r["comment"])
    st.divider()
    # review form
    st.subheader("Write / Update your review")
    rate_key = f"rate_{pid}"
    comment_key = f"comment_{pid}"
    rating = st.slider("Rating",1,5,5, key=rate_key)
    comment = st.text_area("Comment", key=comment_key)
    if st.button("Submit Review", key=f"submit_rev_{pid}"):
        ok,msg = add_review(st.session_state.user["id"], pid, rating, comment)
        st.success(msg) if ok else st.error(msg)

# ---------- Releases UI ----------
def releases_ui():
    st.header("Release Calendar")
    rels = list_releases()
    if not rels:
        st.info("No scheduled releases.")
        return
    for r in rels:
        dt = datetime.fromisoformat(r["drop_datetime"])
        now = datetime.utcnow()
        delta = dt - now
        days = delta.days
        hours = delta.seconds//3600
        minutes = (delta.seconds%3600)//60
        upcoming = delta.total_seconds() > 0
        colL,colR = st.columns([3,1])
        with colL:
            st.markdown(f"**{r['title']}** — {r['product_name'] or 'Product'}")
            st.caption(r["description"] or "")
            st.write(f"Drop time (UTC): {dt.strftime('%Y-%m-%d %H:%M')}")
        with colR:
            if upcoming:
                st.markdown(f"**{days}d {hours}h {minutes}m**")
                if st.button("Remind me", key=f"remind_{r['id']}"):
                    st.success("Reminder set (mock).")
            else:
                st.markdown("**Dropped**")

# ---------- Store locator UI ----------
def stores_ui():
    st.header("Store Locator")
    q = st.text_input("Search city", key="store_search")
    results = search_stores(q)
    if not results:
        st.info("No stores found.")
        return
    for s in results:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"**{s['name']}** — {s['city']}")
        st.caption(s["address"])
        st.write(f"Phone: {s['phone']}")
        st.markdown("</div>", unsafe_allow_html=True)

# ---------- Cart & checkout (mock payment) ----------
def cart_ui():
    st.header("Cart & Checkout")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return
    total = sum(it["price"]*it["quantity"] for it in st.session_state.cart)
    for idx,it in enumerate(list(st.session_state.cart)):
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        with c1: st.write(it["name"])
        with c2:
            k = f"cart_qty_{idx}"
            st.number_input("Qty", min_value=1, value=int(it["quantity"]), key=k)
        with c3:
            line = it["price"] * int(st.session_state[f"cart_qty_{idx}"])
            st.write(f"${line:.2f}")
        with c4:
            if st.button("Remove", key=f"cart_rm_{idx}"):
                st.session_state.cart.pop(idx)
                st.experimental_rerun()
        it["quantity"] = int(st.session_state[f"cart_qty_{idx}"])
    st.subheader(f"Total: ${total:.2f}")
    # Mock payment form
    st.markdown("### Payment (mock)")
    name = st.text_input("Cardholder name", key="pay_name")
    number = st.text_input("Card number (mock)", key="pay_number")
    exp = st.text_input("Expiry (MM/YY)", key="pay_exp")
    cvv = st.text_input("CVV", key="pay_cvv")
    if st.button("Pay & Place Order", key="pay_place"):
        # in production, integrate Stripe / payment gateway server-side
        ok,msg,oid = place_order(st.session_state.user["id"], st.session_state.cart)
        if ok:
            st.success(f"{msg} Order #{oid}")
            st.balloons()
            st.session_state.cart = []
        else:
            st.error(msg)

# ---------- Orders UI ----------
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

# ---------- Profile UI ----------
def profile_ui():
    st.header("Profile")
    st.write(f"Username: **{st.session_state.user['username']}**")
    st.subheader("Change password")
    old = st.text_input("Old password", type="password", key="chg_old")
    new = st.text_input("New password", type="password", key="chg_new")
    if st.button("Change password", key="chg_btn"):
        ok,msg = change_password(st.session_state.user["id"], old, new)
        st.success(msg) if ok else st.error(msg)
    if st.button("Logout", key="logout_btn"):
        logout(); st.experimental_rerun()

# ---------- Admin UI ----------
def admin_ui():
    if not st.session_state.user.get("is_admin"):
        st.warning("Admins only.")
        return
    st.header("Admin Dashboard")
    m = admin_metrics()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Users", m["users"], key="adm_users")
    c2.metric("Orders", m["orders"], key="adm_orders")
    c3.metric("Revenue ($)", float(m["revenue"]), key="adm_revenue")
    c4.metric("Products", m["products"], key="adm_products")
    if m["low_stock"]:
        st.subheader("Low stock")
        for r in m["low_stock"]:
            st.write(f"{r['name']}: {r['stock']}")
    st.divider()
    st.subheader("Product CRUD")
    mode = st.selectbox("Mode", ["Add","Update","Delete"], key="admin_mode")
    products_all, _ = list_products(page=1, page_size=9999)
    current = None
    if mode in ("Update","Delete"):
        opts = {f"#{p['id']} {p['name']}": p for p in products_all}
        sel = st.selectbox("Select", list(opts.keys()), key="admin_select")
        current = opts[sel]
    name = st.text_input("Name", value=current["name"] if current else "", key="admin_name")
    price = st.number_input("Price", value=float(current["price"]) if current else 100.0, key="admin_price")
    image = st.text_input("Image URL", value=current["image"] if current else "", key="admin_image")
    images = st.text_input("Extra images (comma)", value=current["images"] if current else "", key="admin_images")
    category = st.text_input("Category", value=current["category"] if current else "Casual", key="admin_cat")
    desc = st.text_area("Description", value=current["description"] if current else "", key="admin_desc")
    stock = st.number_input("Stock", min_value=0, value=int(current["stock"]) if current else 10, key="admin_stock")
    if st.button("Submit", key="admin_submit"):
        if mode=="Add":
            ok,msg = add_product(name,price,image,images,category,desc,stock)
            st.success(msg) if ok else st.error(msg)
        elif mode=="Update":
            ok,msg = update_product(current["id"],name,price,image,images,category,desc,stock)
            st.success(msg) if ok else st.error(msg)
        else:
            ok,msg = delete_product(current["id"])
            st.success(msg) if ok else st.error(msg)

# ---------- MAIN ROUTER ----------
def main():
    top_bar()
    hero_block()
    if not st.session_state.user:
        auth_ui()
        st.stop()
    # navigation
    tabs = ["Shop","Releases","Stores","Cart","Orders","Profile"]
    if st.session_state.user.get("is_admin"): tabs.append("Admin")
    choice = st.sidebar.radio("Navigate", tabs, index=0, key="main_nav")
    # view product detail if set
    if st.session_state.view_product:
        if choice != "Shop":
            # allow viewing detail from anywhere
            product_detail_ui(st.session_state.view_product)
        else:
            product_detail_ui(st.session_state.view_product)
        if st.button("Back to shop", key="back_btn"):
            st.session_state.view_product = None
        return
    # route pages
    if choice == "Shop": shop_ui()
    elif choice == "Releases": releases_ui()
    elif choice == "Stores": stores_ui()
    elif choice == "Cart": cart_ui()
    elif choice == "Orders": orders_ui()
    elif choice == "Profile": profile_ui()
    elif choice == "Admin": admin_ui()

# run
main()
