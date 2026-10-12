import {
  confirmManualPayment,
  getManualPayments,
  getOwnerStore,
  rejectManualPayment,
  updateOwnerStore,
} from "../api/owner.js";
import { getUser, isLoggedIn } from "../auth/session.js";
import { escapeHtml, renderHeader } from "../components/header.js";
import { money } from "../utils/format.js";

renderHeader("../");
const form = document.getElementById("upi-settings-form");
const message = document.getElementById("owner-message");
const paymentsEl = document.getElementById("manual-payments");

function renderPayments(payments) {
  if (!payments.length) {
    paymentsEl.innerHTML = '<p class="empty">No submitted UPI references are waiting for verification.</p>';
    return;
  }
  paymentsEl.innerHTML = payments.map((payment) => `
    <article class="checkout-box owner-payment">
      <h3>${escapeHtml(payment.order_number)} · ${escapeHtml(payment.customer_name)}</h3>
      <p>Amount: <b>${money(payment.amount)}</b></p>
      <p>Customer reference: <code>${escapeHtml(payment.transaction_reference)}</code></p>
      <p class="text">Submitted: ${escapeHtml(new Date(payment.submitted_at).toLocaleString())}</p>
      <button class="btn solid" type="button" data-confirm="${escapeHtml(payment.order_id)}">Confirm money received</button>
      <button class="btn" type="button" data-reject="${escapeHtml(payment.order_id)}">Reject and cancel order</button>
    </article>`).join("");

  paymentsEl.querySelectorAll("[data-confirm]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Confirm only if this exact amount/reference is visible as credited in your UPI account. Mark payment received?")) return;
      button.disabled = true;
      try {
        await confirmManualPayment(button.dataset.confirm);
        await loadPayments();
      } catch (error) {
        message.textContent = error.message;
        button.disabled = false;
      }
    });
  });
  paymentsEl.querySelectorAll("[data-reject]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Reject this UPI reference and cancel the order? If money arrived, resolve/refund it outside FruitHub first.")) return;
      button.disabled = true;
      try {
        await rejectManualPayment(button.dataset.reject, "Store could not verify the submitted UPI reference");
        await loadPayments();
      } catch (error) {
        message.textContent = error.message;
        button.disabled = false;
      }
    });
  });
}

async function loadPayments() {
  renderPayments(await getManualPayments());
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = form.querySelector("button[type='submit']");
  submit.disabled = true;
  message.textContent = "Saving store UPI ID…";
  try {
    const upiVpa = new FormData(form).get("upi_vpa").trim();
    await updateOwnerStore({ upi_vpa: upiVpa });
    message.textContent = "Store UPI ID saved.";
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

async function init() {
  if (!isLoggedIn() || getUser()?.role !== "OWNER") {
    form.hidden = true;
    paymentsEl.innerHTML = '<p class="empty">Please log in with an owner account to manage store payments.</p>';
    return;
  }
  try {
    const [store] = await Promise.all([getOwnerStore(), loadPayments()]);
    form.elements.upi_vpa.value = store.upi_vpa || "";
  } catch (error) {
    message.textContent = error.message;
    paymentsEl.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

init();
