import { listOffers } from "../api/products.js";
import { escapeHtml, renderHeader } from "../components/header.js";
import { productCard } from "../components/productCard.js";
import { attachFallbacks, money } from "../utils/format.js";

renderHeader("../");

const offersEl = document.getElementById("offers");
const grid = document.getElementById("grid");
grid.innerHTML = Array.from({ length: 4 }, () => '<div class="pcard skel"></div>').join("");

function describe(o) {
  const v = Number(o.discount_value);
  const what = o.discount_type === "PERCENTAGE" ? `${v}% off` : `${money(v)} off`;
  const min = o.min_order_amount ? ` on orders above ${money(o.min_order_amount)}` : "";
  return what + min;
}

(async () => {
  try {
    const data = await listOffers();
    offersEl.innerHTML = data.offers
      .map((o) => `
        <div class="offer">
          <b>${escapeHtml(o.title)}</b>
          <span>${escapeHtml(describe(o))}</span>
          <small>Ends ${new Date(o.ends_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</small>
        </div>`)
      .join("");
    if (!data.products.length) {
      grid.innerHTML = '<p class="empty">No offers right now. Please check back soon.</p>';
      return;
    }
    grid.innerHTML = data.products.map(productCard).join("");
    attachFallbacks(grid);
  } catch (err) {
    grid.innerHTML = `<p class="empty">${escapeHtml(err.message)}</p>`;
  }
})();