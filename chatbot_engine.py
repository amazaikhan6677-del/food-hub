"""
chatbot_engine.py
FoodBot's conversation engine.

- Reads real menu/cart/order data from the database (never hard-coded).
- Fuzzy-matches food names so small typos or partial names still work
  ("zinger", "zinger burgr", "chiken shawarma" all resolve correctly).
- Understands multiple items in one message ("2 zinger burgers and a coke").
- Can walk a customer through a REAL checkout entirely in the chat window:
  name -> phone -> address -> city -> payment method -> confirm, then
  places a genuine order through order_service.create_order_from_cart —
  the exact same function the checkout page uses. Nothing about an order
  placed via chat is fake; it's the same row in the same `orders` table.
"""

import re
import json
import difflib

from database import db, Category, FoodItem, Order, Cart, CartItem, User, ChatState
from order_service import create_order_from_cart

WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

PAYMENT_ALIASES = {
    "cod": "cod", "cash": "cod", "cash on delivery": "cod",
    "card": "card", "credit card": "card", "debit card": "card", "visa": "card", "mastercard": "card",
    "jazzcash": "jazzcash", "jazz cash": "jazzcash", "jazz": "jazzcash",
    "easypaisa": "easypaisa", "easy paisa": "easypaisa", "easy": "easypaisa",
}


# ---------------------------------------------------------------------------
# Cart / state helpers
# ---------------------------------------------------------------------------
def _get_or_create_cart(session_id):
    cart = Cart.query.filter_by(session_id=session_id).first()
    if not cart:
        cart = Cart(session_id=session_id)
        db.session.add(cart)
        db.session.commit()
    return cart


def _get_state(session_id):
    st = ChatState.query.get(session_id)
    if not st:
        st = ChatState(session_id=session_id, stage="idle", data="{}")
        db.session.add(st)
        db.session.commit()
    return st


def _save_state(st, stage, data_dict):
    st.stage = stage
    st.data = json.dumps(data_dict)
    db.session.commit()


def _reset_state(st):
    st.stage = "idle"
    st.data = "{}"
    db.session.commit()


# ---------------------------------------------------------------------------
# Fuzzy food matching
# ---------------------------------------------------------------------------
def _all_available_items():
    return FoodItem.query.filter_by(is_available=True).all()


def _best_food_match(text):
    """Return the single best-matching FoodItem for a free-text snippet, or None."""
    text_norm = text.lower().strip()
    if not text_norm:
        return None
    items = _all_available_items()
    if not items:
        return None

    # 1) exact / substring match
    for item in items:
        if item.name.lower() in text_norm or text_norm in item.name.lower():
            return item

    # 2) word-overlap score
    best, best_score = None, 0
    for item in items:
        words = [w for w in re.split(r"\W+", item.name.lower()) if len(w) > 2]
        score = sum(1 for w in words if w in text_norm)
        if score > best_score:
            best, best_score = item, score
    if best:
        return best

    # 3) fuzzy string similarity (typo tolerance)
    names = {item.name.lower(): item for item in items}
    close = difflib.get_close_matches(text_norm, names.keys(), n=1, cutoff=0.55)
    if close:
        return names[close[0]]
    return None


def _find_food_by_name(text):
    return _best_food_match(text)


def _parse_item_requests(text):
    """
    Split a message like "2 zinger burgers and a coke, plus fries" into
    [(quantity, matched_FoodItem), ...], skipping segments that don't
    resolve to a real menu item.
    """
    segments = re.split(r"\band\b|,|\+", text.lower())
    results = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        qty = 1
        m = re.match(r"^(\d+)\s*x?\s*(.*)$", seg)
        if m and m.group(1):
            qty = int(m.group(1))
            seg = m.group(2)
        else:
            words = seg.split()
            if words and words[0] in WORD_NUMBERS:
                qty = WORD_NUMBERS[words[0]]
                seg = " ".join(words[1:])
        food = _best_food_match(seg)
        if food:
            results.append((max(1, qty), food))
    return results


def _match_payment_method(text):
    text = text.lower().strip()
    for phrase, method in PAYMENT_ALIASES.items():
        if phrase in text:
            return method
    close = difflib.get_close_matches(text, PAYMENT_ALIASES.keys(), n=1, cutoff=0.5)
    if close:
        return PAYMENT_ALIASES[close[0]]
    return None


def _format_items_list(items, limit=8):
    if not items:
        return "Sorry, I couldn't find any items in that category right now."
    lines = []
    for f in items[:limit]:
        avail = "" if f.is_available else " (currently unavailable)"
        lines.append(f"• {f.name} — Rs. {f.price:.0f}{avail}")
    return "\n".join(lines)


def _cart_summary_text(cart, delivery_fee, free_delivery_threshold):
    totals = cart.totals(delivery_fee, free_delivery_threshold)
    lines = [f"{i.quantity} x {i.food.name} — Rs. {i.food.price * i.quantity:.0f}" for i in cart.items if i.food]
    text = "\n".join(lines)
    text += (f"\n\nSubtotal: Rs. {totals['subtotal']:.0f}\nDelivery: Rs. {totals['delivery_fee']:.0f}"
             f"\nTotal: Rs. {totals['total']:.0f}")
    return text


# ---------------------------------------------------------------------------
# In-chat checkout flow (real orders — same DB table as the checkout page)
# ---------------------------------------------------------------------------
def _start_checkout(cart, session_id, user_id, delivery_fee, free_delivery_threshold):
    st = _get_state(session_id)

    if not cart.items:
        return {"reply": "Your cart is empty — add something first, then say 'place order'.", "action": "none"}

    user = User.query.get(user_id) if user_id else None
    data = {}
    if user:
        data["name"] = user.name
        data["phone"] = user.phone
        data["email"] = user.email
        stage = "awaiting_address"
        reply = (f"Great, {user.name.split(' ')[0]}! Let's get this order placed. 🧾\n\n"
                 f"{_cart_summary_text(cart, delivery_fee, free_delivery_threshold)}\n\n"
                 "What's your delivery address?")
    else:
        stage = "awaiting_name"
        reply = ("Great! Let's get you checked out. 🧾\n\n"
                 f"{_cart_summary_text(cart, delivery_fee, free_delivery_threshold)}\n\n"
                 "First, what's your full name?")

    _save_state(st, stage, data)
    return {"reply": reply, "action": "checkout_started"}


def _handle_checkout_flow(text, st, cart, session_id, user_id, delivery_fee, free_delivery_threshold):
    lower = text.lower().strip()
    data = json.loads(st.data or "{}")

    if lower in ("cancel", "stop", "never mind", "nevermind", "abort"):
        _reset_state(st)
        return {"reply": "No problem, I've cancelled the checkout. Your cart is still saved — just say "
                          "'place order' whenever you're ready.", "action": "none"}

    if st.stage == "awaiting_name":
        if len(text.strip()) < 2:
            return {"reply": "Please enter your full name to continue (or say 'cancel').", "action": "none"}
        data["name"] = text.strip()
        _save_state(st, "awaiting_phone", data)
        return {"reply": f"Thanks, {data['name'].split(' ')[0]}! What's the best phone number to reach you on?", "action": "none"}

    if st.stage == "awaiting_phone":
        digits = re.sub(r"\D", "", text)
        if len(digits) < 7:
            return {"reply": "That doesn't look like a valid phone number — please try again (or say 'cancel').", "action": "none"}
        data["phone"] = text.strip()
        _save_state(st, "awaiting_address", data)
        return {"reply": "Got it. What's your delivery address?", "action": "none"}

    if st.stage == "awaiting_address":
        if len(text.strip()) < 4:
            return {"reply": "Please enter a valid delivery address (or say 'cancel').", "action": "none"}
        data["address"] = text.strip()
        _save_state(st, "awaiting_city", data)
        return {"reply": "And which city is that in?", "action": "none"}

    if st.stage == "awaiting_city":
        if len(text.strip()) < 2:
            return {"reply": "Please enter a valid city name (or say 'cancel').", "action": "none"}
        data["city"] = text.strip()
        _save_state(st, "awaiting_payment", data)
        return {"reply": "How would you like to pay? Cash on Delivery, Card, JazzCash, or Easypaisa?", "action": "none"}

    if st.stage == "awaiting_payment":
        method = _match_payment_method(text)
        if not method:
            return {"reply": "Sorry, please choose one of: Cash on Delivery, Card, JazzCash, or Easypaisa.", "action": "none"}
        data["payment_method"] = method
        _save_state(st, "awaiting_confirmation", data)
        method_label = {"cod": "Cash on Delivery", "card": "Card", "jazzcash": "JazzCash", "easypaisa": "Easypaisa"}[method]
        summary = _cart_summary_text(cart, delivery_fee, free_delivery_threshold)
        reply = (f"Here's your order summary:\n\n{summary}\n\n"
                 f"📍 Deliver to: {data.get('address')}, {data.get('city')}\n"
                 f"💳 Payment: {method_label}\n\n"
                 "Type 'yes' to confirm and place your order, or 'cancel' to abort.")
        return {"reply": reply, "action": "none"}

    if st.stage == "awaiting_confirmation":
        if lower in ("yes", "yep", "yeah", "confirm", "ok", "okay", "sure"):
            ok, result = create_order_from_cart(cart, user_id, data, delivery_fee, free_delivery_threshold)
            _reset_state(st)
            if ok:
                order = result
                return {
                    "reply": (f"🎉 Order placed! Your Order ID is {order.order_number}.\n"
                              f"Total: Rs. {order.total:.0f} | Payment: {order.payment_status}\n\n"
                              "You can track it anytime by saying 'track order' with this ID, "
                              "or on the Track Order page."),
                    "action": "order_placed",
                    "order": order.to_dict(),
                }
            return {"reply": f"Sorry, I couldn't place your order: {result}. Please try 'place order' again.", "action": "none"}
        return {"reply": "Please reply 'yes' to confirm your order, or 'cancel' to abort.", "action": "none"}

    # Shouldn't reach here — safety fallback
    _reset_state(st)
    return {"reply": "Let's start over — how can I help?", "action": "none"}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def handle_message(message, session_id, user_id=None, delivery_fee=150.0, free_delivery_threshold=2000.0):
    """
    Returns: { "reply": str, "action": str, "order": dict|None }
    'action' lets the frontend refresh cart/order UI when needed:
      none | cart_updated | goto_checkout | checkout_started | order_placed
    """
    text = (message or "").strip()
    lower = text.lower()
    cart = _get_or_create_cart(session_id)
    st = _get_state(session_id)

    # ---- If mid-checkout conversation, keep collecting answers ------------
    if st.stage != "idle":
        result = _handle_checkout_flow(text, st, cart, session_id, user_id, delivery_fee, free_delivery_threshold)
        result.setdefault("order", None)
        return result

    # ---- Greetings ------------------------------------------------------
    if lower in ("hi", "hello", "hey", "salam", "assalam o alaikum", "asalam o alaikum"):
        return {
            "reply": "Hi! 👋 I'm FoodBot. Try things like 'zinger burger', 'show menu', 'show deals', "
                     "'show cart', or 'place order' — I can take your whole order right here in chat!",
            "action": "none", "order": None,
        }

    # ---- Show full menu ---------------------------------------------------
    if "show menu" in lower or lower == "menu":
        cats = Category.query.all()
        lines = [f"{c.name} ({FoodItem.query.filter_by(category_id=c.id, is_available=True).count()} items)"
                  for c in cats]
        return {"reply": "Here are our menu categories:\n" + "\n".join(lines) +
                          "\n\nTry: 'show burgers' or 'show deals'.", "action": "none", "order": None}

    # ---- Show deals -----------------------------------------------------
    if ("deal" in lower and "show" in lower) or lower == "deals":
        deals = FoodItem.query.filter_by(is_deal=True, is_available=True).all()
        return {"reply": "🔥 Today's Deals:\n" + _format_items_list(deals), "action": "none", "order": None}

    # ---- Show cheap food --------------------------------------------------
    if "cheap" in lower:
        cheap_items = FoodItem.query.filter_by(is_available=True).order_by(FoodItem.price.asc()).limit(6).all()
        return {"reply": "💰 Our most affordable items:\n" + _format_items_list(cheap_items), "action": "none", "order": None}

    # ---- Show <category> --------------------------------------------------
    if lower.startswith("show "):
        cat_query = lower.replace("show ", "").strip().rstrip("s")
        category = Category.query.filter(Category.name.ilike(f"%{cat_query}%")).first()
        if not category:
            names = {c.name.lower(): c for c in Category.query.all()}
            close = difflib.get_close_matches(cat_query, names.keys(), n=1, cutoff=0.5)
            category = names[close[0]] if close else None
        if category:
            items = FoodItem.query.filter_by(category_id=category.id, is_available=True).all()
            return {"reply": f"Here's our {category.name} menu:\n" + _format_items_list(items),
                    "action": "none", "order": None}

    # ---- Show cart ----------------------------------------------------
    if "show cart" in lower or lower == "cart" or "view cart" in lower:
        if not cart.items:
            return {"reply": "Your cart is empty. Try 'add zinger burger' to get started!",
                    "action": "cart_updated", "order": None}
        reply = "🛒 Your Cart:\n" + _cart_summary_text(cart, delivery_fee, free_delivery_threshold)
        return {"reply": reply, "action": "cart_updated", "order": None}

    # ---- Calculate total --------------------------------------------------
    if "total" in lower or "calculate" in lower:
        totals = cart.totals(delivery_fee, free_delivery_threshold)
        return {"reply": f"Your current total is Rs. {totals['total']:.0f} "
                          f"(Subtotal Rs. {totals['subtotal']:.0f} + Delivery Rs. {totals['delivery_fee']:.0f}).",
                "action": "cart_updated", "order": None}

    # ---- Remove item --------------------------------------------------
    if lower.startswith("remove") or "remove item" in lower:
        food = _find_food_by_name(lower)
        if food:
            ci = CartItem.query.filter_by(cart_id=cart.id, food_id=food.id).first()
            if ci:
                db.session.delete(ci)
                db.session.commit()
                return {"reply": f"Removed {food.name} from your cart.", "action": "cart_updated", "order": None}
            return {"reply": f"{food.name} isn't in your cart.", "action": "none", "order": None}
        return {"reply": "Which item would you like to remove? e.g. 'remove zinger burger'.", "action": "none", "order": None}

    # ---- Place order (starts the real in-chat checkout) ------------------
    if "place order" in lower or "checkout" in lower or lower in ("order now", "order"):
        return _start_checkout(cart, session_id, user_id, delivery_fee, free_delivery_threshold)

    # ---- Track order --------------------------------------------------
    if "track" in lower:
        match = re.search(r"(FH[0-9A-Za-z]{6,10})", text, re.IGNORECASE)
        if match:
            order = Order.query.filter_by(order_number=match.group(1).upper()).first()
            if order:
                return {"reply": f"Order {order.order_number} status: {order.status}. "
                                  f"Payment: {order.payment_status}. Total: Rs. {order.total:.0f}.",
                        "action": "none", "order": order.to_dict()}
            return {"reply": "I couldn't find that order ID. Please double-check it.", "action": "none", "order": None}
        return {"reply": "Please share your Order ID (e.g. FH1A2B3C4D) so I can track it, "
                          "or use the Track Order page.", "action": "none", "order": None}

    # ---- Cancel order --------------------------------------------------
    if "cancel order" in lower:
        match = re.search(r"(FH[0-9A-Za-z]{6,10})", text, re.IGNORECASE)
        if match:
            order = Order.query.filter_by(order_number=match.group(1).upper()).first()
            if order and order.status in ("Order Received", "Order Confirmed"):
                order.status = "Cancelled"
                db.session.commit()
                return {"reply": f"Order {order.order_number} has been cancelled.", "action": "none", "order": None}
            if order:
                return {"reply": f"Sorry, order {order.order_number} is already '{order.status}' and can't be cancelled.",
                        "action": "none", "order": None}
            return {"reply": "I couldn't find that order ID.", "action": "none", "order": None}
        return {"reply": "Please share the Order ID you'd like to cancel.", "action": "none", "order": None}

    # ---- Confirmations with nothing pending -------------------------------
    if lower in ("yes", "yep", "yeah", "sure", "ok", "okay"):
        return {"reply": "Great — anything else? You can say 'show cart' or 'place order'.", "action": "none", "order": None}

    # ---- Add item(s) — supports multiple items in one message ------------
    requests = _parse_item_requests(text) if ("add" in lower or _best_food_match(lower)) else []
    if requests:
        added_lines = []
        for qty, food in requests:
            if not food.is_available:
                added_lines.append(f"⚠️ {food.name} is currently out of stock.")
                continue
            ci = CartItem.query.filter_by(cart_id=cart.id, food_id=food.id).first()
            if ci:
                ci.quantity += qty
            else:
                ci = CartItem(cart_id=cart.id, food_id=food.id, quantity=qty)
                db.session.add(ci)
            added_lines.append(f"🍽️ Added {qty} x {food.name} (Rs. {food.price:.0f} each)")
        db.session.commit()
        added_lines.append("\nSay 'show cart' to review or 'place order' to checkout.")
        return {"reply": "\n".join(added_lines), "action": "cart_updated", "order": None}

    if "add" in lower:
        return {"reply": "I couldn't find that item on our menu. Try 'show menu' to see what's available.",
                "action": "none", "order": None}

    # ---- Fallback -------------------------------------------------------
    return {
        "reply": "I'm not sure I understood that. You can try: 'show menu', 'zinger burger', "
                 "'2 burgers and a coke', 'show cart', 'place order', or 'track order FH1234ABCD'.",
        "action": "none", "order": None,
    }
