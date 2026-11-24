# 🍔 FoodHub — Fast Food Ordering Chatbot

FoodHub is a full-stack fast-food ordering website with a working AI-style
chatbot ("FoodBot"), shopping cart, checkout with a demo payment system,
order tracking, and a complete admin panel — built with **Flask + SQLite**
on the backend and **HTML/CSS/vanilla JS (Bootstrap 5)** on the frontend.

---

> **Note on "demo":** The database is 100% real — every order (whether
> placed via the checkout page or through FoodBot) is written permanently
> to `foodhub.db` and shows up immediately in the admin panel, order
> history, and tracking page. The only thing simulated is **payment
> processing** (no real card/JazzCash/Easypaisa transaction is made,
> because that requires a paid merchant account with a real payment
> gateway) — see section 12 for how to plug in a real one.

---

## 1. Project Description

FoodHub lets customers browse a fast-food menu, chat with FoodBot to add
items to their cart conversationally, check out with several payment
options (Cash on Delivery, Card, JazzCash, Easypaisa — all in **Demo
Payment Mode**), and track their order status in real time. Admins get a
full dashboard to manage orders, menu items, customers, payments and
offers, plus sales analytics charts.

## 2. Features

- Modern responsive homepage with popular foods, deals, and reviews
- Full menu with search, category filters, and price filter
- **FoodBot** chatbot — a real conversational engine (fuzzy name matching,
  typo tolerance, multi-item requests like "2 zinger burgers and a coke")
  that can walk a customer through an entire real checkout — name, phone,
  address, city, payment method, confirmation — right inside the chat
  window, placing a genuine order in the database (the same order the
  admin panel and tracking page see). Also understands "show menu",
  "show cart", "track order FH1234ABCD", "cancel order", etc.
- Real shopping cart (session + database backed), persists across pages
- Customer registration/login with hashed passwords
- Checkout with delivery details + 4 payment methods (demo mode)
- Order system with a full status pipeline and live tracking page
- Real food **photographs** for every menu item by default (sourced from
  Unsplash, free to use under the Unsplash License), with full admin
  control: upload your own real photo for any item, replace it, or
  remove it (resets to the category's default photo) — all from the
  Menu Management page
- Admin panel: dashboard analytics (Chart.js), full order management
  (one-click **Approve** / **Reject**, plus a granular status dropdown
  for Preparing/Ready/Out for Delivery/Delivered), menu CRUD with an
  Edit modal (name, price, description, category, image), customer
  management, payment log, offers CRUD
- Friendly error handling everywhere (no raw stack traces to users)

## 3. Technologies

- **Backend:** Python 3, Flask, Flask-SQLAlchemy
- **Database:** SQLite (auto-created on first run, seeded with sample data)
- **Frontend:** HTML5, CSS3, vanilla JavaScript, Bootstrap 5, Font Awesome
- **Charts:** Chart.js (admin analytics)

## 4. Folder Structure

```text
FoodHub/
├── app.py                 # Main Flask app: routes + REST API
├── database.py             # SQLAlchemy models + sample data seeding
├── chatbot_engine.py        # FoodBot conversation engine (fuzzy match + in-chat checkout)
├── order_service.py         # Shared real order-creation logic (checkout page + chatbot)
├── payment_service.py       # Demo payment abstraction layer
├── config.py                # App configuration
├── requirements.txt
├── README.md
├── foodhub.db               # SQLite database (auto-created on first run)
├── templates/                # Jinja2 HTML templates
│   ├── index.html, menu.html, cart.html, checkout.html, ...
│   └── admin/                # Admin panel templates
├── static/
│   ├── css/ (style.css, chatbot.css, admin.css)
│   ├── js/  (main.js, chatbot.js, cart.js, checkout.js, admin.js)
│   └── images/
└── uploads/                  # Admin-uploaded food images
```

## 5. Installation

Make sure you have **Python 3.9+** installed. Then open a terminal in the
`FoodHub` folder (this works directly in PyCharm's or VS Code's terminal).

## 6. Create a Python Virtual Environment

```bash
python -m venv venv
```

Activate it:

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

## 7. Install Requirements

```bash
pip install -r requirements.txt
```

## 8. Database Setup

Nothing manual required — the SQLite database (`foodhub.db`) and all
tables are created automatically the first time you run the app, and
sample menu items, an admin account, and offers are seeded automatically.

## 9. Run the Flask App

```bash
python app.py
```

Then open your browser at:

```text
http://127.0.0.1:5000/
```

## 10. Admin Login

Go to `http://127.0.0.1:5000/admin/login`

- **Username:** `admin`
- **Password:** `admin123`

⚠️ Change these credentials before deploying anywhere public (edit
`DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` in `config.py`, or
update the `Admin` row directly, before your first run — or update the
password hash afterwards).

## 11. Customer Login

Register a new account at `http://127.0.0.1:5000/register`, or just
browse and order as a guest — the cart works for guests too. Guest carts
are merged into your account automatically when you log in.

## 12. Demo Payment Mode

This project ships with a **Demo Payment Mode** (see `payment_service.py`).
No real payment gateway is called and **no card number or CVV is ever
transmitted or stored** — only the last 4 digits of a card are kept for
display purposes, and only for card payments. Card/JazzCash/Easypaisa
payments are simulated as instantly "Paid"; Cash on Delivery orders are
marked "Pending" until delivery.

## 13. How to Replace Demo Payment with a Real Gateway

1. Open `payment_service.py`.
2. Replace the body of `process_payment()` with a real call to your
   gateway's API/SDK (e.g. Stripe PaymentIntents, PayFast, or the
   JazzCash/Easypaisa merchant APIs).
3. Keep the same return shape — `{"status": "Paid"/"Pending"/"Failed",
   "transaction_id": str}` — so nothing else in the app needs to change.
4. Store your API keys as environment variables, never directly in code.
5. Add proper webhook/callback verification for asynchronous gateways.

## 14. How to Customize the Menu

- Easiest: log in to the **Admin Panel → Menu**, click the pencil (Edit)
  icon on any item to change its name, price, description, category or
  photo, use "Add New Food Item" (with image upload) to add a new one, or
  toggle availability/deals/popular flags — all changes save to the
  database instantly.
- The default menu images are real Unsplash photos, hotlinked by URL (see
  `CATEGORY_DEFAULT_IMAGES` in `database.py`) so no binary images ship in
  the project; they load directly from Unsplash's CDN when a page opens,
  which requires the computer running the app to have internet access.
  Uploading your own photo for an item replaces this with a locally
  stored file instead.
- Alternatively, edit the sample data list inside `seed_data()` in
  `database.py` before the first run (only runs when the `food_items`
  table is empty).

## 15. How to Deploy

For a simple production deployment:

1. Set `debug=False` in `app.py` (or use an environment variable).
2. Set a strong `FOODHUB_SECRET_KEY` environment variable.
3. Serve the app with a production WSGI server, e.g.:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8000 app:app
   ```
4. Put a reverse proxy (Nginx) in front of Gunicorn and serve `/static`
   and `/uploads` directly from Nginx for better performance.
5. For anything beyond a demo, swap SQLite for PostgreSQL/MySQL by
   changing `SQLALCHEMY_DATABASE_URI` in `config.py`, and connect a real
   payment gateway as described above.

---

## API Routes Reference

```text
GET  /api/menu                          Get menu items (filters: category, search, max_price)
POST /api/register                      Create a customer account
POST /api/login                         Customer login
GET  /api/cart                          Get current cart
POST /api/cart/add                      Add item to cart
POST /api/cart/update                   Update item quantity
POST /api/cart/remove                   Remove item from cart
POST /api/orders/create                 Place an order (checkout)
GET  /api/orders                        Logged-in user's order history
GET  /api/orders/<order_number>         Get order details (for tracking)
POST /api/orders/<order_number>/status  Cancel an order (customer)
POST /api/payment                       Standalone demo payment call
POST /api/chatbot                       Send a message to FoodBot

GET  /api/admin/stats                   Dashboard analytics
GET  /api/admin/orders                  All orders (filter by status)
POST /api/admin/orders/<id>/status      Admin: update order status
GET/POST /api/admin/menu                List / create menu items (POST accepts an image upload)
PUT/DELETE /api/admin/menu/<id>         Update / delete a menu item
                                         (PUT accepts multipart form data with a new image file
                                         and/or remove_image=true to reset to the default photo)
POST /api/admin/orders/<id>/approve     One-click approve (Order Received -> Order Confirmed)
POST /api/admin/orders/<id>/reject      One-click reject/cancel (optional JSON {"reason": "..."})
GET  /api/admin/customers               List / search customers
POST /api/admin/customers/<id>/toggle   Enable/disable a customer
GET  /api/admin/payments                All payment transactions
GET/POST /api/admin/offers              List / create offers
PUT/DELETE /api/admin/offers/<id>       Update / delete an offer
```

---

Built as a demo/educational full-stack project. Not affiliated with any
real payment provider — replace `payment_service.py` before handling
real money.


## 16. Deploying this project to Vercel (GitHub)

This repository has a root-level `app.py` exporting the Flask `app`
instance and a root-level `requirements.txt`. Vercel currently auto-detects
Flask projects, so no custom build command or `vercel.json` is required.

1. Push the **contents of this project folder** to a GitHub repository (so
   `app.py`, `requirements.txt`, `templates/`, and `static/` are at the
   repository root).
2. In Vercel, choose **Add New → Project**, import that GitHub repository,
   and deploy. Keep the project Root Directory as `./`.
3. In Project Settings → Environment Variables, set `FOODHUB_SECRET_KEY`
   to a long random secret. Also set `FOODHUB_ADMIN_USERNAME` and
   `FOODHUB_ADMIN_PASSWORD` if you want custom initial admin credentials.
4. Redeploy after adding or changing environment variables.

### Important Vercel limitations

- The app currently uses SQLite. On Vercel it is placed in `/tmp` because
  the deployed project directory is read-only. `/tmp` is **temporary and
  instance-local**, so users, orders, carts, menu changes, and other database
  data are not guaranteed to persist across cold starts or instances.
- Admin image uploads are also written to temporary `/tmp` storage and are
  not durable. Use object storage for permanent uploads.
- Therefore this Vercel package is suitable for a preview/demo, but **not
  production ordering with persistent customer/order data**. For a real
  public store, migrate SQLite to a managed PostgreSQL database and uploads
  to persistent object storage before launch.
- The bundled payment service is demo-only. Card, JazzCash, and Easypaisa
  payments are simulated; no real payment is collected.

Local development remains unchanged: run `python app.py` from this folder.
