"""
order_service.py

Single source of truth for turning a Cart into a REAL, permanently saved
Order row in the SQLite database. Used by both:
  - the checkout page (/api/orders/create in app.py)
  - FoodBot, so an order placed via chat is the exact same real database
    record as one placed via the checkout form (same table, same fields,
    same payment handling — nothing about it is faked or mocked).
"""

from database import db, Order, OrderItem, Payment
from payment_service import process_payment


def create_order_from_cart(cart, user_id, data, delivery_fee, free_delivery_threshold):
    """
    cart: a Cart model instance (must have .items)
    user_id: logged-in user's id, or None for guest
    data: dict with name, phone, address, city, payment_method,
          and optionally email, instructions, card_last4, mobile_number
    Returns: (True, order) on success, (False, error_message) on failure.
    This always writes a real row to the `orders`, `order_items`, and
    `payments` tables — the same tables the admin panel reads from.
    """
    if not cart.items:
        return False, "Your cart is empty."

    required = ["name", "phone", "address", "city", "payment_method"]
    for field in required:
        if not data.get(field):
            return False, f"Missing required field: {field}"

    for ci in cart.items:
        if not ci.food or not ci.food.is_available:
            return False, f"'{ci.food.name if ci.food else 'An item'}' is no longer available."

    totals = cart.totals(delivery_fee, free_delivery_threshold)

    order = Order(
        order_number=Order.generate_order_number(),
        user_id=user_id,
        customer_name=data["name"],
        phone=data["phone"],
        email=data.get("email", ""),
        address=data["address"],
        city=data["city"],
        instructions=data.get("instructions", ""),
        subtotal=totals["subtotal"],
        delivery_fee=totals["delivery_fee"],
        discount=totals["discount"],
        total=totals["total"],
        payment_method=data["payment_method"],
        payment_status="Pending",
        status="Order Received",
    )
    db.session.add(order)
    db.session.flush()  # get order.id before commit

    for ci in cart.items:
        db.session.add(OrderItem(order_id=order.id, food_id=ci.food_id,
                                  name=ci.food.name, price=ci.food.price, quantity=ci.quantity))

    result = process_payment(
        method=data["payment_method"],
        amount=totals["total"],
        card_last4=data.get("card_last4"),
        mobile_number=data.get("mobile_number"),
    )
    payment = Payment(
        order_id=order.id,
        method=data["payment_method"],
        status=result["status"],
        transaction_id=result["transaction_id"],
        amount=totals["total"],
        is_demo=True,
    )
    db.session.add(payment)
    order.payment_status = result["status"]

    if result["status"] == "Failed":
        db.session.rollback()
        return False, "Payment failed. Please try again or choose Cash on Delivery."

    if order.payment_status == "Paid":
        order.status = "Order Confirmed"

    for ci in list(cart.items):
        db.session.delete(ci)

    db.session.commit()
    return True, order
