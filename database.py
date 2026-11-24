"""
database.py
SQLAlchemy models + helper for seeding sample data on first run.
"""

from datetime import datetime
import uuid

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

# Built-in default photos (used as the default image for new items, and as
# the "reset" image when an admin removes an uploaded photo). These are
# real food photographs (not icons), hotlinked from Unsplash under the
# free Unsplash License. Admins can replace any of these with their own
# uploaded photo at any time from the admin panel.
CATEGORY_DEFAULT_IMAGES = {
    "Burgers": "https://images.unsplash.com/photo-1553979459-d2229ba7433b?auto=format&fit=crop&w=600&q=70",
    "Pizza": "https://images.unsplash.com/photo-1559160582-eab6966b680f?auto=format&fit=crop&w=600&q=70",
    "Fries": "https://images.unsplash.com/photo-1615485290836-4ebcebf44aaf?auto=format&fit=crop&w=600&q=70",
    "Chicken": "https://images.unsplash.com/photo-1426869981800-95ebf51ce900?auto=format&fit=crop&w=600&q=70",
    "Shawarma": "https://images.unsplash.com/photo-1699728088614-7d1d4277414b?auto=format&fit=crop&w=600&q=70",
    "Wraps": "https://images.unsplash.com/photo-1562059390-a761a084768e?auto=format&fit=crop&w=600&q=70",
    "Drinks": "https://images.unsplash.com/photo-1514218953589-2d7d37efd2dc?auto=format&fit=crop&w=600&q=70",
    "Desserts": "https://images.unsplash.com/photo-1608108132933-741a71c144ef?auto=format&fit=crop&w=600&q=70",
    "Deals": "https://images.unsplash.com/photo-1685633224810-bd23d2b0c699?auto=format&fit=crop&w=600&q=70",
}


# ---------------------------------------------------------------------------
# USERS / ADMINS
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship("Order", backref="user", lazy=True)
    addresses = db.relationship("DeliveryAddress", backref="user", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


# ---------------------------------------------------------------------------
# MENU
# ---------------------------------------------------------------------------
class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    items = db.relationship("FoodItem", backref="category", lazy=True)


class FoodItem(db.Model):
    __tablename__ = "food_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), default="")
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    image = db.Column(db.String(255), default="placeholder.svg")
    rating = db.Column(db.Float, default=4.5)
    is_available = db.Column(db.Boolean, default=True)
    is_deal = db.Column(db.Boolean, default=False)
    is_popular = db.Column(db.Boolean, default=False)

    @property
    def image_url(self):
        """
        Resolves the stored `image` value into an actual URL the browser
        can load:
          - "https://..."      -> a real photo (built-in default, or an
                                   admin-set external URL) — used as-is
          - "food/<name>.svg"  -> legacy built-in icon (/static/images/food/...)
          - "placeholder.svg"  -> default fallback (/static/images/placeholder.svg)
          - anything else      -> an admin-uploaded file, served from /uploads/<file>
        """
        img = self.image or "placeholder.svg"
        if img.startswith("http://") or img.startswith("https://"):
            return img
        if img.startswith("food/") or img == "placeholder.svg":
            return "/static/images/" + img
        return "/uploads/" + img

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "category": self.category.name if self.category else None,
            "category_id": self.category_id,
            "image": self.image,
            "image_url": self.image_url,
            "rating": self.rating,
            "is_available": self.is_available,
            "is_deal": self.is_deal,
            "is_popular": self.is_popular,
        }


# ---------------------------------------------------------------------------
# CART (works for guests via session_id, and logged-in users via user_id)
# ---------------------------------------------------------------------------
class Cart(db.Model):
    __tablename__ = "cart"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("CartItem", backref="cart", lazy=True, cascade="all, delete-orphan")

    def totals(self, delivery_fee=150.0, free_delivery_threshold=2000.0, discount_percent=0.0):
        subtotal = sum(i.food.price * i.quantity for i in self.items if i.food)
        discount = round(subtotal * (discount_percent / 100.0), 2)
        delivery = 0.0 if subtotal >= free_delivery_threshold or subtotal == 0 else delivery_fee
        total = round(subtotal - discount + delivery, 2)
        return {
            "subtotal": round(subtotal, 2),
            "discount": discount,
            "delivery_fee": delivery,
            "total": total,
        }

    def to_dict(self):
        return {
            "items": [i.to_dict() for i in self.items],
            "totals": self.totals(),
        }


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id"), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    food = db.relationship("FoodItem")

    def to_dict(self):
        return {
            "id": self.id,
            "food_id": self.food_id,
            "name": self.food.name if self.food else "Unknown item",
            "price": self.food.price if self.food else 0,
            "image": self.food.image if self.food else "placeholder.svg",
            "image_url": self.food.image_url if self.food else "/static/images/placeholder.svg",
            "quantity": self.quantity,
            "line_total": round((self.food.price if self.food else 0) * self.quantity, 2),
        }


# ---------------------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------------------
class Order(db.Model):
    __tablename__ = "orders"

    STATUS_FLOW = [
        "Order Received",
        "Order Confirmed",
        "Preparing",
        "Ready",
        "Out for Delivery",
        "Delivered",
    ]

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    instructions = db.Column(db.String(500), default="")

    subtotal = db.Column(db.Float, default=0.0)
    delivery_fee = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)

    payment_method = db.Column(db.String(30), default="cod")   # cod | card | jazzcash | easypaisa
    payment_status = db.Column(db.String(30), default="Pending")  # Pending | Paid | Failed

    status = db.Column(db.String(30), default="Order Received")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")
    payment = db.relationship("Payment", backref="order", uselist=False, cascade="all, delete-orphan")

    @staticmethod
    def generate_order_number():
        return "FH" + uuid.uuid4().hex[:8].upper()

    def to_dict(self):
        return {
            "order_number": self.order_number,
            "customer_name": self.customer_name,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "city": self.city,
            "instructions": self.instructions,
            "subtotal": self.subtotal,
            "delivery_fee": self.delivery_fee,
            "discount": self.discount,
            "total": self.total,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "status": self.status,
            "status_flow": self.STATUS_FLOW,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "items": [i.to_dict() for i in self.items],
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)

    def to_dict(self):
        return {
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity,
            "line_total": round(self.price * self.quantity, 2),
        }


# ---------------------------------------------------------------------------
# PAYMENTS  (payment-service abstraction — no raw card data is ever stored)
# ---------------------------------------------------------------------------
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    method = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), default="Pending")
    transaction_id = db.Column(db.String(64), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    is_demo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "method": self.method,
            "status": self.status,
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "is_demo": self.is_demo,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


# ---------------------------------------------------------------------------
# ADDRESSES / REVIEWS / OFFERS / CHATBOT LOG
# ---------------------------------------------------------------------------
class DeliveryAddress(db.Model):
    __tablename__ = "delivery_addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(50), default="Home")
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(80), nullable=False)


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    customer_name = db.Column(db.String(120), default="Anonymous")
    rating = db.Column(db.Integer, default=5)
    comment = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Offer(db.Model):
    __tablename__ = "offers"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), default="")
    discount_percent = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "discount_percent": self.discount_percent,
            "active": self.active,
        }


class ChatbotMessage(db.Model):
    __tablename__ = "chatbot_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    message = db.Column(db.String(500), nullable=False)
    response = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatState(db.Model):
    """
    Holds FoodBot's multi-turn conversation state per visitor session, so it
    can walk someone through a real checkout (name -> phone -> address ->
    city -> payment method -> confirm) entirely inside the chat window and
    then create a genuine Order row via order_service.create_order_from_cart.
    """
    __tablename__ = "chat_states"

    session_id = db.Column(db.String(64), primary_key=True)
    stage = db.Column(db.String(40), default="idle")
    # JSON-encoded scratch data being collected during the conversation
    # (name, phone, address, city, payment_method, etc.)
    data = db.Column(db.Text, default="{}")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# SEED DATA
# ---------------------------------------------------------------------------
def seed_data(app):
    """Create tables (if missing) and populate sample data on first run."""
    with app.app_context():
        db.create_all()

        # ---- Admin -------------------------------------------------------
        if not Admin.query.first():
            admin = Admin(
                username=app.config["DEFAULT_ADMIN_USERNAME"],
                password_hash=generate_password_hash(app.config["DEFAULT_ADMIN_PASSWORD"]),
            )
            db.session.add(admin)

        # ---- Categories ----------------------------------------------------
        category_names = ["Burgers", "Pizza", "Fries", "Chicken", "Shawarma",
                           "Wraps", "Drinks", "Desserts", "Deals"]
        existing = {c.name: c for c in Category.query.all()}
        for name in category_names:
            if name not in existing:
                c = Category(name=name)
                db.session.add(c)
                existing[name] = c
        db.session.commit()
        cat = {c.name: c.id for c in Category.query.all()}

        # ---- Food items ------------------------------------------------
        if FoodItem.query.count() == 0:
            items = [
                ("Zinger Burger", "Crispy fried chicken fillet burger with spicy mayo.", 450, "Burgers", 4.7, True, False),
                ("Beef Deluxe Burger", "Juicy beef patty, cheddar cheese, lettuce & tomato.", 550, "Burgers", 4.6, True, False),
                ("Classic Cheeseburger", "Beef patty topped with melted cheese.", 380, "Burgers", 4.4, False, False),
                ("Chicken Tikka Pizza", "Loaded with spicy chicken tikka & mozzarella.", 1150, "Pizza", 4.8, True, False),
                ("Fajita Pizza", "Grilled chicken fajita with peppers & onions.", 1200, "Pizza", 4.5, False, False),
                ("Margherita Pizza", "Classic cheese & tomato pizza.", 950, "Pizza", 4.3, False, False),
                ("Peri Peri Fries", "Crispy fries tossed in peri peri seasoning.", 280, "Fries", 4.6, True, False),
                ("Loaded Cheese Fries", "Fries topped with melted cheese sauce.", 350, "Fries", 4.5, False, False),
                ("Plain Fries", "Golden crispy classic fries.", 220, "Fries", 4.2, False, False),
                ("Crispy Fried Chicken (4pcs)", "Spicy crunchy fried chicken pieces.", 750, "Chicken", 4.7, True, False),
                ("Grilled Chicken Platter", "Grilled chicken served with rice & salad.", 850, "Chicken", 4.5, False, False),
                ("Chicken Shawarma", "Classic garlic-sauce chicken shawarma roll.", 300, "Shawarma", 4.6, True, False),
                ("Beef Shawarma", "Spiced beef shawarma with tahini sauce.", 330, "Shawarma", 4.4, False, False),
                ("Chicken Fajita Wrap", "Grilled chicken fajita wrapped in soft bread.", 400, "Wraps", 4.5, False, False),
                ("Zinger Wrap", "Crispy chicken zinger wrapped with veggies.", 420, "Wraps", 4.6, True, False),
                ("Coca-Cola (500ml)", "Chilled soft drink.", 120, "Drinks", 4.3, False, False),
                ("Fresh Lemonade", "Freshly squeezed lemonade.", 180, "Drinks", 4.5, False, False),
                ("Chocolate Lava Cake", "Warm chocolate cake with molten center.", 380, "Desserts", 4.8, True, False),
                ("Ice Cream Sundae", "Vanilla ice cream with chocolate syrup.", 300, "Desserts", 4.4, False, False),
                ("Family Deal (2 Burgers + Fries + Drink)", "Perfect combo for two people.", 1400, "Deals", 4.7, True, True),
                ("Burger + Fries + Drink Combo", "Single-person value combo meal.", 750, "Deals", 4.6, True, True),
            ]
            for name, desc, price, cat_name, rating, is_deal, is_popular in items:
                food = FoodItem(
                    name=name,
                    description=desc,
                    price=price,
                    category_id=cat[cat_name],
                    image=CATEGORY_DEFAULT_IMAGES.get(cat_name, "placeholder.svg"),
                    rating=rating,
                    is_available=True,
                    is_deal=is_deal,
                    is_popular=is_popular or (rating >= 4.7),
                )
                db.session.add(food)

        # ---- Offers ------------------------------------------------------
        if Offer.query.count() == 0:
            db.session.add_all([
                Offer(title="Weekend Special", description="15% off on all pizza orders.", discount_percent=15, active=True),
                Offer(title="Student Deal", description="10% off orders above Rs. 800.", discount_percent=10, active=True),
                Offer(title="New Customer Offer", description="20% off on your first order.", discount_percent=20, active=True),
            ])

        # ---- Sample reviews -----------------------------------------------
        if Review.query.count() == 0:
            db.session.add_all([
                Review(customer_name="Ayesha K.", rating=5, comment="Fast delivery and the zinger burger was amazing!"),
                Review(customer_name="Bilal A.", rating=4, comment="Great taste, chatbot ordering was super convenient."),
                Review(customer_name="Sana M.", rating=5, comment="Best fast food in town, FoodBot made ordering so easy."),
            ])

        db.session.commit()
