import { FILES_BASE } from "../config.js";

export const money = (n) =>
  "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });

export const qtyText = (n) => String(Number(n));

export const stars = (r) => {
  const k = Math.max(0, Math.min(5, Math.round(Number(r) || 0)));
  return "★".repeat(k) + "☆".repeat(5 - k);
};

// Backend files are saved as "/uploads/..." and served by the backend itself.
export function fileUrl(u) {
  if (!u) return null;
  return /^https?:/.test(u) ? u : FILES_BASE + u;
}

// The animated preview sits next to manifest.json
export function animatedUrl(p) {
  if (p.asset_3d_url && /manifest\.json$/.test(p.asset_3d_url)) {
    return fileUrl(p.asset_3d_url.replace(/manifest\.json$/, "animated.webp"));
  }
  return null;
}

const EMOJI = {
  mango: "🥭", apple: "🍎", banana: "🍌", citrus: "🍊", berries: "🍓",
  melons: "🍉", grapes: "🍇", pomegranate: "🍎", tropical: "🍍", seasonal: "🍑",
};
export const emojiFor = (p) => {
  const type = p.category && p.category.product_type;
  if (type === "JUICE") return "🧃";
  if (type === "DRY_FRUIT") return "🥜";
  return EMOJI[p.category && p.category.slug] || "🍑";
};

// If an image fails to load, try the still photo, then fall back to an emoji.
export function attachFallbacks(root) {
  root.querySelectorAll("img[data-emoji]").forEach((img) => {
    img.addEventListener("error", () => {
      const alt = img.dataset.altSrc;
      if (alt) {
        img.dataset.altSrc = "";
        img.src = alt;
      } else {
        const s = document.createElement("span");
        s.className = "emoji-fb";
        s.textContent = img.dataset.emoji || "🍑";
        img.replaceWith(s);
      }
    });
  });
}