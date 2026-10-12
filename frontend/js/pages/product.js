import { addToCart } from "../api/cart.js";
import { getProduct, productReviews, relatedProducts } from "../api/products.js";
import { getUser, isLoggedIn } from "../auth/session.js";
import { escapeHtml, renderHeader } from "../components/header.js";
import { productCard } from "../components/productCard.js";
import { toast } from "../components/toast.js";
import { detectTier } from "../3d/PerformanceManager.js";
import { animatedUrl, attachFallbacks, emojiFor, fileUrl, money, qtyText, stars } from "../utils/format.js";

renderHeader("../");

const page = document.getElementById("page");
const id = new URLSearchParams(location.search).get("id");
let viewer = null;

function notFound(message) {
  page.innerHTML = `<p class="empty">${escapeHtml(message)} <a class="link-btn" href="products.html">Back to fruits</a></p>`;
}

function setupAssetControls(product) {
  const message = document.getElementById("asset-message");
  const setBusy = (busy) => {
    document.getElementById("regenerate-asset").disabled = busy;
    document.getElementById("remove-asset").disabled = busy;
    document.getElementById("asset-image").disabled = busy;
  };
  document.getElementById("regenerate-asset").addEventListener("click", async () => {
    setBusy(true);
    try {
      const result = await fetchOwnerAsset(`/owner/products/${product.id}/3d`, "POST");
      message.textContent = result.message || "Preview generation started.";
    } catch (error) {
      message.textContent = error.message;
    } finally {
      setBusy(false);
    }
  });
  document.getElementById("remove-asset").addEventListener("click", async () => {
    setBusy(true);
    try {
      await fetchOwnerAsset(`/owner/products/${product.id}/3d`, "DELETE");
      message.textContent = "Animated preview removed.";
      product.asset_3d_url = null;
      if (viewer) viewer.dispose();
      viewer = null;
      showStill(product);
    } catch (error) {
      message.textContent = error.message;
    } finally {
      setBusy(false);
    }
  });
  document.getElementById("asset-image").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await fetchOwnerAsset(`/owner/products/${product.id}/image`, "POST", form);
      message.textContent = result.message || "Photo uploaded; animated preview generation started.";
    } catch (error) {
      message.textContent = error.message;
    } finally {
      event.target.value = "";
      setBusy(false);
    }
  });
}

async function fetchOwnerAsset(path, method, body) {
  const { API_BASE } = await import("../config.js");
  const { getToken } = await import("../auth/session.js");
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(API_BASE + path, { method, headers, body });
  const data = await response.json();
  if (!response.ok) throw new Error(data?.error?.message || "Could not update the animated preview.");
  return data;
}

function render(p) {
  document.title = `${p.name} | FruitHub`;
  const whole = p.unit === "piece" || p.unit === "dozen";
  const step = whole ? 1 : 0.5;
  const max = Math.max(step, Math.min(50, Number(p.stock_quantity)));
  const sale = Number(p.discount_percent) > 0;

  page.innerHTML = `
    <a class="back" href="products.html">← All products</a>
    <div class="pdp">
      <div>
        <div class="viewer" id="viewer">
          <canvas id="viewer-canvas" aria-label="Interactive depth preview of ${escapeHtml(p.name)}"></canvas>
          <div class="still" id="still" hidden></div>
          <div class="vbar" id="vbar" hidden>
            <button type="button" data-act="in" aria-label="Zoom in">+</button>
            <button type="button" data-act="out" aria-label="Zoom out">−</button>
            <button type="button" data-act="reset">Reset</button>
            <button type="button" data-act="full">Fullscreen</button>
          </div>
        </div>
        <p class="hint" id="hint" hidden>Drag to tilt the product photo's depth effect; scroll or pinch to zoom.</p>
        <p class="text preview-note">When the owner generates an animated preview, it appears here and in your cart. This is a moving depth effect made from the product photo, not a fully modelled 3D product.</p>
      </div>

      <div class="info">
        <h1 class="d">${escapeHtml(p.name)}</h1>
        <div class="meta"><span class="stars">${stars(p.rating)}</span>
          ${p.rating_count ? `${Number(p.rating).toFixed(1)} (${p.rating_count})` : "No reviews yet"}</div>
        <div class="bigprice">
          <b>${money(p.final_price)}</b><small>/${escapeHtml(p.unit)}</small>
          ${sale ? `<s>${money(p.price)}</s><span class="badge-inline">-${p.discount_percent}%</span>` : ""}
        </div>
        <p class="avail ${p.is_available ? "ok" : "no"}">${p.is_available ? "● Fresh today" : "Sold out"}</p>
        ${p.is_available ? `<p class="stock">Available: ${qtyText(p.stock_quantity)} ${escapeHtml(p.unit)}</p>` : ""}

        <div class="qrow">
          <span>Quantity</span>
          <div class="qty" id="qty-box">
            <button type="button" id="q-minus" aria-label="Decrease">−</button>
            <b id="q-val">${step}</b>
            <button type="button" id="q-plus" aria-label="Increase">+</button>
          </div>
          <span class="unit">${escapeHtml(p.unit)}</span>
        </div>
        <div class="cta">
          <button class="btn solid" id="add-btn" type="button" ${p.is_available ? "" : "disabled"}>Add to cart</button>
          <button class="btn" id="buy-btn" type="button" ${p.is_available ? "" : "disabled"}>Buy now</button>
        </div>
        <p class="text delivery-note">Seller delivery is offered only to locations within the seller's service area. Outside that area, you can still pay for products here, but must arrange and pay for delivery separately.</p>
        ${getUser()?.role === "OWNER" ? `
          <section class="asset-controls">
            <h2 class="sec">Animated product view</h2>
            <p class="text">Generate or remove the moving depth preview made from this product's photo. Customers see it on this page and in their cart.</p>
            <label class="btn" for="asset-image">Upload photo and regenerate</label>
            <input id="asset-image" type="file" accept="image/jpeg,image/png,image/webp" hidden>
            <button class="btn" id="regenerate-asset" type="button">Regenerate preview</button>
            <button class="btn" id="remove-asset" type="button">Remove preview</button>
            <p id="asset-message" role="status"></p>
          </section>` : ""}

        <div class="facts">
          <div><span>Seller</span>${escapeHtml(p.store_name)}</div>
          <div><span>Origin</span>${p.origin ? escapeHtml(p.origin) : "Not listed"}</div>
          <div><span>Category</span>${escapeHtml(p.category.name)}</div>
        </div>
        <h2 class="sec">About</h2>
        <p class="text">${p.description ? escapeHtml(p.description) : "No description yet."}</p>
        ${p.nutrition ? `<h2 class="sec">Nutrition</h2><p class="text">${escapeHtml(p.nutrition)}</p>` : ""}
      </div>
    </div>

    <section>
      <h2 class="sec big">Reviews</h2>
      <div id="reviews"><p class="empty">Loading reviews...</p></div>
    </section>
    <section>
      <h2 class="sec big">You may also like</h2>
      <div class="pgrid" id="related"><p class="empty">Loading...</p></div>
    </section>`;

  // quantity
  let qty = step;
  const val = document.getElementById("q-val");
  const set = (n) => {
    qty = Math.min(max, Math.max(step, n));
    val.textContent = qty;
  };
  document.getElementById("q-minus").addEventListener("click", () => set(qty - step));
  document.getElementById("q-plus").addEventListener("click", () => set(qty + step));

  async function add(thenBuy) {
    if (!isLoggedIn()) return (location.href = "login.html");
    const user = getUser();
    if (user && user.role !== "CUSTOMER") return toast("Only customer accounts can order.", "err");
    const btn = document.getElementById(thenBuy ? "buy-btn" : "add-btn");
    btn.disabled = true;
    try {
      await addToCart(p.id, qty);
      toast(`Added ${qty} ${p.unit} of ${p.name} to your cart`);
      if (thenBuy) location.href = "cart.html";
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  }
  document.getElementById("add-btn").addEventListener("click", () => add(false));
  document.getElementById("buy-btn").addEventListener("click", () => add(true));
  if (getUser()?.role === "OWNER") setupAssetControls(p);

  initViewer(p);
  loadReviews(p.id);
  loadRelated(p.id);
}

function showStill(p) {
  const still = document.getElementById("still");
  const canvas = document.getElementById("viewer-canvas");
  const src = animatedUrl(p) || fileUrl(p.image_url);
  const alt = animatedUrl(p) ? fileUrl(p.image_url) || "" : "";
  canvas.hidden = true;
  document.getElementById("vbar").hidden = true;
  document.getElementById("hint").hidden = true;
  still.hidden = false;
  still.innerHTML = src
    ? `<img src="${src}" alt="${escapeHtml(p.name)}" data-alt-src="${alt}" data-emoji="${emojiFor(p)}">`
    : `<span class="emoji-fb">${emojiFor(p)}</span>`;
  attachFallbacks(still);
}

async function initViewer(p) {
  const box = document.getElementById("viewer");
  if (!p.asset_3d_url || !/manifest\.json$/.test(p.asset_3d_url)) return showStill(p);
  const tier = detectTier();
  if (tier === "static") return showStill(p);

  try {
    const res = await fetch(fileUrl(p.asset_3d_url));
    if (!res.ok) throw new Error("manifest " + res.status);
    const manifest = await res.json();
    const { ProductViewer } = await import("../3d/ProductViewer.js");
    viewer = new ProductViewer(box, document.getElementById("viewer-canvas"), {
      cutoutUrl: fileUrl(manifest.cutout),
      depthUrl: fileUrl(manifest.depth),
      tierName: tier,
      onFail: () => showStill(p),
    });
    await viewer.ready;
    document.getElementById("vbar").hidden = false;
    document.getElementById("hint").hidden = false;
    document.getElementById("vbar").addEventListener("click", (e) => {
      const act = e.target.dataset.act;
      if (act === "in") viewer.zoom(0.8);
      if (act === "out") viewer.zoom(1.25);
      if (act === "reset") viewer.reset();
      if (act === "full") {
        if (document.fullscreenElement) document.exitFullscreen();
        else if (box.requestFullscreen) box.requestFullscreen();
      }
    });
  } catch (err) {
    console.warn("FruitHub viewer unavailable, using the still image:", err);
    if (viewer) viewer.dispose();
    viewer = null;
    showStill(p);
  }
}

async function loadReviews(pid) {
  const el = document.getElementById("reviews");
  try {
    const data = await productReviews(pid);
    if (!data.items.length) {
      el.innerHTML = '<p class="empty">No reviews yet. Reviews open after an order is delivered.</p>';
      return;
    }
    el.innerHTML = data.items
      .map((r) => `
        <div class="review">
          <div><span class="stars">${stars(r.rating)}</span> <b>${escapeHtml(r.reviewer_name)}</b>
            <small>${new Date(r.created_at).toLocaleDateString("en-IN")}</small></div>
          ${r.comment ? `<p>${escapeHtml(r.comment)}</p>` : ""}
        </div>`)
      .join("");
  } catch {
    el.innerHTML = '<p class="empty">Reviews could not be loaded.</p>';
  }
}

async function loadRelated(pid) {
  const el = document.getElementById("related");
  try {
    const items = await relatedProducts(pid);
    if (!items.length) return (el.innerHTML = '<p class="empty">No related fruits yet.</p>');
    el.innerHTML = items.map(productCard).join("");
    attachFallbacks(el);
  } catch {
    el.innerHTML = "";
  }
}

(async () => {
  if (!id) return notFound("No fruit selected.");
  try {
    render(await getProduct(id));
  } catch (err) {
    notFound(err.status === 404 || err.status === 422 ? "This fruit was not found." : err.message);
  }
})();