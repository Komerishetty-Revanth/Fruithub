import { request } from "./http.js";

export const getOwnerStore = () => request("/owner/store");
export const updateOwnerStore = (body) => request("/owner/store", { method: "PATCH", body });
export const getManualPayments = () => request("/owner/orders/manual-payments");
export const confirmManualPayment = (orderId) =>
  request(`/owner/orders/${orderId}/manual-payment/confirm`, { method: "POST" });
export const rejectManualPayment = (orderId, note) =>
  request(`/owner/orders/${orderId}/manual-payment/reject`, { method: "POST", body: { note } });
