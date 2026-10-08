import { register } from "../api/auth.js";
import { saveSession } from "../auth/session.js";
import { renderHeader } from "../components/header.js";

renderHeader("../");

const form = document.getElementById("register-form");
const errorEl = document.getElementById("form-error");
const btn = document.getElementById("submit-btn");

const PHONE_RE = /^(\+?91|0)?[6-9]\d{9}$/;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  const full_name = form.full_name.value.trim();
  const email = form.email.value.trim();
  const phone = form.phone.value.replace(/[\s-]/g, "");
  const password = form.password.value;

  if (full_name.length < 2) return (errorEl.textContent = "Enter your full name.");
  if (!/^\S+@\S+\.\S+$/.test(email)) return (errorEl.textContent = "Enter a valid email address.");
  if (!PHONE_RE.test(phone)) return (errorEl.textContent = "Enter a valid 10-digit mobile number.");
  if (password.length < 8) return (errorEl.textContent = "Password must be at least 8 characters.");

  btn.disabled = true;
  btn.textContent = "Creating account...";
  try {
    const data = await register({ full_name, email, phone, password });
    saveSession(data.access_token, data.user);
    // Testing only: the backend returns the code when OTP_DEV_MODE=true
    if (data.otp && data.otp.dev_otp) sessionStorage.setItem("fh_dev_otp", data.otp.dev_otp);
    if (data.otp) sessionStorage.setItem("fh_resend_at", String(Date.now() + data.otp.resend_after_seconds * 1000));
    location.href = "verify-phone.html";
  } catch (err) {
    errorEl.textContent = err.message;
    btn.disabled = false;
    btn.textContent = "Create account";
  }
});