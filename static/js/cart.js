/* =========================================================
   FoodHub - cart.js
   Cart page rendering + quantity/remove actions
   ========================================================= */

// Page-specific code runs after the DOM is ready, so that the inline
// <script> that sets window.FH_PAGE (placed after this file) has already run.
document.addEventListener("DOMContentLoaded", function () {
if (window.FH_PAGE === "cart") {
  const listEl = document.getElementById("cartItemsList");
  const emptyEl = document.getElementById("cartEmptyState");
  const template = document.getElementById("cartItemTemplate");
  const checkoutBtn = document.getElementById("checkoutBtn");

  async function loadCart() {
    const data = await fhFetch("/api/cart");
    if (!data.success) return;
    renderCart(data.cart);
  }

  function renderCart(cart) {
    fhUpdateCartBadge(cart);
    listEl.innerHTML = "";

    if (!cart.items || cart.items.length === 0) {
      emptyEl.classList.remove("d-none");
      checkoutBtn.classList.add("disabled");
    } else {
      emptyEl.classList.add("d-none");
      checkoutBtn.classList.remove("disabled");
      cart.items.forEach((item) => {
        const node = template.content.cloneNode(true);
        node.querySelector(".ci-name").textContent = item.name;
        node.querySelector(".ci-price").textContent = fhMoney(item.price) + " each";
        node.querySelector(".ci-qty").textContent = item.quantity;
        node.querySelector(".ci-total").textContent = fhMoney(item.line_total);
        const imgEl = node.querySelector(".ci-img");
        imgEl.src = item.image_url || "/static/images/placeholder.svg";
        imgEl.alt = item.name;

        const root = node.querySelector(".fh-cart-item");
        root.dataset.itemId = item.id;

        node.querySelector(".qty-plus").addEventListener("click", () => updateQty(item.id, item.quantity + 1));
        node.querySelector(".qty-minus").addEventListener("click", () => updateQty(item.id, item.quantity - 1));
        node.querySelector(".ci-remove").addEventListener("click", () => removeItem(item.id));

        listEl.appendChild(node);
      });
    }

    const t = cart.totals;
    document.getElementById("sumSubtotal").textContent = fhMoney(t.subtotal);
    document.getElementById("sumDiscount").textContent = "- " + fhMoney(t.discount);
    document.getElementById("sumDelivery").textContent = t.delivery_fee === 0 ? "FREE" : fhMoney(t.delivery_fee);
    document.getElementById("sumTotal").textContent = fhMoney(t.total);
  }

  async function updateQty(itemId, quantity) {
    const data = await fhFetch("/api/cart/update", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, quantity }),
    });
    if (data.success) renderCart(data.cart);
  }

  async function removeItem(itemId) {
    const data = await fhFetch("/api/cart/remove", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId }),
    });
    if (data.success) {
      fhToast("Item removed from cart.", "info");
      renderCart(data.cart);
    }
  }

  loadCart();
}

});
