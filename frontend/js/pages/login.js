import { login } from "../api/auth.js";
import { saveSession } from "../auth/session.js";
import { renderHeader } from "../components/header.js";

renderHeader("../");

const form = document.getElementById("login-form");
const errorEl = document.getElementById("form-error");
const btn = document.getElementById("submit-btn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  const email = form.email.value.trim();
  const password = form.password.value;

  if (!email || !password) {
    errorEl.textContent = "Enter your email and password.";
    return;
  }

  btn.disabled = true;
  btn.textContent = "Logging in...";
  try {
    const data = await login(email, password);
    saveSession(data.access_token, data.user);
    // Owners and admins get their own dashboards in a later step.
    location.href = "../index.html";
  } catch (err) {
    errorEl.textContent = err.message;
    btn.disabled = false;
    btn.textContent = "Log in";
  }
});