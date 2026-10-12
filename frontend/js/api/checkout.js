import { request } from "./http.js";

export const getCart = () => request("/cart");
export const updateCartItem = (productId, quantity, variantId = null) => {
  const query = variantId ? `?variant_id=${encodeURIComponent(variantId)}` : "";
  return request(`/cart/items/${productId}${query}`, {
    method: "PATCH",
    body: { quantity: Number(quantity) },
  });
};
export const removeCartItem = (productId, variantId = null) => {
  const query = variantId ? `?variant_id=${encodeURIComponent(variantId)}` : "";
  return request(`/cart/items/${productId}${query}`, { method: "DELETE" });
};
export const getAddresses = () => request("/addresses");
export const addAddress = (body) => request("/addresses", { method: "POST", body });
export const checkLocation = (body) => request("/locations/check", { method: "POST", body, auth: false });
export const startCheckout = (address_id, accept_self_delivery = false, payment_method = "UPI_MANUAL") =>
  request("/orders/checkout", {
    method: "POST",
    body: { address_id, accept_self_delivery, payment_method },
  });
export const submitUpiReference = (orderId, transaction_reference) =>
  request(`/orders/${orderId}/upi-reference`, {
    method: "POST",
    body: { transaction_reference },
  });
export const getUpiPayment = (orderId) => request(`/orders/${orderId}/upi-payment`);
export const getOrders = () => request("/orders?page=1&page_size=50");
export const confirmExternalDelivery = (orderId) =>
  request(`/orders/${orderId}/confirm-external-delivery`, { method: "POST" });
