import { request } from "./http.js";

export const login = (email, password) =>
  request("/auth/login", { method: "POST", body: { email, password }, auth: false });

export const register = ({ full_name, email, phone, password }) =>
  request("/auth/register", {
    method: "POST",
    body: { full_name, email, phone: phone || null, password },
    auth: false,
  });

export const me = () => request("/auth/me");