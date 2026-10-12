import { clearSession, getUser } from "../auth/session.js";

// root is "" on index.html and "../" on pages inside /pages
export function renderHeader(root = "") {
  const el = document.getElementById("site-header");
  if (!el) return;
  const user = getUser();
  const first = user ? user.full_name.split(" ")[0] : "";

  el.innerHTML = `
    <header class="site-header">
      <a class="brand d" href="${root}index.html">FruitHub</a>
      <nav class="nav">
        <a href="${root}index.html">Home</a>
        <a href="${root}pages/products.html?type=FRUIT">Fruits</a>
        <a href="${root}pages/products.html?type=JUICE">Juices</a>
        <a href="${root}pages/products.html?type=DRY_FRUIT">Dry fruits</a>
        <a href="${root}pages/cart.html">Cart</a>
        <a href="${root}pages/orders.html">Orders</a>
        ${user?.role === "OWNER" ? `<a href="${root}pages/owner.html">Owner panel</a>` : ""}
        <a href="${root}pages/offers.html">Offers</a>
      </nav>
      <div class="acct">
        ${
          user
            ? `<span class="hello">Hi, ${escapeHtml(first)}</span>
               <button class="btn small" id="logout-btn" type="button">Log out</button>`
            : `<a class="btn small" href="${root}pages/login.html">Log in</a>
               <a class="btn small solid" href="${root}pages/register.html">Sign up</a>`
        }
      </div>
    </header>`;

  const out = document.getElementById("logout-btn");
  if (out) {
    out.addEventListener("click", () => {
      clearSession();
      location.href = `${root}index.html`;
    });
  }
}

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}