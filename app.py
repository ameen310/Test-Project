# app.py
import streamlit as st
import sqlite3
from sqlite3 import Connection

# -----------------------
# Database Utilities
# -----------------------
DB_PATH = "store.db"

def get_conn() -> Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        # Users table
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0
        )
        """)
        # Products table
        c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            image TEXT,
            images TEXT,
            category TEXT,
            description TEXT,
            stock INTEGER
        )
        """)
        # Orders table
        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            total REAL
        )
        """)
        conn.commit()

# -----------------------
# Authentication
# -----------------------
def create_user(username, password, is_admin=0):
    try:
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users(username,password,is_admin) VALUES (?,?,?)", (username,password,is_admin))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        if user:
            return dict(user)
        return None

# -----------------------
# Product CRUD
# -----------------------
def add_product(name, price, image, images, category, description, stock):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO products(name,price,image,images,category,description,stock) VALUES (?,?,?,?,?,?,?)",
                  (name, price, image, images, category, description, stock))
        conn.commit()
        return True, "Product added!"

def update_product(pid, name, price, image, images, category, description, stock):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""UPDATE products SET name=?,price=?,image=?,images=?,category=?,description=?,stock=? WHERE id=?""",
                  (name, price, image, images, category, description, stock, pid))
        conn.commit()
        return True, "Product updated!"

def delete_product(pid):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
        return True, "Product deleted!"

def list_products():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM products")
        return [dict(p) for p in c.fetchall()]

# -----------------------
# Admin Metrics
# -----------------------
def admin_metrics():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        users = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM orders")
        orders = int(c.fetchone()[0] or 0)
        c.execute("SELECT COALESCE(SUM(total),0) FROM orders")
        revenue = float(c.fetchone()[0] or 0.0)
        c.execute("SELECT COUNT(*) FROM products")
        products = int(c.fetchone()[0] or 0)
        # low stock products
        c.execute("SELECT id,name,stock FROM products WHERE stock<=5 ORDER BY stock ASC")
        low_stock = [dict(r) for r in c.fetchall()]
        return {
            "users": users,
            "orders": orders,
            "revenue": revenue,
            "products": products,
            "low_stock": low_stock
        }

# -----------------------
# Admin UI
# -----------------------
def admin_ui():
    st.header("Admin Dashboard")
    metrics = admin_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users", metrics["users"], key="adm_users")
    c2.metric("Orders", metrics["orders"], key="adm_orders")
    c3.metric("Revenue ($)", f"${metrics['revenue']:.2f}", key="adm_revenue")
    c4.metric("Products", metrics["products"], key="adm_products")
    if metrics["low_stock"]:
        st.subheader("Low Stock Products")
        for p in metrics["low_stock"]:
            st.write(f"{p['name']}: {p['stock']} left")

    st.divider()
    st.subheader("Manage Products")
    products = list_products()
    mode = st.selectbox("Mode", ["Add", "Update", "Delete"], key="mode_key")
    current = None
    if mode in ("Update","Delete"):
        options = {f"#{p['id']} {p['name']}": p for p in products}
        if options:
            sel = st.selectbox("Select Product", list(options.keys()), key="select_key")
            current = options[sel]

    name = st.text_input("Name", value=(current["name"] if current else ""), key="name_key")
    price = st.number_input("Price", min_value=0.0, value=(float(current["price"]) if current else 100.0), key="price_key")
    image = st.text_input("Image URL", value=(current["image"] if current else ""), key="image_key")
    images = st.text_input("Extra Images (comma)", value=(current["images"] if current else ""), key="images_key")
    category = st.text_input("Category", value=(current["category"] if current else "Casual"), key="cat_key")
    desc = st.text_area("Description", value=(current["description"] if current else ""), key="desc_key")
    stock = st.number_input("Stock", min_value=0, value=(int(current["stock"]) if current else 10), key="stock_key")

    if st.button("Submit", key="submit_key"):
        if mode=="Add":
            add_product(name, price, image, images, category, desc, stock)
            st.success("Product added!")
        elif mode=="Update" and current:
            update_product(current["id"], name, price, image, images, category, desc, stock)
            st.success("Product updated!")
        elif mode=="Delete" and current:
            delete_product(current["id"])
            st.success("Product deleted!")

# -----------------------
# Main App
# -----------------------
def main():
    st.title("E-Commerce Store")
    init_db()

    # Sidebar login
    if "user" not in st.session_state:
        st.session_state.user = None

    if not st.session_state.user:
        st.sidebar.subheader("Login")
        username = st.sidebar.text_input("Username", key="login_user")
        password = st.sidebar.text_input("Password", type="password", key="login_pass")
        if st.sidebar.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Welcome {user['username']}!")
            else:
                st.error("Invalid credentials")

        st.sidebar.markdown("---")
        st.sidebar.subheader("New User?")
        new_user = st.sidebar.text_input("Username", key="reg_user")
        new_pass = st.sidebar.text_input("Password", type="password", key="reg_pass")
        if st.sidebar.button("Register"):
            if create_user(new_user, new_pass):
                st.success("User registered! Login now.")
            else:
                st.error("Username taken.")
    else:
        st.sidebar.success(f"Logged in as {st.session_state.user['username']}")
        if st.sidebar.button("Logout"):
            st.session_state.user = None
            st.experimental_rerun()

        # Tabs for navigation
        tabs = st.tabs(["Dashboard","Products","Admin"])
        with tabs[0]:
            st.subheader("Dashboard")
            st.write("Welcome to your dashboard!")
        with tabs[1]:
            st.subheader("All Products")
            for p in list_products():
                st.image(p["image"], width=150)
                st.write(f"**{p['name']}** - ${p['price']}")
                st.write(f"{p['description']}")
        with tabs[2]:
            if st.session_state.user["is_admin"]:
                admin_ui()
            else:
                st.warning("Admins only.")

if __name__ == "__main__":
    main()
