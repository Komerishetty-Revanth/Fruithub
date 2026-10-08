import { me, sendOtp, verifyOtp } from "../api/auth.js";
import { isLoggedIn, updateUser } from "../auth/session.js";
import { renderHeader } from "../components/header.js";

renderHeader("../");

if (!isLoggedIn()) location.replace("login.html");

const form = document.getElementById("otp-form");
const errorEl = document.getElementById("form-error");
const btn = document.getElementById("submit-btn");
const resendBtn = document.getElementById("resend-btn");
const devBox = document.getElementById("dev-box");
const lead = document.getElementById("lead");
let timer = null;

function showDevCode(code) {
  if (!code) return (devBox.hidden = true);
  devBox.hidden = false;
  devBox.textContent = `Testing mode: your code is ${code}`;
}

function startCountdown(untilMs) {
  clearInterval(timer);
  const tick = () => {
    const left = Math.ceil((untilMs - Date.now()) / 1000);
    if (left > 0) {
      resendBtn.disabled = true;
      resendBtn.textContent = `Resend code in ${left}s`;
    } else {
      clearInterval(timer);
      resendBtn.disabled = false;
      resendBtn.textContent = "Resend code";
    }
  };
  tick();
  timer = setInterval(tick, 500);
}

async function init() {
  try {
    const user = await me();
    updateUser(user);
    if (user.phone_verified) return (location.replace("../index.html"));
    lead.textContent = `We sent a 6-digit code to ${user.phone}.`;
  } catch {
    return location.replace("login.html");
  }
  showDevCode(sessionStorage.getItem("fh_dev_otp"));
  startCountdown(Number(sessionStorage.getItem("fh_resend_at")) || 0);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  const code = form.code.value.trim();
  if (!/^\d{6}$/.test(code)) return (errorEl.textContent = "Enter the 6-digit code.");

  btn.disabled = true;
  btn.textContent = "Verifying...";
  try {
    const user = await verifyOtp(code);
    updateUser(user);
    sessionStorage.removeItem("fh_dev_otp");
    sessionStorage.removeItem("fh_resend_at");
    location.href = "../index.html";
  } catch (err) {
    errorEl.textContent = err.message;
    btn.disabled = false;
    btn.textContent = "Verify";
  }
});

resendBtn.addEventListener("click", async () => {
  errorEl.textContent = "";
  resendBtn.disabled = true;
  try {
    const sent = await sendOtp();
    showDevCode(sent.dev_otp);
    if (sent.dev_otp) sessionStorage.setItem("fh_dev_otp", sent.dev_otp);
    const until = Date.now() + sent.resend_after_seconds * 1000;
    sessionStorage.setItem("fh_resend_at", String(until));
    startCountdown(until);
  } catch (err) {
    errorEl.textContent = err.message;
    resendBtn.disabled = false;
  }
});

init();