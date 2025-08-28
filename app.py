# app.py
import streamlit as st
from math import ceil

from database import (
    register_user, authenticate, change_password,
    list_products, product_min_max_price, product_categories,
    add_product, update_product, delete_product,
    add_wishlist, remove_wishlist, get_wishlist,
    add_review, get_reviews,
    place_order, list_orders, order_items,
    admin_metrics
)

st.set_page_config(page_title="Nike-Style Store", page_icon="👟", layout="wide")

# --- small CSS for nicer look ---
st.markdown("""
<style>
.block-container { padding-top: 1rem; }
.card { background: #fff; border-radius:12px; padding:12px; box-shadow:0 6px 18px rgba(0,0,0,0.06); margin-bottom:12px; }
.product-img { border-radius:8px; }
</style>
""", unsafe_allow_html=True)

# --- session state defaults ---
if "user" not in st.session_state: st.session_state.user = None
if "cart" not in st.session_state: st.session_state.cart = []
if "active_review_pid" not in st.session_state: st.session_state.active_review_pid = None

# ---------- helpers ----------
def logout():
    st.session_state.user = None
    st.session_state.cart = []
    st.session_state.active_review_pid = None

def add_to_cart(product_id: int, name: str, price: float, qty: int):
    # merge
    for it in st.session_state.cart:
        if it["id"] == product_id:
            it["quantity"] += qty
            return
    st.session_state.cart.append({"id": product_id, "name": name, "price": price, "quantity": qty})

def stars(r: float) -> str:
    filled = int(round(r))
    return "★"*filled + "☆"*(5-filled)

# ---------- Auth UI ----------
def auth_ui():
    st.title("👟 Nike-Style Store — Login / Register")
    left, right = st.columns(2)
    with left:
        st.subheader("Login")
        lu = st.text_input("Username", key="login_username")
        lp = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="btn_login"):
            ok, user = authenticate(lu, lp)
            if ok:
                st.session_state.user = user
                st.success(f"Welcome back, {user['username']}!")
            else:
                st.error("Invalid username or password.")
    with right:
        st.subheader("Register")
        ru = st.text_input("New username", key="reg_username")
        rp = st.text_input("New password", type="password", key="reg_password")
        if st.button("Create account", key="btn_register"):
            ok, msg = register_user(ru, rp)
            if ok:
                st.success(msg + " Now please login.")
            else:
                st.error(msg)

# ---------- Shop tab ----------
def shop_tab():
    st.header("Shop")
    min_p, max_p = product_min_max_price()
    c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
    with c1:
        search = st.text_input("Search products", key="search_input")
    with c2:
        cats = product_categories()
        cat = st.selectbox("Category", cats, key="category_select")
    with c3:
        price_range = st.slider("Price range", float(min_p), float(max_p) if max_p>0 else 500.0,
                                (float(min_p), float(max_p) if max_p>0 else 500.0), key="price_slider")
    with c4:
        sort_by = st.selectbox("Sort", ["newest", "price_asc", "price_desc", "rating_desc"], key="sort_select")

    page_size = 6
    page = st.number_input("Page", min_value=1, value=1, step=1, key="page_input")
    products, total = list_products(search=search, category=cat, price_min=price_range[0],
                                    price_max=price_range[1], sort_by=sort_by, page=page, page_size=page_size)
    total_pages = max(1, ceil(total / page_size))
    st.caption(f"Showing page {page}/{total_pages} — {total} items")

    # grid
    for i in range(0, len(products), 3):
        cols = st.columns(3)
        for j, p in enumerate(products[i:i+3]):
            with cols[j]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.image(p["image"], use_column_width=True, output_format="auto")
                st.markdown(f"**{p['name']}**")
                st.markdown(f"**${p['price']:.2f}**")
                if p["category"]:
                    st.write(f"Category: {p['category']}")
                st.write(stars(p["avg_rating"] or 0) + f"  ({int(p['review_count'] or 0)})")
                st.caption(p["description"] or "")
                qty_key = f"qty_{p['id']}"
                st.number_input("Qty", min_value=1, max_value=max(1, int(p["stock"])), value=1, key=qty_key)
                if st.button("Add to cart", key=f"addcart_{p['id']}"):
                    qty = int(st.session_state[qty_key])
                    add_to_cart(p["id"], p["name"], float(p["price"]), qty)
                    st.success(f"Added {qty} × {p['name']} to cart.")
                if st.button("Add to wishlist", key=f"wish_{p['id']}"):
                    ok, msg = add_wishlist(st.session_state.user["id"], p["id"])
                    st.success(msg) if ok else st.error(msg)
                if st.button("Write review", key=f"revbtn_{p['id']}"):
                    st.session_state.active_review_pid = p["id"]
                st.markdown("</div>", unsafe_allow_html=True)

# ---------- Wishlist ----------
def wishlist_tab():
    st.header("Wishlist")
    items = get_wishlist(st.session_state.user["id"])
    if not items:
        st.info("Wishlist is empty.")
        return
    for i in range(0, len(items), 3):
        cols = st.columns(3)
        for j, p in enumerate(items[i:i+3]):
            with cols[j]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.image(p["image"], use_column_width=True)
                st.markdown(f"**{p['name']}**")
                st.markdown(f"${p['price']:.2f}")
                if st.button("Add to cart", key=f"wl_add_{p['id']}"):
                    add_to_cart(p["id"], p["name"], float(p["price"]), 1)
                    st.success("Added to cart")
                if st.button("Remove", key=f"wl_rm_{p['id']}"):
                    ok, msg = remove_wishlist(st.session_state.user["id"], p["id"])
                    st.success(msg)
                st.markdown("</div>", unsafe_allow_html=True)

# ---------- Review flow ----------
def review_tab():
    pid = st.session_state.active_review_pid
    st.header("Write a Review")
    st.write(f"Product id: {pid}")
    rating = st.slider("Rating", 1, 5, 5, key=f"rev_rating_{pid}")
    comment = st.text_area("Comment", key=f"rev_comment_{pid}")
    if st.button("Save review", key=f"save_rev_{pid}"):
        ok, msg = add_review(st.session_state.user["id"], pid, rating, comment)
        st.success(msg) if ok else st.error(msg)
        st.session_state.active_review_pid = None
    st.divider()
    st.subheader("Recent Reviews")
    for r in get_reviews(pid):
        st.markdown(f"**{r['username']}** — {stars(r['rating'])}")
        if r["comment"]:
            st.caption(r["comment"])

# ---------- Cart & Checkout ----------
def cart_tab():
    st.header("Cart")
    if not st.session_state.cart:
        st.info("Cart empty.")
        return
    total = 0.0
    for idx, it in enumerate(st.session_state.cart):
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
        it["quantity"] = int(st.session_state[qty_key])
        total += it["price"] * it["quantity"]
    st.subheader(f"Total: ${total:.2f}")
    if st.button("Clear cart", key="clear_cart"):
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

# ---------- Orders ----------
def orders_tab():
    st.header("Your Orders")
    orders = list_orders(st.session_state.user["id"])
    if not orders:
        st.info("No orders yet.")
        return
    for o in orders:
        with st.expander(f"Order #{o['id']} — {o['created_at']} — ${o['total']:.2f}"):
            for it in order_items(o["id"]):
                c1, c2 = st.columns([1,3])
                with c1:
                    st.image(it["image"], width=80)
                with c2:
                    st.write(f"**{it['name']}**")
                    st.caption(f"Qty: {it['quantity']} — ${it['price_each']:.2f} each")

# ---------- Profile ----------
def profile_tab():
    st.header("Profile")
    st.write(f"Username: **{st.session_state.user['username']}**")
    st.subheader("Change password")
    old = st.text_input("Old password", type="password", key="chg_old")
    new = st.text_input("New password", type="password", key="chg_new")
    if st.button("Change password", key="chg_btn"):
        ok, msg = change_password(st.session_state.user["id"], old, new)
        st.success(msg) if ok else st.error(msg)
    if st.button("Logout", key="logout_profile"):
        logout()
        st.experimental_rerun()

# ---------- Admin ----------
def admin_tab():
    if not st.session_state.user.get("is_admin"):
        st.warning("Admin only")
        return
    st.header("Admin Dashboard")
    m = admin_metrics()
    st.metric("Users", m["users"], delta=None, key="adm_users")
    st.metric("Orders", m["orders"], key="adm_orders")
    st.metric("Revenue ($)", float(m["revenue"]), key="adm_revenue")
    st.metric("Products", m["products"], key="adm_products")
    if m["low_stock"]:
        st.subheader("Low stock")
        for r in m["low_stock"]:
            st.write(f"{r['name']}: {r['stock']}")
    st.divider()
    st.subheader("Manage Products")
    mode = st.selectbox("Mode", ["Add", "Update", "Delete"], key="admin_mode")
    products_all, _ = list_products(page=1, page_size=9999)
    if mode in ("Update", "Delete"):
        opts = {f"#{p['id']} {p['name']}": p for p in products_all}
        sel = st.selectbox("Select product", list(opts.keys()), key="admin_select")
        current = opts[sel]
    else:
        current = None
    name = st.text_input("Name", value=current["name"] if current else "", key="admin_name")
    price = st.number_input("Price", value=float(current["price"]) if current else 100.0, key="admin_price")
    image = st.text_input("Image URL", value=current["image"] if current else "", key="admin_image")
    category = st.text_input("Category", value=current["category"] if current else "Casual", key="admin_cat")
    desc = st.text_area("Description", value=current["description"] if current else "", key="admin_desc")
    stock = st.number_input("Stock", min_value=0, value=int(current["stock"]) if current else 10, key="admin_stock")
    if st.button("Submit", key="admin_submit"):
        if mode == "Add":
            ok, msg = add_product(name, price, image, category, desc, stock)
            st.success(msg) if ok else st.error(msg)
        elif mode == "Update":
            ok, msg = update_product(current["id"], name, price, image, category, desc, stock)
            st.success(msg) if ok else st.error(msg)
        elif mode == "Delete":
            ok, msg = delete_product(current["id"])
            st.success(msg) if ok else st.error(msg)

# ---------- Router ----------
def router():
    if st.session_state.active_review_pid:
        review_tab()
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

# ---------- Entry ----------
if st.session_state.user is None:
    auth_ui()
else:
    topL, topR = st.columns([4,1])
    with topL:
        st.title(f"Hello, {st.session_state.user['username']} 👋")
    with topR:
        if st.button("Logout", key="logout_top"):
            logout()
            st.experimental_rerun()
    router()
