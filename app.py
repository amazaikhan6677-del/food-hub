"""
app.py
FoodHub - Fast Food Ordering Chatbot Website
Main Flask application: page routes, REST API, auth, admin panel.

Run with:
    python app.py
Then open:
    http://127.0.0.1:5000/
"""

import os
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, jsonify, session,
                    redirect, url_for, flash, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config
from database import (db, seed_data, User, Admin, Category, FoodItem,
                       Cart, CartItem, Order, OrderItem, Payment,
                       DeliveryAddress, Review, Offer, ChatbotMessage,
                       CATEGORY_DEFAULT_IMAGES)
from chatbot_engine import handle_message
from payment_service import process_payment
from order_service import create_order_from_cart

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    seed_data(app)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def get_session_id():
    """Every visitor (guest or logged in) gets a stable cart/session id."""
    if "cart_session_id" not in session:
        session["cart_session_id"] = uuid.uuid4().hex
    return session["cart_session_id"]


def current_user():
    uid = session.get("user_id")
    if uid:
        return User.query.get(uid)
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


def get_or_create_cart():
    sid = get_session_id()
    cart = Cart.query.filter_by(session_id=sid).first()
    if not cart:
        cart = Cart(session_id=sid, user_id=session.get("user_id"))
        db.session.add(cart)
        db.session.commit()
    return cart


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serves real photos the admin uploads for menu items."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.context_processor
def inject_globals():
    cart = None
    try:
        cart = get_or_create_cart()
    except Exception:
        pass
    cart_count = sum(i.quantity for i in cart.items) if cart else 0
    return {"current_user": current_user(), "cart_count": cart_count}


# ---------------------------------------------------------------------------
# ERROR HANDLERS  (friendly pages, never raw stack traces)
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template("error.html", code=500, message="Something went wrong on our end. Please try again."), 500


# ---------------------------------------------------------------------------
# CUSTOMER-FACING PAGES
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    popular = FoodItem.query.filter_by(is_popular=True, is_available=True).limit(8).all()
    deals = FoodItem.query.filter_by(is_deal=True, is_available=True).limit(6).all()
    offers = Offer.query.filter_by(active=True).all()
    reviews = Review.query.order_by(Review.id.desc()).limit(6).all()
    return render_template("index.html", popular=popular, deals=deals, offers=offers, reviews=reviews)


@app.route("/menu")
def menu():
    categories = Category.query.all()
    return render_template("menu.html", categories=categories)


@app.route("/cart")
def cart_page():
    return render_template("cart.html")


@app.route("/checkout")
def checkout_page():
    cart = get_or_create_cart()
    if not cart.items:
        flash("Your cart is empty. Add something tasty first!", "warning")
        return redirect(url_for("menu"))
    return render_template("checkout.html")


@app.route("/orders")
@login_required
def orders_page():
    return render_template("orders.html")


@app.route("/tracking")
def tracking_page():
    order_number = request.args.get("order_number", "")
    return render_template("tracking.html", order_number=order_number)


# ---------------------------------------------------------------------------
# AUTH PAGES (customer)
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not (name and email and phone and password):
            flash("Please fill in all fields.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
        else:
            user = User(name=name, email=email, phone=phone,
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash("Welcome to FoodHub! Your account has been created.", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash("Your account has been disabled. Please contact support.", "danger")
                return render_template("login.html")
            session["user_id"] = user.id
            # merge guest cart into user
            cart = get_or_create_cart()
            cart.user_id = user.id
            db.session.commit()
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# CUSTOMER API
# ---------------------------------------------------------------------------
@app.route("/api/menu")
def api_menu():
    category = request.args.get("category")
    search = request.args.get("search")
    max_price = request.args.get("max_price", type=float)
    query = FoodItem.query
    if category and category.lower() != "all":
        query = query.join(Category).filter(Category.name.ilike(category))
    if search:
        query = query.filter(FoodItem.name.ilike(f"%{search}%"))
    if max_price:
        query = query.filter(FoodItem.price <= max_price)
    items = query.all()
    return jsonify({"success": True, "items": [i.to_dict() for i in items]})


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True, silent=True) or {}
    name, email, phone, password = data.get("name"), data.get("email"), data.get("phone"), data.get("password")
    if not (name and email and phone and password):
        return jsonify({"success": False, "message": "All fields are required."}), 400
    if User.query.filter_by(email=email.lower()).first():
        return jsonify({"success": False, "message": "Email already registered."}), 400
    user = User(name=name, email=email.lower(), phone=phone, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    session["user_id"] = user.id
    return jsonify({"success": True, "user": user.to_dict()})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email, password = data.get("email", "").lower(), data.get("password", "")
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"success": False, "message": "Invalid email or password."}), 401
    if not user.is_active:
        return jsonify({"success": False, "message": "Account disabled."}), 403
    session["user_id"] = user.id
    return jsonify({"success": True, "user": user.to_dict()})


@app.route("/api/cart", methods=["GET"])
def api_cart():
    cart = get_or_create_cart()
    return jsonify({"success": True, "cart": cart.to_dict()})


@app.route("/api/cart/add", methods=["POST"])
def api_cart_add():
    data = request.get_json(force=True, silent=True) or {}
    food_id = data.get("food_id")
    quantity = int(data.get("quantity", 1))
    food = FoodItem.query.get(food_id)
    if not food:
        return jsonify({"success": False, "message": "Item not found."}), 404
    if not food.is_available:
        return jsonify({"success": False, "message": f"{food.name} is currently out of stock."}), 400

    cart = get_or_create_cart()
    ci = CartItem.query.filter_by(cart_id=cart.id, food_id=food.id).first()
    if ci:
        ci.quantity += quantity
    else:
        ci = CartItem(cart_id=cart.id, food_id=food.id, quantity=max(1, quantity))
        db.session.add(ci)
    db.session.commit()
    return jsonify({"success": True, "cart": cart.to_dict()})


@app.route("/api/cart/update", methods=["POST"])
def api_cart_update():
    data = request.get_json(force=True, silent=True) or {}
    item_id = data.get("item_id")
    quantity = int(data.get("quantity", 1))
    cart = get_or_create_cart()
    ci = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if not ci:
        return jsonify({"success": False, "message": "Cart item not found."}), 404
    if quantity <= 0:
        db.session.delete(ci)
    else:
        ci.quantity = quantity
    db.session.commit()
    return jsonify({"success": True, "cart": cart.to_dict()})


@app.route("/api/cart/remove", methods=["POST"])
def api_cart_remove():
    data = request.get_json(force=True, silent=True) or {}
    item_id = data.get("item_id")
    cart = get_or_create_cart()
    ci = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if ci:
        db.session.delete(ci)
        db.session.commit()
    return jsonify({"success": True, "cart": cart.to_dict()})


@app.route("/api/orders/create", methods=["POST"])
def api_orders_create():
    data = request.get_json(force=True, silent=True) or {}
    cart = get_or_create_cart()

    ok, result = create_order_from_cart(
        cart=cart,
        user_id=session.get("user_id"),
        data=data,
        delivery_fee=app.config["DELIVERY_FEE"],
        free_delivery_threshold=app.config["FREE_DELIVERY_THRESHOLD"],
    )
    if not ok:
        return jsonify({"success": False, "message": result}), 400
    return jsonify({"success": True, "order": result.to_dict()})


@app.route("/api/orders")
def api_orders():
    user = current_user()
    if not user:
        return jsonify({"success": False, "message": "Login required."}), 401
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return jsonify({"success": True, "orders": [o.to_dict() for o in orders]})


@app.route("/api/orders/<order_number>")
def api_order_detail(order_number):
    order = Order.query.filter_by(order_number=order_number.upper()).first()
    if not order:
        return jsonify({"success": False, "message": "Invalid Order ID. Please check and try again."}), 404
    return jsonify({"success": True, "order": order.to_dict()})


@app.route("/api/orders/<order_number>/status", methods=["POST"])
def api_order_update_status(order_number):
    # Customer-side cancellation only; broader status changes are admin-only
    # (see /api/admin/orders/<id>/status).
    data = request.get_json(force=True, silent=True) or {}
    order = Order.query.filter_by(order_number=order_number.upper()).first()
    if not order:
        return jsonify({"success": False, "message": "Invalid Order ID."}), 404
    new_status = data.get("status")
    if new_status == "Cancelled" and order.status in ("Order Received", "Order Confirmed"):
        order.status = "Cancelled"
        db.session.commit()
        return jsonify({"success": True, "order": order.to_dict()})
    return jsonify({"success": False, "message": "This order can no longer be cancelled."}), 400


@app.route("/api/payment", methods=["POST"])
def api_payment():
    """Standalone demo payment endpoint (e.g. for retrying a failed payment)."""
    data = request.get_json(force=True, silent=True) or {}
    result = process_payment(
        method=data.get("method", "cod"),
        amount=float(data.get("amount", 0)),
        card_last4=data.get("card_last4"),
        mobile_number=data.get("mobile_number"),
    )
    return jsonify({"success": result["status"] != "Failed", "payment": result})


@app.route("/api/chatbot", methods=["POST"])
def api_chatbot():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"success": False, "message": "Empty message."}), 400

    sid = get_session_id()
    result = handle_message(
        message, sid,
        user_id=session.get("user_id"),
        delivery_fee=app.config["DELIVERY_FEE"],
        free_delivery_threshold=app.config["FREE_DELIVERY_THRESHOLD"],
    )

    log = ChatbotMessage(session_id=sid, user_id=session.get("user_id"),
                          message=message, response=result["reply"])
    db.session.add(log)
    db.session.commit()

    return jsonify({
        "success": True,
        "reply": result["reply"],
        "action": result["action"],
        "order": result.get("order"),
    })


# ---------------------------------------------------------------------------
# ADMIN PAGES
# ---------------------------------------------------------------------------
@app.route("/admin")
def admin_root():
    return redirect(url_for("admin_dashboard") if session.get("admin_id") else url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session["admin_id"] = admin.id
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "danger")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html")


@app.route("/admin/orders")
@admin_required
def admin_orders():
    return render_template("admin/orders.html")


@app.route("/admin/menu")
@admin_required
def admin_menu():
    categories = Category.query.all()
    return render_template("admin/menu.html", categories=categories)


@app.route("/admin/customers")
@admin_required
def admin_customers():
    return render_template("admin/customers.html")


@app.route("/admin/payments")
@admin_required
def admin_payments():
    return render_template("admin/payments.html")


@app.route("/admin/offers")
@admin_required
def admin_offers():
    return render_template("admin/offers.html")


# ---------------------------------------------------------------------------
# ADMIN API
# ---------------------------------------------------------------------------
@app.route("/api/admin/stats")
@admin_required
def api_admin_stats():
    today = datetime.utcnow().date()
    total_orders = Order.query.count()
    todays_orders = Order.query.filter(db.func.date(Order.created_at) == str(today)).count()
    total_revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)) \
        .filter(Order.payment_status == "Paid").scalar()
    pending = Order.query.filter(Order.status.notin_(["Delivered", "Cancelled"])).count()
    completed = Order.query.filter_by(status="Delivered").count()
    customers = User.query.count()

    popular = db.session.query(OrderItem.name, db.func.sum(OrderItem.quantity).label("qty")) \
        .group_by(OrderItem.name).order_by(db.desc("qty")).limit(5).all()

    # last 7 days sales
    since = today - timedelta(days=6)
    daily = db.session.query(db.func.date(Order.created_at), db.func.coalesce(db.func.sum(Order.total), 0)) \
        .filter(db.func.date(Order.created_at) >= str(since)) \
        .group_by(db.func.date(Order.created_at)).all()
    daily_map = {str(d): float(v) for d, v in daily}
    daily_sales = [{"date": str(since + timedelta(days=i)),
                     "total": daily_map.get(str(since + timedelta(days=i)), 0)} for i in range(7)]

    by_category = db.session.query(Category.name, db.func.coalesce(db.func.sum(OrderItem.quantity), 0)) \
        .join(FoodItem, FoodItem.category_id == Category.id) \
        .join(OrderItem, OrderItem.food_id == FoodItem.id) \
        .group_by(Category.name).all()

    by_payment_method = db.session.query(Order.payment_method, db.func.count(Order.id)) \
        .group_by(Order.payment_method).all()

    return jsonify({
        "success": True,
        "stats": {
            "total_orders": total_orders,
            "todays_orders": todays_orders,
            "total_revenue": round(total_revenue or 0, 2),
            "pending_orders": pending,
            "completed_orders": completed,
            "customers": customers,
            "popular_products": [{"name": n, "qty": int(q)} for n, q in popular],
            "daily_sales": daily_sales,
            "orders_by_category": [{"category": c, "qty": int(q)} for c, q in by_category],
            "payment_methods": [{"method": m, "count": c} for m, c in by_payment_method],
        }
    })


@app.route("/api/admin/orders")
@admin_required
def api_admin_orders():
    status = request.args.get("status")
    query = Order.query
    if status and status.lower() != "all":
        query = query.filter_by(status=status)
    orders = query.order_by(Order.created_at.desc()).all()
    return jsonify({"success": True, "orders": [o.to_dict() for o in orders]})


@app.route("/api/admin/orders/<order_number>/status", methods=["POST"])
@admin_required
def api_admin_order_status(order_number):
    data = request.get_json(force=True, silent=True) or {}
    order = Order.query.filter_by(order_number=order_number.upper()).first()
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404
    new_status = data.get("status")
    if new_status not in Order.STATUS_FLOW + ["Cancelled"]:
        return jsonify({"success": False, "message": "Invalid status."}), 400
    order.status = new_status
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})


@app.route("/api/admin/orders/<order_number>/approve", methods=["POST"])
@admin_required
def api_admin_order_approve(order_number):
    """One-click approve: Order Received -> Order Confirmed, and marks a
    pending Cash-on-Delivery payment as acknowledged by staff."""
    order = Order.query.filter_by(order_number=order_number.upper()).first()
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404
    if order.status not in ("Order Received",):
        return jsonify({"success": False, "message": f"Order is already '{order.status}'."}), 400
    order.status = "Order Confirmed"
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})


@app.route("/api/admin/orders/<order_number>/reject", methods=["POST"])
@admin_required
def api_admin_order_reject(order_number):
    """One-click reject/cancel an order that hasn't been prepared yet."""
    data = request.get_json(force=True, silent=True) or {}
    order = Order.query.filter_by(order_number=order_number.upper()).first()
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404
    if order.status in ("Delivered", "Cancelled"):
        return jsonify({"success": False, "message": f"Order is already '{order.status}' and can't be rejected."}), 400
    order.status = "Cancelled"
    if data.get("reason"):
        order.instructions = (order.instructions or "") + f"\n[Rejected by admin: {data['reason']}]"
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})


@app.route("/api/admin/menu", methods=["GET", "POST"])
@admin_required
def api_admin_menu():
    if request.method == "GET":
        items = FoodItem.query.all()
        return jsonify({"success": True, "items": [i.to_dict() for i in items]})

    # POST -> create new item
    name = request.form.get("name")
    price = request.form.get("price", type=float)
    category_id = request.form.get("category_id", type=int)
    description = request.form.get("description", "")
    if not (name and price and category_id):
        return jsonify({"success": False, "message": "Name, price and category are required."}), 400

    category = Category.query.get(category_id)
    image_filename = CATEGORY_DEFAULT_IMAGES.get(category.name if category else None, "placeholder.svg")

    file = request.files.get("image")
    if file and file.filename:
        if not allowed_file(file.filename):
            return jsonify({"success": False, "message": "Image must be png, jpg, jpeg, gif or webp."}), 400
        image_filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

    item = FoodItem(name=name, description=description, price=price,
                     category_id=category_id, image=image_filename)
    db.session.add(item)
    db.session.commit()
    return jsonify({"success": True, "item": item.to_dict()})


def _delete_uploaded_file(filename):
    """Best-effort cleanup of a real uploaded photo (never touches built-in
    default photos, whether they're external URLs or legacy local icons)."""
    if not filename:
        return
    if filename.startswith("http://") or filename.startswith("https://"):
        return
    if filename.startswith("food/") or filename == "placeholder.svg":
        return
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@app.route("/api/admin/menu/<int:item_id>", methods=["PUT", "DELETE"])
@admin_required
def api_admin_menu_item(item_id):
    item = FoodItem.query.get(item_id)
    if not item:
        return jsonify({"success": False, "message": "Item not found."}), 404

    if request.method == "DELETE":
        _delete_uploaded_file(item.image)
        db.session.delete(item)
        db.session.commit()
        return jsonify({"success": True})

    # ---- Full edit with real image upload/removal (multipart form) -------
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        for field in ("name", "description"):
            if request.form.get(field) is not None and request.form.get(field) != "":
                setattr(item, field, request.form.get(field))
        if request.form.get("price"):
            item.price = float(request.form.get("price"))
        if request.form.get("category_id"):
            item.category_id = int(request.form.get("category_id"))
        for flag in ("is_available", "is_deal", "is_popular"):
            if request.form.get(flag) is not None:
                item.__setattr__(flag, request.form.get(flag) in ("true", "1", "on", "True"))

        # Remove current photo -> reset to this item's category default image
        if request.form.get("remove_image") in ("true", "1"):
            _delete_uploaded_file(item.image)
            category = Category.query.get(item.category_id)
            item.image = CATEGORY_DEFAULT_IMAGES.get(category.name if category else None, "placeholder.svg")

        # Upload a new real photo -> replaces the current image
        file = request.files.get("image")
        if file and file.filename:
            if not allowed_file(file.filename):
                return jsonify({"success": False, "message": "Image must be png, jpg, jpeg, gif or webp."}), 400
            _delete_uploaded_file(item.image)
            new_filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], new_filename))
            item.image = new_filename

        db.session.commit()
        return jsonify({"success": True, "item": item.to_dict()})

    # ---- Quick JSON toggles (availability / deal / popular switches) -----
    data = request.get_json(force=True, silent=True) or {}
    for field in ("name", "description", "price", "category_id", "is_available", "is_deal", "is_popular"):
        if field in data:
            setattr(item, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "item": item.to_dict()})


@app.route("/api/admin/customers")
@admin_required
def api_admin_customers():
    search = request.args.get("search", "")
    query = User.query
    if search:
        query = query.filter(db.or_(User.name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
    users = query.order_by(User.created_at.desc()).all()
    return jsonify({"success": True, "customers": [u.to_dict() for u in users]})


@app.route("/api/admin/customers/<int:user_id>/toggle", methods=["POST"])
@admin_required
def api_admin_customer_toggle(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "Customer not found."}), 404
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({"success": True, "customer": user.to_dict()})


@app.route("/api/admin/payments")
@admin_required
def api_admin_payments():
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    result = []
    for p in payments:
        d = p.to_dict()
        d["order_number"] = p.order.order_number if p.order else None
        d["customer_name"] = p.order.customer_name if p.order else None
        result.append(d)
    return jsonify({"success": True, "payments": result})


@app.route("/api/admin/offers", methods=["GET", "POST"])
@admin_required
def api_admin_offers():
    if request.method == "GET":
        return jsonify({"success": True, "offers": [o.to_dict() for o in Offer.query.all()]})
    data = request.get_json(force=True, silent=True) or {}
    offer = Offer(title=data.get("title", "New Offer"), description=data.get("description", ""),
                  discount_percent=data.get("discount_percent", 0), active=True)
    db.session.add(offer)
    db.session.commit()
    return jsonify({"success": True, "offer": offer.to_dict()})


@app.route("/api/admin/offers/<int:offer_id>", methods=["PUT", "DELETE"])
@admin_required
def api_admin_offer_item(offer_id):
    offer = Offer.query.get(offer_id)
    if not offer:
        return jsonify({"success": False, "message": "Offer not found."}), 404
    if request.method == "DELETE":
        db.session.delete(offer)
        db.session.commit()
        return jsonify({"success": True})
    data = request.get_json(force=True, silent=True) or {}
    for field in ("title", "description", "discount_percent", "active"):
        if field in data:
            setattr(offer, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "offer": offer.to_dict()})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
