import { register } from "../api/auth.js";
import { saveSession } from "../auth/session.js";
import { renderHeader } from "../components/header.js";

renderHeader("../");

const form = document.getElementById("register-form");
const errorEl = document.getElementById("form-error");
const btn = document.getElementById("submit-btn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  const full_name = form.full_name.value.trim();
  const email = form.email.value.trim();
  const phone = form.phone.value.trim();
  const password = form.password.value;

  if (full_name.length < 2) return (errorEl.textContent = "Enter your full name.");
  if (!/^\S+@\S+\.\S+$/.test(email)) return (errorEl.textContent = "Enter a valid email address.");
  if (phone && !/^[0-9+\- ]{7,20}$/.test(phone)) return (errorEl.textContent = "Enter a valid phone number.");
  if (password.length < 8) return (errorEl.textContent = "Password must be at least 8 characters.");

  btn.disabled = true;
  btn.textContent = "Creating account...";
  try {
    const data = await register({ full_name, email, phone, password });
    saveSession(data.access_token, data.user);
    location.href = "../index.html";
  } catch (err) {
    errorEl.textContent = err.message;
    btn.disabled = false;
    btn.textContent = "Create account";
  }
});