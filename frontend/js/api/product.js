import { request } from "./http.js";

export const listProducts = (qs) => request(`/products?${qs}`, { auth: false });
export const getProduct = (id) => request(`/products/${id}`, { auth: false });
export const relatedProducts = (id) => request(`/products/${id}/related`, { auth: false });
export const productReviews = (id, page = 1, size = 5) =>
  request(`/products/${id}/reviews?page=${page}&page_size=${size}`, { auth: false });
export const listCategories = () => request("/categories", { auth: false });
export const listOffers = () => request("/offers", { auth: false });