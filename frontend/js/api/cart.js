import { request } from "./http.js";

export const addToCart = (product_id, quantity) =>
  request("/cart/items", { method: "POST", body: { product_id, quantity: Number(quantity) } });