import {
  addAddress,
  checkLocation,
  getAddresses,
  getCart,
  removeCartItem,
  submitUpiReference,
  startCheckout,
  updateCartItem,
} from "../api/checkout.js";
import { isLoggedIn } from "../auth/session.js";
import { escapeHtml, renderHeader } from "../components/header.js";
import { attachFallbacks, fileUrl, money } from "../utils/format.js";

renderHeader("../");
const itemsEl = document.getElementById("cart-items");
const checkoutBox = document.getElementById("checkout-box");
const addressSelect = document.getElementById("address-select");
const deliveryText = document.getElementById("address-delivery");
const ackWrap = document.getElementById("external-ack-wrap");
const ack = document.getElementById("external-ack");
const totalEl = document.getElementById("cart-total");
const placeButton = document.getElementById("place-order");
const message = document.getElementById("checkout-message");
const addressForm = document.getElementById("new-address-form");
const upiPanel = document.getElementById("upi-payment");
const upiReferenceForm = document.getElementById("upi-reference-form");
let pendingUpiOrderId = null;
let cart = null;
let addresses = [];
let selectedDelivery = null;

const amount = (value) => money(Number(value || 0));
const animatedSource = (item) => {
  const url = item.asset_3d_url;
  if (url && /manifest\.json$/.test(url)) return fileUrl(url.replace(/manifest\.json$/, "animated.webp"));
  return fileUrl(item.image_url);
};

function renderCart() {
  if (!cart?.items?.length) {
    itemsEl.innerHTML = '<p class="empty">Your cart is empty. <a href="products.html">Browse products</a>.</p>';
    checkoutBox.hidden = true;
    return;
  }
  checkoutBox.hidden = false;
  itemsEl.innerHTML = cart.items.map((item) => `
    <article class="cart-item">
      <div class="cart-preview-wrap">
        <img class="cart-preview" src="${escapeHtml(animatedSource(item) || "")}" alt="${escapeHtml(item.name)}"
          data-alt-src="${escapeHtml(fileUrl(item.image_url) || "")}" data-emoji="🧺">
        <span>${item.asset_3d_url ? "Animated preview" : "Product photo"}</span>
      </div>
      <div class="cart-item-info">
        <h2><a href="product.html?id=${encodeURIComponent(item.product_id)}">${escapeHtml(item.name)}</a></h2>
        <p>${amount(item.unit_price)} / ${escapeHtml(item.unit)}</p>
        ${item.issue ? `<p class="avail no">${escapeHtml(item.issue)}</p>` : ""}
        <label>Quantity
          <input type="number" min="0.01" max="50" step="0.01" value="${Number(item.quantity)}"
            data-quantity="${item.product_id}" data-variant="${item.variant_id || ""}">
        </label>
        <button class="link-btn" type="button" data-remove="${item.product_id}" data-variant="${item.variant_id || ""}">Remove</button>
      </div>
      <strong>${amount(item.line_total)}</strong>
    </article>`).join("");
  attachFallbacks(itemsEl);

  itemsEl.querySelectorAll("[data-quantity]").forEach((input) => {
    input.addEventListener("change", async () => {
      const variantId = input.dataset.variant || null;
      try {
        cart = await updateCartItem(input.dataset.quantity, input.value, variantId);
        await refreshCart();
      } catch (error) {
        message.textContent = error.message;
      }
    });
  });
  itemsEl.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        cart = await removeCartItem(button.dataset.remove, button.dataset.variant || null);
        await refreshCart();
      } catch (error) {
        message.textContent = error.message;
      }
    });
  });
  renderTotal();
  placeButton.disabled = cart.has_issues || !selectedDelivery ||
    (selectedDelivery.self_delivery_required && !ack.checked);
}

function renderTotal() {
  if (!cart) return;
  const productTotal = Number(cart.subtotal) - Number(cart.discount_total);
  if (selectedDelivery?.self_delivery_required) {
    totalEl.innerHTML = `
      <p>Products after discounts: <b>${amount(productTotal)}</b></p>
      <p>FruitHub delivery charge: <b>${amount(0)}</b></p>
      <p>External delivery: <b>Arranged and paid separately by you</b></p>
      <p>Pay the store by UPI: <b>${amount(productTotal)}</b></p>`;
  } else if (selectedDelivery) {
    totalEl.innerHTML = `
      <p>Products after discounts: <b>${amount(productTotal)}</b></p>
      <p>Seller delivery: <b>${amount(cart.delivery_fee)}</b></p>
      <p>Pay the store by UPI: <b>${amount(cart.total)}</b></p>`;
  } else {
    totalEl.innerHTML = `
      <p>Products after discounts: <b>${amount(productTotal)}</b></p>
      <p>Delivery charge is determined after you select an address.</p>`;
  }
}

async function refreshCart() {
  cart = await getCart();
  renderCart();
}

async function loadDeliveryOption() {
  const address = addresses.find((item) => item.id === addressSelect.value);
  selectedDelivery = null;
  ack.checked = false;
  ackWrap.hidden = true;
  placeButton.disabled = true;
  if (!address || !cart?.store_id) {
    deliveryText.textContent = address ? "Could not determine this store's delivery area." : "Add or select a complete address to continue.";
    return;
  }
  try {
    selectedDelivery = await checkLocation({
      latitude: address.latitude,
      longitude: address.longitude,
      store_id: cart.store_id,
    });
    if (!address.is_complete) {
      deliveryText.textContent = "Please save a complete street address, city, and pincode before checkout.";
      selectedDelivery = null;
      renderTotal();
      return;
    }
    deliveryText.textContent = selectedDelivery.message;
    ackWrap.hidden = !selectedDelivery.self_delivery_required;
    placeButton.disabled = cart.has_issues ||
      (selectedDelivery.self_delivery_required && !ack.checked);
  } catch (error) {
    deliveryText.textContent = error.message;
  }
  renderTotal();
}

addressSelect.addEventListener("change", loadDeliveryOption);
ack.addEventListener("change", () => {
  placeButton.disabled = cart?.has_issues || !selectedDelivery ||
    (selectedDelivery.self_delivery_required && !ack.checked);
});
document.getElementById("show-address-form").addEventListener("click", () => {
  addressForm.hidden = !addressForm.hidden;
});

addressForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(addressForm);
  const body = Object.fromEntries(form.entries());
  body.latitude = Number(body.latitude);
  body.longitude = Number(body.longitude);
  try {
    const address = await addAddress(body);
    addresses.push(address);
    addressSelect.insertAdjacentHTML("beforeend",
      `<option value="${escapeHtml(address.id)}">${escapeHtml(address.label)} — ${escapeHtml(address.city || "")}</option>`);
    addressSelect.value = address.id;
    addressForm.reset();
    addressForm.hidden = true;
    await loadDeliveryOption();
  } catch (error) {
    message.textContent = error.message;
  }
});

placeButton.addEventListener("click", async () => {
  if (!selectedDelivery || !addressSelect.value) return;
  placeButton.disabled = true;
  message.textContent = "Creating your order…";
  try {
    const checkout = await startCheckout(addressSelect.value, ack.checked, "UPI_MANUAL");
    const order = checkout.order;
    pendingUpiOrderId = order.id;
    document.getElementById("upi-amount").textContent = amount(checkout.payment.amount);
    document.getElementById("upi-payee").textContent = checkout.payment.payee_name;
    document.getElementById("upi-vpa").textContent = checkout.payment.upi_vpa;
    const upiLaunch = document.getElementById("upi-launch");
    upiLaunch.href = checkout.payment.payment_uri;
    upiLaunch.setAttribute("aria-label", `Pay ${amount(checkout.payment.amount)} to ${checkout.payment.payee_name} using UPI`);
    upiPanel.hidden = false;
    document.getElementById("copy-upi").onclick = async () => {
      try {
        await navigator.clipboard.writeText(checkout.payment.upi_vpa);
        message.textContent = "Store UPI ID copied. Open your preferred UPI app to pay.";
      } catch {
        message.textContent = `Copy failed. Store UPI ID: ${checkout.payment.upi_vpa}`;
      }
    };
    placeButton.hidden = true;
    message.textContent = `Order ${order.order_number} created. ${
      order.seller_delivery_available
        ? "The seller can deliver to your address."
        : "The seller cannot deliver here; arrange and pay for delivery separately."
    }`;
    document.getElementById("orders-link").hidden = false;
  } catch (error) {
    message.textContent = error.message;
    placeButton.disabled = false;
  }
});

upiReferenceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!pendingUpiOrderId) return;
  const submit = upiReferenceForm.querySelector("button[type='submit']");
  submit.disabled = true;
  message.textContent = "Submitting your UPI reference…";
  try {
    await submitUpiReference(
      pendingUpiOrderId,
      new FormData(upiReferenceForm).get("transaction_reference").trim(),
    );
    upiReferenceForm.hidden = true;
    message.textContent = "Reference submitted. The order will be marked paid only after the store verifies the credit in its UPI account.";
  } catch (error) {
    message.textContent = error.message;
    submit.disabled = false;
  }
});

async function init() {
  if (!isLoggedIn()) {
    itemsEl.innerHTML = '<p class="empty">Please <a href="login.html">log in</a> to view your cart.</p>';
    return;
  }
  try {
    [cart, addresses] = await Promise.all([getCart(), getAddresses()]);
    addressSelect.innerHTML = addresses.map((address) =>
      `<option value="${escapeHtml(address.id)}">${escapeHtml(address.label)} — ${escapeHtml(address.city || "")}</option>`
    ).join("");
    renderCart();
    if (addresses.length) {
      addressSelect.value = addresses.find((address) => address.is_default)?.id || addresses[0].id;
      await loadDeliveryOption();
    } else {
      deliveryText.textContent = "Add an address to check seller delivery availability.";
    }
  } catch (error) {
    itemsEl.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

init();
