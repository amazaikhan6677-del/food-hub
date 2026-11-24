/* =========================================================
   FoodHub - main.js
   Shared helpers + menu page logic
   ========================================================= */

// ---------- Toast notifications ----------
function fhToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return alert(message);
  const id = "t" + Date.now();
  const icon = type === "success" ? "fa-circle-check" : type === "danger" ? "fa-circle-exclamation" : "fa-circle-info";
  const bg = type === "success" ? "text-bg-success" : type === "danger" ? "text-bg-danger" : "text-bg-primary";
  const el = document.createElement("div");
  el.className = `toast align-items-center ${bg} border-0`;
  el.id = id;
  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body"><i class="fa-solid ${icon} me-2"></i>${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(el);
  const toast = new bootstrap.Toast(el, { delay: 3000 });
  toast.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

// ---------- Fetch helpers ----------
async function fhFetch(url, options = {}) {
  const opts = Object.assign({ headers: { "Content-Type": "application/json" } }, options);
  const res = await fetch(url, opts);
  let data;
  try { data = await res.json(); } catch (e) { data = { success: false, message: "Server error." }; }
  return data;
}

function fhMoney(n) {
  return "Rs. " + Number(n || 0).toLocaleString("en-PK", { maximumFractionDigits: 0 });
}

// ---------- Update navbar cart badge ----------
function fhUpdateCartBadge(cart) {
  const badge = document.getElementById("navCartCount");
  if (!badge) return;
  const count = (cart.items || []).reduce((s, i) => s + i.quantity, 0);
  badge.textContent = count;
}

// ---------- Add to cart (used across pages) ----------
async function fhAddToCart(foodId, quantity = 1) {
  const data = await fhFetch("/api/cart/add", {
    method: "POST",
    body: JSON.stringify({ food_id: foodId, quantity }),
  });
  if (data.success) {
    fhToast("Item added to cart!", "success");
    fhUpdateCartBadge(data.cart);
  } else {
    fhToast(data.message || "Could not add item.", "danger");
  }
  return data;
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".add-to-cart-btn");
  if (btn) {
    fhAddToCart(parseInt(btn.dataset.id, 10));
  }
});

// Page-specific code runs after the DOM is ready, so that the inline
// <script> that sets window.FH_PAGE (placed after this file) has already run.
document.addEventListener("DOMContentLoaded", function () {
// =========================================================
// MENU PAGE LOGIC
// =========================================================
if (window.FH_PAGE === "menu") {
  let allItems = [];
  let currentCategory = "all";

  const grid = document.getElementById("menuGrid");
  const emptyState = document.getElementById("menuEmpty");
  const template = document.getElementById("foodCardTemplate");
  const searchInput = document.getElementById("menuSearch");
  const priceFilter = document.getElementById("priceFilter");
  const priceFilterVal = document.getElementById("priceFilterVal");
  const sortFilter = document.getElementById("sortFilter");
  const tabs = document.querySelectorAll(".fh-cat-tab");

  async function loadMenu() {
    try {
      const data = await fhFetch("/api/menu");
      if (data.success && data.items && data.items.length > 0) {
        allItems = data.items;
        renderMenu();
      } else if (data.success && data.items && data.items.length === 0) {
        grid.innerHTML = "";
        emptyState.classList.remove("d-none");
        emptyState.querySelector("p").textContent =
          "No menu items found in the database. If this is unexpected, delete foodhub.db and restart the server so it reseeds sample data.";
      } else {
        throw new Error(data.message || "Unknown error from /api/menu");
      }
    } catch (err) {
      grid.innerHTML = `<div class="col-12 text-center text-danger py-5">
        <i class="fa-solid fa-triangle-exclamation fa-2x mb-3"></i>
        <p>Couldn't load the menu: ${err.message}</p>
        <p class="text-muted small">Open the browser console (F12) for details, and make sure the Flask server is running.</p>
      </div>`;
      console.error("FoodHub menu load error:", err);
    }
  }

  function renderMenu() {
    let items = allItems.slice();

    if (currentCategory !== "all") {
      items = items.filter((i) => i.category === currentCategory);
    }
    const q = (searchInput.value || "").toLowerCase().trim();
    if (q) {
      items = items.filter((i) => i.name.toLowerCase().includes(q));
    }
    const maxPrice = parseInt(priceFilter.value, 10);
    items = items.filter((i) => i.price <= maxPrice);

    if (sortFilter.value === "price_asc") items.sort((a, b) => a.price - b.price);
    if (sortFilter.value === "price_desc") items.sort((a, b) => b.price - a.price);
    if (sortFilter.value === "rating") items.sort((a, b) => b.rating - a.rating);

    grid.innerHTML = "";
    if (items.length === 0) {
      emptyState.classList.remove("d-none");
      return;
    }
    emptyState.classList.add("d-none");

    items.forEach((item) => {
      const node = template.content.cloneNode(true);
      node.querySelector(".fc-name").textContent = item.name;
      node.querySelector(".fc-desc").textContent = item.description;
      node.querySelector(".fc-category").textContent = item.category;
      node.querySelector(".fc-price").textContent = fhMoney(item.price);
      node.querySelector(".fc-rating").textContent = item.rating;
      const imgEl = node.querySelector(".fc-img");
      imgEl.src = item.image_url || "/static/images/placeholder.svg";
      imgEl.alt = item.name;
      const addBtn = node.querySelector(".fc-add");
      const buyBtn = node.querySelector(".fc-buy");
      addBtn.dataset.id = item.id;
      buyBtn.dataset.id = item.id;

      if (!item.is_available) {
        node.querySelector(".fc-unavailable").classList.remove("d-none");
        addBtn.disabled = true;
        buyBtn.disabled = true;
        addBtn.classList.add("disabled");
        buyBtn.classList.add("disabled");
      }

      addBtn.addEventListener("click", () => fhAddToCart(item.id));
      buyBtn.addEventListener("click", async () => {
        await fhAddToCart(item.id);
        window.location.href = "/cart";
      });

      grid.appendChild(node);
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      currentCategory = tab.dataset.category;
      renderMenu();
    });
  });

  searchInput.addEventListener("input", renderMenu);
  sortFilter.addEventListener("change", renderMenu);
  priceFilter.addEventListener("input", () => {
    priceFilterVal.textContent = priceFilter.value;
    renderMenu();
  });

  loadMenu();
}

// =========================================================
// CUSTOMER ORDERS (dashboard) PAGE LOGIC
// =========================================================
if (window.FH_PAGE === "orders") {
  async function loadOrders() {
    const data = await fhFetch("/api/orders");
    const list = document.getElementById("ordersList");
    const emptyState = document.getElementById("ordersEmpty");
    if (!data.success || data.orders.length === 0) {
      emptyState.classList.remove("d-none");
      return;
    }
    list.innerHTML = data.orders.map((o) => `
      <div class="fh-order-card">
        <div class="d-flex justify-content-between flex-wrap">
          <div>
            <h6 class="mb-1">Order ${o.order_number}</h6>
            <small class="text-muted">${o.created_at} • ${o.items.length} item(s)</small>
          </div>
          <div class="text-end">
            <span class="fh-status-badge">${o.status}</span>
            <div class="fw-bold mt-1">${fhMoney(o.total)}</div>
          </div>
        </div>
        <div class="mt-2 d-flex justify-content-between align-items-center">
          <small class="text-muted">Payment: ${o.payment_method.toUpperCase()} — ${o.payment_status}</small>
          <a href="/tracking?order_number=${o.order_number}" class="btn btn-sm fh-btn-outline">Track Order</a>
        </div>
      </div>
    `).join("");
  }
  loadOrders();
}

// =========================================================
// TRACKING PAGE LOGIC
// =========================================================
if (window.FH_PAGE === "tracking") {
  const input = document.getElementById("trackOrderInput");
  const btn = document.getElementById("trackBtn");
  const resultBox = document.getElementById("trackResult");
  const notFoundBox = document.getElementById("trackNotFound");

  async function trackOrder() {
    const orderNumber = (input.value || "").trim();
    if (!orderNumber) {
      fhToast("Please enter an Order ID first.", "danger");
      return;
    }
    resultBox.classList.add("d-none");
    notFoundBox.classList.add("d-none");

    let data;
    try {
      data = await fhFetch(`/api/orders/${encodeURIComponent(orderNumber)}`);
    } catch (err) {
      console.error("FoodHub tracking error:", err);
      notFoundBox.classList.remove("d-none");
      notFoundBox.querySelector("p").textContent = "Something went wrong reaching the server. Check the browser console (F12) and make sure the Flask server is running.";
      return;
    }
    if (!data || !data.success) {
      notFoundBox.classList.remove("d-none");
      notFoundBox.querySelector("p").textContent = (data && data.message) || "Invalid Order ID. Please double-check it.";
      return;
    }
    const o = data.order;
    document.getElementById("trkOrderNumber").textContent = o.order_number;
    document.getElementById("trkDate").textContent = o.created_at;
    document.getElementById("trkStatusBadge").textContent = o.status;
    document.getElementById("trkTotal").textContent = fhMoney(o.total);
    document.getElementById("trkPayment").textContent = `${o.payment_method.toUpperCase()} (${o.payment_status})`;
    document.getElementById("trkAddress").textContent = `${o.address}, ${o.city}`;
    document.getElementById("trkItems").innerHTML = o.items.map(
      (i) => `<li>${i.quantity} x ${i.name} — ${fhMoney(i.line_total)}</li>`
    ).join("");

    const flow = o.status_flow;
    const currentIndex = flow.indexOf(o.status);
    document.getElementById("trkTimeline").innerHTML = flow.map((step, idx) => {
      let cls = "";
      if (o.status === "Cancelled") cls = "";
      else if (idx < currentIndex) cls = "done";
      else if (idx === currentIndex) cls = "current";
      return `<div class="tl-step ${cls}">
                <div class="tl-dot"><i class="fa-solid ${idx <= currentIndex ? 'fa-check' : 'fa-circle'}"></i></div>
                <div class="tl-label">${step}</div>
              </div>`;
    }).join("");

    resultBox.classList.remove("d-none");
  }

  btn.addEventListener("click", trackOrder);
  input.addEventListener("keypress", (e) => { if (e.key === "Enter") trackOrder(); });

  if (window.FH_INITIAL_ORDER) {
    input.value = window.FH_INITIAL_ORDER;
    trackOrder();
  }
}

});
