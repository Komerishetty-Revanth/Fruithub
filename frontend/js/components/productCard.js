import { escapeHtml } from "./header.js";
import { animatedUrl, emojiFor, fileUrl, money } from "../utils/format.js";

// Used on pages inside /pages, so the product page is a sibling file.
export function productCard(p) {
  const anim = animatedUrl(p);
  const still = fileUrl(p.image_url);
  const src = anim || still;
  const emoji = emojiFor(p);
  const visual = src
    ? `<img src="${src}" alt="" loading="lazy" data-alt-src="${anim && still ? still : ""}" data-emoji="${emoji}">`
    : `<span class="emoji-fb">${emoji}</span>`;
  const sale = Number(p.discount_percent) > 0;

  return `
    <a class="pcard${p.is_available ? "" : " sold"}" href="product.html?id=${p.id}">
      ${sale ? `<span class="badge-off">-${p.discount_percent}%</span>` : ""}
      <div class="pv">${visual}</div>
      <h3>${escapeHtml(p.name)}</h3>
      <div class="price">
        <b>${money(p.final_price)}</b><small>/${escapeHtml(p.unit)}</small>
        ${sale ? `<s>${money(p.price)}</s>` : ""}
      </div>
      <span class="avail ${p.is_available ? "ok" : "no"}">${p.is_available ? "● Fresh today" : "Sold out"}</span>
    </a>`;
}