import {
  confirmExternalDelivery,
  getOrders,
  getUpiPayment,
  submitUpiReference,
} from "../api/checkout.js";
import { isLoggedIn } from "../auth/session.js";
import { escapeHtml, renderHeader } from "../components/header.js";
import { money } from "../utils/format.js";

renderHeader("../");
const list = document.getElementById("orders-list");

function upiPaymentPanel(order, payment) {
  if (!payment || payment.error) {
    return '<p class="delivery-note">Could not load payment details. Refresh this page or contact the store before paying.</p>';
  }
  if (payment.reference_submitted) {
    return '<p class="delivery-note">Your UPI reference has been submitted. The order remains unpaid until the store verifies that the money arrived.</p>';
  }
  return `
    <section class="upi-payment">
      <h3>Finish product payment</h3>
      <p>Pay <b>${money(payment.amount)}</b> to ${escapeHtml(payment.payee_name)} using PhonePe, Google Pay, Paytm, or another installed UPI app.</p>
      <p>UPI ID: <code>${escapeHtml(payment.upi_vpa)}</code>
        <button class="btn small" type="button" data-copy-upi="${escapeHtml(payment.upi_vpa)}">Copy UPI ID</button>
      </p>
      <a class="btn solid" href="${escapeHtml(payment.payment_uri)}" rel="noopener">Open a UPI app</a>
      <p class="text">If no app opens, copy the UPI ID and amount and pay manually from your UPI app.</p>
      ${payment.pay_before
        ? `<p class="text">Complete payment before ${escapeHtml(new Date(payment.pay_before).toLocaleString())}.</p>`
        : ""}
      <form class="address-form" data-upi-reference="${escapeHtml(order.id)}">
        <label class="field"><span>UPI transaction reference / UTR</span>
          <input name="transaction_reference" minlength="6" maxlength="50" pattern="[A-Za-z0-9/-]+" required>
        </label>
        <button class="btn" type="submit">Submit reference for verification</button>
      </form>
    </section>`;
}

function render(orders, upiPayments) {
  if (!orders.length) {
    list.innerHTML = '<p class="empty">You have no orders yet. <a href="products.html">Browse products</a>.</p>';
    return;
  }
  list.innerHTML = orders.map((order) => `
    <article class="checkout-box order-card">
      <h2>Order ${escapeHtml(order.order_number)}</h2>
      <p>Status: <b>${escapeHtml(order.status.replaceAll("_", " "))}</b> · Payment: <b>${escapeHtml(order.payment_status)}</b></p>
      <p>Product order total: <b>${money(order.total)}</b></p>
      ${order.payment_method === "UPI_MANUAL" && order.status === "PENDING_PAYMENT"
        ? upiPaymentPanel(order, upiPayments[order.id])
        : ""}
      ${order.payment_method === "UPI_MANUAL" && order.status === "CANCELLED" && order.payment_status === "PAID"
        ? '<p class="delivery-note">The store cancelled this order after verifying your direct UPI payment. Contact the store to arrange your refund outside FruitHub.</p>'
        : ""}
      ${order.seller_delivery_available
        ? "<p>Seller delivery is available for this order.</p>"
        : `<p class="delivery-note">The seller cannot deliver to this address. Arrange and pay for external delivery separately. ${
          order.payment_method === "UPI_MANUAL"
            ? "Product payment is sent directly to the store by UPI."
            : "Product payment is handled by the selected payment method."
        }</p>`}
      ${!order.seller_delivery_available && order.status === "READY_FOR_DELIVERY" && order.payment_status === "PAID"
        ? `<button class="btn solid" type="button" data-received="${escapeHtml(order.id)}">Confirm I received this order</button>`
        : ""}
    </article>`).join("");
  list.querySelectorAll("[data-received]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await confirmExternalDelivery(button.dataset.received);
        await load();
      } catch (error) {
        button.disabled = false;
        button.insertAdjacentText("afterend", ` ${error.message}`);
      }
    });
  });
  list.querySelectorAll("[data-copy-upi]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copyUpi);
        button.textContent = "Copied";
      } catch {
        button.insertAdjacentText("afterend", " Copy failed; select the UPI ID above and copy it.");
      }
    });
  });
  list.querySelectorAll("[data-upi-reference]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = form.querySelector("button[type='submit']");
      submit.disabled = true;
      try {
        await submitUpiReference(
          form.dataset.upiReference,
          new FormData(form).get("transaction_reference").trim(),
        );
        await load();
      } catch (error) {
        submit.disabled = false;
        submit.insertAdjacentText("afterend", ` ${error.message}`);
      }
    });
  });
}

async function load() {
  if (!isLoggedIn()) {
    list.innerHTML = '<p class="empty">Please <a href="login.html">log in</a> to view your orders.</p>';
    return;
  }
  try {
    const orders = await getOrders();
    const upiPayments = {};
    await Promise.all(orders.filter(
      (order) => order.payment_method === "UPI_MANUAL" && order.status === "PENDING_PAYMENT",
    ).map(async (order) => {
      try {
        upiPayments[order.id] = await getUpiPayment(order.id);
      } catch (error) {
        upiPayments[order.id] = { error: error.message };
      }
    }));
    render(orders, upiPayments);
  } catch (error) {
    list.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

load();
