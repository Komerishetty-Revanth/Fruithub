import { request } from "./http.js";

export const login = (email, password) =>
  request("/auth/login", { method: "POST", body: { email, password }, auth: false });

export const register = ({ full_name, email, phone, password }) =>
  request("/auth/register", {
    method: "POST",
    body: { full_name, email, phone, password },
    auth: false,
  });

export const me = () => request("/auth/me");
export const sendOtp = () => request("/auth/phone/send", { method: "POST" });
export const verifyOtp = (code) => request("/auth/phone/verify", { method: "POST", body: { code } });