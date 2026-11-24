/* =========================================================
   FoodHub - chatbot.js
   FoodBot floating chatbot widget: talks to /api/chatbot
   ========================================================= */

(function () {
  const toggleBtn = document.getElementById("foodbot-toggle");
  const closeBtn = document.getElementById("foodbot-close");
  const panel = document.getElementById("foodbot-panel");
  const messagesEl = document.getElementById("foodbot-messages");
  const form = document.getElementById("foodbot-form");
  const input = document.getElementById("foodbot-input");
  const quickReplies = document.getElementById("foodbotQuickReplies");

  if (!toggleBtn) return;

  let greeted = false;

  function addMessage(text, sender) {
    const div = document.createElement("div");
    div.className = `fb-msg ${sender}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addTyping() {
    const div = document.createElement("div");
    div.className = "fb-msg bot typing";
    div.id = "fbTyping";
    div.textContent = "FoodBot is typing...";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function removeTyping() {
    const el = document.getElementById("fbTyping");
    if (el) el.remove();
  }

  async function sendMessage(text) {
    if (!text.trim()) return;
    addMessage(text, "user");
    addTyping();

    const data = await fhFetch("/api/chatbot", {
      method: "POST",
      body: JSON.stringify({ message: text }),
    });

    removeTyping();

    if (data.success) {
      addMessage(data.reply, "bot");
      if (data.action === "cart_updated" || data.action === "checkout_started") {
        const cartData = await fhFetch("/api/cart");
        if (cartData.success) fhUpdateCartBadge(cartData.cart);
      }
      if (data.action === "goto_checkout") {
        setTimeout(() => { window.location.href = "/checkout"; }, 900);
      }
      if (data.action === "order_placed" && data.order) {
        fhUpdateCartBadge({ items: [] });
        setTimeout(() => { window.location.href = `/tracking?order_number=${data.order.order_number}`; }, 1800);
      }
    } else {
      addMessage("Sorry, something went wrong. Please try again.", "bot");
    }
  }

  toggleBtn.addEventListener("click", () => {
    panel.classList.toggle("d-none");
    if (!panel.classList.contains("d-none") && !greeted) {
      greeted = true;
      addMessage(
        "Hi! 👋 I'm FoodBot 🤖. Ask me for 'zinger burger', 'show menu', 'show deals', " +
        "'show cart', or 'place order' — I'll handle the rest!",
        "bot"
      );
    }
  });

  closeBtn.addEventListener("click", () => panel.classList.add("d-none"));

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    sendMessage(text);
  });

  quickReplies.addEventListener("click", (e) => {
    const btn = e.target.closest(".qr-btn");
    if (btn) sendMessage(btn.dataset.msg);
  });
})();
