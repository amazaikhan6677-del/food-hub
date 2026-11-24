/* =========================================================
   FoodHub - admin.js
   Admin panel: dashboard charts, orders, menu, customers,
   payments, offers management
   ========================================================= */

function adToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container || typeof bootstrap === "undefined") return alert(message);
  const bg = type === "success" ? "text-bg-success" : type === "danger" ? "text-bg-danger" : "text-bg-primary";
  const el = document.createElement("div");
  el.className = `toast align-items-center ${bg} border-0`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body"></div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  el.querySelector(".toast-body").textContent = message;
  container.appendChild(el);
  new bootstrap.Toast(el, { delay: 3000 }).show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

async function adFetch(url, options = {}) {
  const opts = Object.assign({ headers: { "Content-Type": "application/json" } }, options);
  const res = await fetch(url, opts);
  try { return await res.json(); } catch (e) { return { success: false, message: "Server error." }; }
}

function adMoney(n) {
  return "Rs. " + Number(n || 0).toLocaleString("en-PK", { maximumFractionDigits: 0 });
}

function statusClass(status) {
  const map = {
    "Order Received": "received", "Order Confirmed": "confirmed", "Preparing": "preparing",
    "Ready": "ready", "Out for Delivery": "out", "Delivered": "delivered", "Cancelled": "cancelled",
  };
  return map[status] || "received";
}

// Page-specific code runs after the DOM is ready, so that the inline
// <script> that sets window.FH_PAGE (placed after this file) has already run.
document.addEventListener("DOMContentLoaded", function () {
// =========================================================
// DASHBOARD
// =========================================================
if (window.FH_ADMIN_PAGE === "dashboard") {
  (async function () {
    const data = await adFetch("/api/admin/stats");
    if (!data.success) return;
    const s = data.stats;

    document.getElementById("statTotalOrders").textContent = s.total_orders;
    document.getElementById("statTodayOrders").textContent = s.todays_orders;
    document.getElementById("statRevenue").textContent = adMoney(s.total_revenue);
    document.getElementById("statCustomers").textContent = s.customers;
    document.getElementById("statPending").textContent = s.pending_orders;
    document.getElementById("statCompleted").textContent = s.completed_orders;

    document.getElementById("popularProductsList").innerHTML = s.popular_products.length
      ? s.popular_products.map((p, idx) => `
          <li class="d-flex justify-content-between border-bottom py-2">
            <span>${idx + 1}. ${p.name}</span><strong>${p.qty} sold</strong>
          </li>`).join("")
      : '<li class="text-muted">No sales yet.</li>';

    new Chart(document.getElementById("dailySalesChart"), {
      type: "line",
      data: {
        labels: s.daily_sales.map((d) => d.date.slice(5)),
        datasets: [{
          label: "Sales (Rs.)", data: s.daily_sales.map((d) => d.total),
          borderColor: "#e8342a", backgroundColor: "rgba(232,52,42,.1)", fill: true, tension: .3,
        }],
      },
      options: { plugins: { legend: { display: false } } },
    });

    new Chart(document.getElementById("paymentMethodChart"), {
      type: "doughnut",
      data: {
        labels: s.payment_methods.map((p) => p.method.toUpperCase()),
        datasets: [{ data: s.payment_methods.map((p) => p.count), backgroundColor: ["#e8342a", "#ff8a3d", "#1e1b1b", "#f5a623"] }],
      },
    });

    new Chart(document.getElementById("categoryChart"), {
      type: "bar",
      data: {
        labels: s.orders_by_category.map((c) => c.category),
        datasets: [{ label: "Items Sold", data: s.orders_by_category.map((c) => c.qty), backgroundColor: "#ff8a3d" }],
      },
      options: { plugins: { legend: { display: false } } },
    });
  })();
}

// =========================================================
// ORDERS
// =========================================================
if (window.FH_ADMIN_PAGE === "orders") {
  const tbody = document.getElementById("ordersTableBody");
  const filter = document.getElementById("orderStatusFilter");
  const statuses = ["Order Received", "Order Confirmed", "Preparing", "Ready", "Out for Delivery", "Delivered", "Cancelled"];

  async function loadOrders() {
    const status = filter.value;
    const data = await adFetch(`/api/admin/orders?status=${encodeURIComponent(status)}`);
    if (!data.success) return;
    tbody.innerHTML = data.orders.map((o) => `
      <tr>
        <td><strong>${o.order_number}</strong></td>
        <td>${o.customer_name}<br><small class="text-muted">${o.phone}</small></td>
        <td>${o.items.length} item(s)</td>
        <td>${adMoney(o.total)}</td>
        <td>${o.payment_method.toUpperCase()}<br><small class="text-muted">${o.payment_status}</small></td>
        <td><span class="badge-status ${statusClass(o.status)}">${o.status}</span></td>
        <td><small>${o.created_at}</small></td>
        <td class="text-nowrap">
          <div class="d-flex flex-column gap-1">
            <select class="form-select form-select-sm status-select" data-order="${o.order_number}">
              ${statuses.map((s) => `<option value="${s}" ${s === o.status ? "selected" : ""}>${s}</option>`).join("")}
            </select>
            <div class="d-flex gap-1">
              <button class="btn btn-sm btn-success flex-fill approve-btn" data-order="${o.order_number}"
                ${o.status !== "Order Received" ? "disabled" : ""}><i class="fa-solid fa-check"></i> Approve</button>
              <button class="btn btn-sm btn-outline-danger flex-fill reject-btn" data-order="${o.order_number}"
                ${["Delivered", "Cancelled"].includes(o.status) ? "disabled" : ""}><i class="fa-solid fa-xmark"></i> Reject</button>
            </div>
          </div>
        </td>
      </tr>
    `).join("") || `<tr><td colspan="8" class="text-center text-muted py-4">No orders found.</td></tr>`;
  }

  tbody.addEventListener("change", async (e) => {
    const sel = e.target.closest(".status-select");
    if (!sel) return;
    const data = await adFetch(`/api/admin/orders/${sel.dataset.order}/status`, {
      method: "POST",
      body: JSON.stringify({ status: sel.value }),
    });
    if (data.success) {
      adToast(`Order ${sel.dataset.order} updated to "${sel.value}".`);
      loadOrders();
    } else {
      adToast(data.message || "Update failed.", "danger");
    }
  });

  tbody.addEventListener("click", async (e) => {
    const approveBtn = e.target.closest(".approve-btn");
    if (approveBtn) {
      const data = await adFetch(`/api/admin/orders/${approveBtn.dataset.order}/approve`, { method: "POST" });
      if (data.success) {
        adToast(`Order ${approveBtn.dataset.order} approved!`);
        loadOrders();
      } else {
        adToast(data.message || "Could not approve order.", "danger");
      }
      return;
    }
    const rejectBtn = e.target.closest(".reject-btn");
    if (rejectBtn) {
      if (!confirm(`Reject order ${rejectBtn.dataset.order}? This cancels it.`)) return;
      const reason = prompt("Reason for rejection (optional):", "") || "";
      const data = await adFetch(`/api/admin/orders/${rejectBtn.dataset.order}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      if (data.success) {
        adToast(`Order ${rejectBtn.dataset.order} rejected.`);
        loadOrders();
      } else {
        adToast(data.message || "Could not reject order.", "danger");
      }
    }
  });

  filter.addEventListener("change", loadOrders);
  loadOrders();
}

// =========================================================
// MENU MANAGEMENT
// =========================================================
if (window.FH_ADMIN_PAGE === "menu") {
  const tbody = document.getElementById("menuTableBody");
  const addForm = document.getElementById("addFoodForm");
  const editForm = document.getElementById("editFoodForm");
  const editModalEl = document.getElementById("editFoodModal");
  const editModal = new bootstrap.Modal(editModalEl);
  let menuCache = [];

  async function loadMenu() {
    const data = await adFetch("/api/admin/menu");
    if (!data.success) return;
    menuCache = data.items;
    tbody.innerHTML = data.items.map((i) => `
      <tr data-id="${i.id}">
        <td><img src="${i.image_url}" alt="${i.name}" style="width:56px;height:48px;object-fit:cover;border-radius:8px;"></td>
        <td>${i.name}</td>
        <td>${i.category}</td>
        <td>${adMoney(i.price)}</td>
        <td><input type="checkbox" class="form-check-input toggle-available" ${i.is_available ? "checked" : ""}></td>
        <td><input type="checkbox" class="form-check-input toggle-deal" ${i.is_deal ? "checked" : ""}></td>
        <td><input type="checkbox" class="form-check-input toggle-popular" ${i.is_popular ? "checked" : ""}></td>
        <td class="text-nowrap">
          <button class="btn btn-sm fh-btn-outline edit-item me-1"><i class="fa-solid fa-pen"></i></button>
          <button class="btn btn-sm btn-outline-danger delete-item"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join("");
  }

  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(addForm);
    const res = await fetch("/api/admin/menu", { method: "POST", body: formData });
    const data = await res.json();
    if (data.success) {
      adToast("Food item added!");
      addForm.reset();
      loadMenu();
    } else {
      adToast(data.message || "Could not add item.", "danger");
    }
  });

  tbody.addEventListener("change", async (e) => {
    const row = e.target.closest("tr");
    if (!row) return;
    const id = row.dataset.id;
    const payload = {};
    if (e.target.classList.contains("toggle-available")) payload.is_available = e.target.checked;
    if (e.target.classList.contains("toggle-deal")) payload.is_deal = e.target.checked;
    if (e.target.classList.contains("toggle-popular")) payload.is_popular = e.target.checked;
    const data = await adFetch(`/api/admin/menu/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    if (data.success) adToast("Item updated.");
  });

  tbody.addEventListener("click", async (e) => {
    const delBtn = e.target.closest(".delete-item");
    if (delBtn) {
      const row = delBtn.closest("tr");
      if (!confirm("Delete this food item? This also removes its uploaded photo (if any).")) return;
      const data = await adFetch(`/api/admin/menu/${row.dataset.id}`, { method: "DELETE" });
      if (data.success) {
        adToast("Item deleted.");
        row.remove();
      }
      return;
    }

    const editBtn = e.target.closest(".edit-item");
    if (editBtn) {
      const row = editBtn.closest("tr");
      const item = menuCache.find((i) => String(i.id) === row.dataset.id);
      if (!item) return;
      document.getElementById("editItemId").value = item.id;
      document.getElementById("editName").value = item.name;
      document.getElementById("editPrice").value = item.price;
      document.getElementById("editCategory").value = item.category_id;
      document.getElementById("editDescription").value = item.description || "";
      document.getElementById("editCurrentImage").src = item.image_url;
      document.getElementById("editRemoveImage").checked = false;
      editModal.show();
    }
  });

  editForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const itemId = document.getElementById("editItemId").value;
    const formData = new FormData(editForm);
    const res = await fetch(`/api/admin/menu/${itemId}`, { method: "PUT", body: formData });
    const data = await res.json();
    if (data.success) {
      adToast("Item updated successfully!");
      editModal.hide();
      loadMenu();
    } else {
      adToast(data.message || "Could not update item.", "danger");
    }
  });

  loadMenu();
}

// =========================================================
// CUSTOMERS
// =========================================================
if (window.FH_ADMIN_PAGE === "customers") {
  const tbody = document.getElementById("customersTableBody");
  const search = document.getElementById("customerSearch");

  async function loadCustomers() {
    const data = await adFetch(`/api/admin/customers?search=${encodeURIComponent(search.value || "")}`);
    if (!data.success) return;
    tbody.innerHTML = data.customers.map((c) => `
      <tr data-id="${c.id}">
        <td>${c.name}</td>
        <td>${c.email}</td>
        <td>${c.phone}</td>
        <td>${c.created_at}</td>
        <td><span class="badge-status ${c.is_active ? "ready" : "cancelled"}">${c.is_active ? "Active" : "Disabled"}</span></td>
        <td><button class="btn btn-sm fh-btn-outline toggle-customer">${c.is_active ? "Disable" : "Enable"}</button></td>
      </tr>
    `).join("") || `<tr><td colspan="6" class="text-center text-muted py-4">No customers found.</td></tr>`;
  }

  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest(".toggle-customer");
    if (!btn) return;
    const row = btn.closest("tr");
    const data = await adFetch(`/api/admin/customers/${row.dataset.id}/toggle`, { method: "POST" });
    if (data.success) {
      adToast("Customer status updated.");
      loadCustomers();
    }
  });

  let debounce;
  search.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(loadCustomers, 300);
  });

  loadCustomers();
}

// =========================================================
// PAYMENTS
// =========================================================
if (window.FH_ADMIN_PAGE === "payments") {
  (async function () {
    const data = await adFetch("/api/admin/payments");
    const tbody = document.getElementById("paymentsTableBody");
    if (!data.success) return;
    tbody.innerHTML = data.payments.map((p) => `
      <tr>
        <td>${p.order_number || "-"}</td>
        <td>${p.customer_name || "-"}</td>
        <td>${adMoney(p.amount)}</td>
        <td>${p.method.toUpperCase()}</td>
        <td><span class="badge-status ${p.status === "Paid" ? "delivered" : p.status === "Failed" ? "cancelled" : "received"}">${p.status}</span></td>
        <td><small>${p.transaction_id || "—"}</small></td>
        <td><small>${p.created_at}</small></td>
      </tr>
    `).join("") || `<tr><td colspan="7" class="text-center text-muted py-4">No payments yet.</td></tr>`;
  })();
}

// =========================================================
// OFFERS
// =========================================================
if (window.FH_ADMIN_PAGE === "offers") {
  const tbody = document.getElementById("offersTableBody");
  const addForm = document.getElementById("addOfferForm");

  async function loadOffers() {
    const data = await adFetch("/api/admin/offers");
    if (!data.success) return;
    tbody.innerHTML = data.offers.map((o) => `
      <tr data-id="${o.id}">
        <td>${o.title}</td>
        <td>${o.description || "-"}</td>
        <td>${o.discount_percent}%</td>
        <td><input type="checkbox" class="form-check-input toggle-active" ${o.active ? "checked" : ""}></td>
        <td><button class="btn btn-sm btn-outline-danger delete-offer"><i class="fa-solid fa-trash"></i></button></td>
      </tr>
    `).join("") || `<tr><td colspan="5" class="text-center text-muted py-4">No offers yet.</td></tr>`;
  }

  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(addForm);
    const payload = Object.fromEntries(formData.entries());
    payload.discount_percent = parseFloat(payload.discount_percent);
    const data = await adFetch("/api/admin/offers", { method: "POST", body: JSON.stringify(payload) });
    if (data.success) {
      adToast("Offer created!");
      addForm.reset();
      loadOffers();
    }
  });

  tbody.addEventListener("change", async (e) => {
    if (!e.target.classList.contains("toggle-active")) return;
    const row = e.target.closest("tr");
    const data = await adFetch(`/api/admin/offers/${row.dataset.id}`, {
      method: "PUT", body: JSON.stringify({ active: e.target.checked }),
    });
    if (data.success) adToast("Offer updated.");
  });

  tbody.addEventListener("click", async (e) => {
    const delBtn = e.target.closest(".delete-offer");
    if (!delBtn) return;
    const row = delBtn.closest("tr");
    if (!confirm("Delete this offer?")) return;
    const data = await adFetch(`/api/admin/offers/${row.dataset.id}`, { method: "DELETE" });
    if (data.success) {
      adToast("Offer deleted.");
      row.remove();
    }
  });

  loadOffers();
}

});
