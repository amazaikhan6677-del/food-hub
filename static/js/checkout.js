/* =========================================================
   FoodHub - checkout.js
   Checkout page: order summary, payment fields, place order
   ========================================================= */

(function () {
  const form = document.getElementById("checkoutForm");
  if (!form) return;

  const itemsList = document.getElementById("checkoutItemsList");
  const cardFields = document.getElementById("cardFields");
  const mobileFields = document.getElementById("mobileFields");
  const placeOrderBtn = document.getElementById("placeOrderBtn");

  async function loadSummary() {
    const data = await fhFetch("/api/cart");
    if (!data.success) return;
    const cart = data.cart;

    itemsList.innerHTML = cart.items.map(
      (i) => `<div class="d-flex justify-content-between small mb-1">
                <span>${i.quantity} x ${i.name}</span><span>${fhMoney(i.line_total)}</span>
              </div>`
    ).join("");

    const t = cart.totals;
    document.getElementById("coSubtotal").textContent = fhMoney(t.subtotal);
    document.getElementById("coDiscount").textContent = "- " + fhMoney(t.discount);
    document.getElementById("coDelivery").textContent = t.delivery_fee === 0 ? "FREE" : fhMoney(t.delivery_fee);
    document.getElementById("coTotal").textContent = fhMoney(t.total);
  }

  document.querySelectorAll('input[name="payment_method"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      cardFields.classList.add("d-none");
      mobileFields.classList.add("d-none");
      if (radio.value === "card" && radio.checked) cardFields.classList.remove("d-none");
      if ((radio.value === "jazzcash" || radio.value === "easypaisa") && radio.checked) mobileFields.classList.remove("d-none");
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    placeOrderBtn.disabled = true;
    placeOrderBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Placing order...';

    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    // Never send full card numbers — only a masked last-4 for demo display.
    const cardInput = document.getElementById("cardNumberInput");
    if (cardInput && cardInput.value) {
      const digits = cardInput.value.replace(/\D/g, "");
      payload.card_last4 = digits.slice(-4);
    }
    const mobileInput = document.getElementById("mobileNumberInput");
    if (mobileInput && mobileInput.value) {
      payload.mobile_number = mobileInput.value;
    }

    const data = await fhFetch("/api/orders/create", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (data.success) {
      fhToast("Order placed successfully!", "success");
      window.location.href = `/tracking?order_number=${data.order.order_number}`;
    } else {
      fhToast(data.message || "Could not place order.", "danger");
      placeOrderBtn.disabled = false;
      placeOrderBtn.innerHTML = '<i class="fa-solid fa-lock me-2"></i>Place Order';
    }
  });

  loadSummary();
})();
