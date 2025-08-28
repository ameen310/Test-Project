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

# ---------- Page & Style ----------
st.set_page_config(page_title="Nike-Style Store", page_icon="👟", layout="wide")

PRIMARY = "#111"          # Dark header
ACCENT = "#ff3b30"        # Nike-ish red
CARD_BG = "#ffffff"
MUTED = "#6b7280"

st.markdown(f"""
<style>
/* Global */
:root {{
  --primary: {PRIMARY};
  --accent: {ACCENT};
}}
.block-container {{
  padding-top: 1.5rem;
}}
/* Headline */
h1, h2, h3, h4 {{
  letter-spacing: 0.2px;
}}
/* Card */
.card {{
  background: {CARD_BG};
  border-radius: 16px;
  padding: 14px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
  border: 1px solid rgba(0,0,0,0.05);
}}
.btn {{
  display:inline-block; padding: 8px 16px; border-radius: 999px; 
  background: var(--accent); color: #fff; text-decoration:none; font-weight: 600;
}}
.btn-muted {{
  background: #e5e7eb; color:#111;
}}
.badge {{
  display:inline-block; padding: 4px 10px; border-radius:999px; 
  background:#111; color:#fff; font-size:12px; font-weight:700;
}}
.price {{
  font-weight: 800; font-size: 18px; color:#111;
}}
.rating {{
  color: #f59e0b; font-weight:700;
}}
.muted {{
  color: {MUTED};
  font-size: 13px;
}}
.hr {{
  margin: 12px 0; height:1px; background:#eee;
}}
</style>
""", unsafe_allow_html=True)

# ---------- Session ----------
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []  # list of dicts: id, name, price, quantity
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Shop"

def logout():
    st.session_state.user = None
    st.session_state.cart = []
    st.session_state.active_tab = "Shop"

# ---------- Auth ----------
def auth_ui():
    st.title("👟 Welcome to the Nike-Style Store")
    st.caption("Sign in to shop, review, wishlist, and track your orders.")

    colL, colR = st.columns(2)
    with colL:
        st.subheader("Sign In")
        lu = st.text_input("Username", key="login_user")
        lp = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", use_container_width=True):
            ok, user = authenticate(lu, lp)
            if ok:
                st.session_state.user = user
                st.success(f"Welcome back, **{user['username']}**!")
            else:
                st.error("Invalid credentials.")

    with colR:
        st.subheader("Register")
        ru = st.text_input("New Username", key="reg_user")
        rp = st.text_input("New Password", type="password", key="reg_pass")
        if st.button("Create Account", use_container_width=True):
            ok, msg = register_user(ru, rp)
            if ok:
                st.success(msg + " You can now log in.")
            else:
                st.error(msg)

# ---------- Utilities ----------
def stars(r: float) -> str:
    # show 5 star unicode based on average rating
    filled = int(round(r))
    return "⭐" * filled + "☆" * (5 - filled)

def add_to_cart(product_id: int, name: str, price: float, qty: int):
    if qty < 1:
        st.warning("Quantity must be at least 1.")
        return
    # merge items
    for it in st.session_state.cart:
        if it["id"] == product_id:
            it["quantity"] += qty
            break
    else:
        st.session_state.cart.append({"id": product_id, "name": name, "price": price, "quantity": qty})
    st.toast(f"Added {qty} × {name} to cart")

def render_product_card(p):
    pid = p["id"]
    st.image(p["image"], use_column_width=True)
    st.markdown(f"<div class='price'>${p['price']:.2f}</div>", unsafe_allow_html=True)
    st.markdown(f"**{p['name']}**")
    if p["category"]:
        st.markdown(f"<span class='badge'>{p['category']}</span>", unsafe_allow_html=True)
    avg = p["avg_rating"] or 0
    st.markdown(f"<div class='rating'>{stars(avg)} <span class='muted'>({int(p['review_count'])} reviews)</span></div>", unsafe_allow_html=True)
    if p["description"]:
        st.caption(p["description"])
    st.caption(f"Stock: {p['stock']}")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        qty = st.number_input("Qty", min_value=1, max_value=max(1, int(p["stock"])), value=1, key=f"qty_{pid}")
    with c2:
        if st.button("Add to Cart", key=f"add_{pid}", use_container_width=True):
            add_to_cart(pid, p["name"], float(p["price"]), int(st.session_state[f"qty_{pid}"]))
    with c3:
        wish_col, review_col = st.columns(2)
        with wish_col:
            if st.button("♡ Wishlist", key=f"wish_{pid}", use_container_width=True):
                ok, msg = add_wishlist(st.session_state.user["id"], pid)
                st.toast(msg)
        with review_col:
            if st.button("✍️ Review", key=f"rev_{pid}", use_container_width=True):
                st.session_state.active_tab = f"Review:{pid}"

# ---------- Tabs ----------
def shop_tab():
    st.header("Shop")
    # filters
    cats = product_categories()
    min_p, max_p = product_min_max_price()
    colA, colB, colC, colD = st.columns([2, 1, 2, 1])
    with colA:
        search = st.text_input("Search by name")
    with colB:
        category = st.selectbox("Category", cats)
    with colC:
        price_range = st.slider("Price range", float(min_p), float(max_p) if max_p>0 else 500.0, (float(min_p), float(max_p) if max_p>0 else 500.0))
    with colD:
        sort_by = st.selectbox("Sort by", ["newest", "price_asc", "price_desc", "rating_desc"])

    # pagination
    page_size = 6
    page = st.number_input("Page", min_value=1, value=1, step=1)

    products, total = list_products(
        search=search, category=category,
        price_min=price_range[0], price_max=price_range[1],
        sort_by=sort_by, page=int(page), page_size=page_size
    )
    total_pages = max(1, ceil(total / page_size))
    st.caption(f"Showing page {int(page)} of {total_pages} — {total} items found")

    # grid
    for i in range(0, len(products), 3):
        row = st.columns(3)
        for j, p in enumerate(products[i:i+3]):
            with row[j]:
                with st.container():
                    st.markdown("<div class='card'>", unsafe_allow_html=True)
                    render_product_card(p)
                    st.markdown("</div>", unsafe_allow_html=True)

def wishlist_tab():
    st.header("Wishlist")
    wl = get_wishlist(st.session_state.user["id"])
    if not wl:
        st.info("Your wishlist is empty.")
        return
    for i in range(0, len(wl), 3):
        row = st.columns(3)
        for j, p in enumerate(wl[i:i+3]):
            with row[j]:
                with st.container():
                    st.markdown("<div class='card'>", unsafe_allow_html=True)
                    st.image(p["image"], use_column_width=True)
                    st.markdown(f"**{p['name']}**")
                    st.markdown(f"<div class='price'>${p['price']:.2f}</div>", unsafe_allow_html=True)
                    st.caption(p["category"] or "Uncategorized")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Add to Cart", key=f"wl_add_{p['id']}", use_container_width=True):
                            add_to_cart(p["id"], p["name"], float(p["price"]), 1)
                    with c2:
                        if st.button("Remove", key=f"wl_rm_{p['id']}", use_container_width=True):
                            ok, msg = remove_wishlist(st.session_state.user["id"], p["id"])
                            st.toast(msg)
                    st.markdown("</div>", unsafe_allow_html=True)

def reviews_flow(product_id: int):
    st.header("Write a Review")
    rating = st.slider("Rating", 1, 5, 5)
    comment = st.text_area("Comment (optional)")
    if st.button("Save Review"):
        ok, msg = add_review(st.session_state.user["id"], product_id, rating, comment)
        if ok:
            st.success(msg)
            st.session_state.active_tab = "Shop"
        else:
            st.error(msg)
    st.divider()
    st.subheader("Recent Reviews")
    for r in get_reviews(product_id):
        st.markdown(f"**{r['username']}** — {stars(r['rating'])}")
        if r["comment"]:
            st.caption(r["comment"])

def cart_tab():
    st.header("Cart & Checkout")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return
    total = 0.0
    for idx, it in enumerate(list(st.session_state.cart)):
        c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
        with c1:
            st.markdown(f"**{it['name']}**")
        with c2:
            qty = st.number_input("Qty", min_value=1, value=int(it["quantity"]), key=f"cart_qty_{idx}")
        with c3:
            price_line = it["price"] * st.session_state[f"cart_qty_{idx}"]
            st.markdown(f"${price_line:.2f}")
        with c4:
            if st.button("Remove", key=f"rm_{idx}"):
                st.session_state.cart.pop(idx)
                st.experimental_set_query_params()  # UI refresh hint
                st.rerun()
        it["quantity"] = int(st.session_state[f"cart_qty_{idx}"])
        total += it["price"] * it["quantity"]
    st.divider()
    st.subheader(f"Total: ${total:.2f}")
    colL, colR = st.columns(2)
    with colL:
        if st.button("Clear Cart", use_container_width=True):
            st.session_state.cart = []
            st.success("Cart cleared.")
    with colR:
        if st.button("Checkout", use_container_width=True):
            ok, msg, order_id = place_order(st.session_state.user["id"], st.session_state.cart)
            if ok:
                st.success(f"{msg} (Order #{order_id})")
                st.balloons()
                st.session_state.cart = []
            else:
                st.error(msg)

def orders_tab():
    st.header("Orders")
    orders = list_orders(st.session_state.user["id"])
    if not orders:
        st.info("No orders yet.")
        return
    for o in orders:
        with st.expander(f"Order #{o['id']} — {o['created_at']} — Total ${o['total']:.2f}"):
            items = order_items(o["id"])
            for it in items:
                c1, c2, c3 = st.columns([1, 4, 2])
                with c1:
                    st.image(it["image"], use_column_width=True)
                with c2:
                    st.markdown(f"**{it['name']}**")
                    st.caption(f"Qty: {it['quantity']}")
                with c3:
                    st.markdown(f"${it['price_each']*it['quantity']:.2f}")

def profile_tab():
    st.header("Profile")
    st.caption(f"Logged in as **{st.session_state.user['username']}**")
    st.subheader("Change Password")
    old = st.text_input("Old Password", type="password")
    new = st.text_input("New Password", type="password")
    if st.button("Update Password"):
        ok, msg = change_password(st.session_state.user["id"], old, new)
        st.success(msg) if ok else st.error(msg)
    st.divider()
    if st.button("Logout", type="secondary"):
        logout()
        st.success("Logged out.")

def admin_tab():
    if not st.session_state.user.get("is_admin"):
        st.warning("Admin only.")
        return
    st.header("Admin Dashboard")

    m = admin_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users", m["users"])
    c2.metric("Orders", m["orders"])
    c3.metric("Revenue ($)", float(m["revenue"]))
    c4.metric("Products", m["products"])
    if m["low_stock"]:
        st.subheader("🔻 Low Stock")
        for row in m["low_stock"]:
            st.write(f"{row['name']}: {row['stock']} left")

    st.divider()
    st.subheader("Add / Update / Delete Product")

    # Create / Update form
    mode = st.radio("Mode", ["Add", "Update", "Delete"], horizontal=True)
    if mode in ("Update", "Delete"):
        # quick picker
        page = 1
        rows, total = list_products(page=page, page_size=9999)
        options = {f"#{r['id']} — {r['name']}": r for r in rows}
        chosen = st.selectbox("Select Product", list(options.keys()))
        current = options[chosen]
    else:
        current = None

    with st.form("product_form", clear_on_submit=(mode=="Add")):
        name = st.text_input("Name", value=current["name"] if current else "")
        price = st.number_input("Price", min_value=0.0, value=float(current["price"]) if current else 100.0)
        image = st.text_input("Image URL", value=current["image"] if current else "")
        category = st.text_input("Category", value=current["category"] if current else "Casual")
        desc = st.text_area("Description", value=current["description"] if current else "")
        stock = st.number_input("Stock", min_value=0, value=int(current["stock"]) if current else 10)
        submitted = st.form_submit_button(mode)

    if mode == "Add" and submitted:
        ok, msg = add_product(name, price, image, category, desc, stock)
        st.success(msg) if ok else st.error(msg)
    elif mode == "Update" and submitted:
        ok, msg = update_product(current["id"], name, price, image, category, desc, stock)
        st.success(msg) if ok else st.error(msg)
    elif mode == "Delete" and submitted:
        ok, msg = delete_product(current["id"])
        st.success(msg) if ok else st.error(msg)

# ---------- Router ----------
def router():
    # Special sub-route for writing a review
    if isinstance(st.session_state.active_tab, str) and st.session_state.active_tab.startswith("Review:"):
        pid = int(st.session_state.active_tab.split(":")[1])
        reviews_flow(pid)
        return

    tabs = st.tabs(["Shop", "Cart", "Orders", "Wishlist", "Profile"] + (["Admin"] if st.session_state.user.get("is_admin") else []))
    with tabs[0]: shop_tab()
    with tabs[1]: cart_tab()
    with tabs[2]: orders_tab()
    with tabs[3]: wishlist_tab()
    with tabs[4]: profile_tab()
    if st.session_state.user.get("is_admin"):
        with tabs[5]: admin_tab()

# ---------- Entry ----------
if st.session_state.user is None:
    auth_ui()
else:
    top = st.container()
    with top:
        left, right = st.columns([4,1])
        with left:
            st.title(f"Hey, {st.session_state.user['username']} 👋")
            st.caption("Browse, wishlist, review, and shop your favorite kicks.")
        with right:
            if st.button("Logout"):
                logout()
                st.stop()
    router()
