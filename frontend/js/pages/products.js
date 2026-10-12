import { listCategories, listProducts } from "../api/product.js";
import { escapeHtml, renderHeader } from "../components/header.js";
import { productCard } from "../components/productCard.js";
import { attachFallbacks } from "../utils/format.js";

renderHeader("../");

const TYPE_LABELS = {
  FRUIT: { title: "Fresh fruits", subtitle: "Picked fresh and offered by local sellers." },
  JUICE: { title: "Fresh juices", subtitle: "Refreshing juices from local sellers." },
  DRY_FRUIT: { title: "Dry fruits", subtitle: "Quality dry fruits and nuts from local sellers." },
};
const TYPE_OPTIONS = [
  ["", "All products"],
  ["FRUIT", "Fruits"],
  ["JUICE", "Juices"],
  ["DRY_FRUIT", "Dry fruits"],
];

const title = document.getElementById("page-title");
const subtitle = document.getElementById("page-sub");
const search = document.getElementById("search");
const typeChips = document.getElementById("type-chips");
const categoryChips = document.getElementById("chips");
const sort = document.getElementById("sort");
const maxPrice = document.getElementById("max_price");
const minRating = document.getElementById("min_rating");
const available = document.getElementById("available");
const hasOffer = document.getElementById("has_offer");
const reset = document.getElementById("reset");
const count = document.getElementById("count");
const grid = document.getElementById("grid");
const pager = document.getElementById("pager");

let categories = [];
let page = 1;
let activeCategory = new URLSearchParams(location.search).get("category") || "";
let activeType = new URLSearchParams(location.search).get("type") || "";
let searchTimer;

if (!TYPE_OPTIONS.some(([value]) => value === activeType)) activeType = "";

function updateUrl() {
  const params = new URLSearchParams();
  if (activeType) params.set("type", activeType);
  if (activeCategory) params.set("category", activeCategory);
  const query = params.toString();
  history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}`);
}

function renderTypeChips() {
  typeChips.innerHTML = TYPE_OPTIONS.map(([value, label]) => `
    <button class="chip${activeType === value ? " on" : ""}" type="button"
      role="tab" aria-selected="${activeType === value}" data-type="${value}">
      ${label}
    </button>`).join("");
  typeChips.querySelectorAll("[data-type]").forEach((button) => {
    button.addEventListener("click", () => {
      activeType = button.dataset.type;
      activeCategory = "";
      page = 1;
      updateUrl();
      renderTypeChips();
      renderCategoryChips();
      renderTitle();
      loadProducts();
    });
  });
}

function renderCategoryChips() {
  const visibleCategories = categories.filter(
    (category) => !activeType || category.product_type === activeType
  );
  const options = [["", "All categories"], ...visibleCategories.map((c) => [c.slug, c.name])];
  categoryChips.innerHTML = options.map(([value, label]) => `
    <button class="chip${activeCategory === value ? " on" : ""}" type="button"
      role="tab" aria-selected="${activeCategory === value}" data-category="${escapeHtml(value)}">
      ${escapeHtml(label)}
    </button>`).join("");
  categoryChips.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.category;
      page = 1;
      updateUrl();
      renderCategoryChips();
      loadProducts();
    });
  });
}

function renderTitle() {
  const copy = TYPE_LABELS[activeType];
  title.textContent = copy ? copy.title : "Shop fresh products";
  subtitle.textContent = copy ? copy.subtitle : "Fresh products from local sellers.";
  document.title = `${copy ? copy.title : "Shop"} | FruitHub`;
}

function renderPager(total, pageSize) {
  const pageCount = Math.ceil(total / pageSize);
  if (pageCount <= 1) {
    pager.innerHTML = "";
    return;
  }
  pager.innerHTML = `
    <button class="link-btn" type="button" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>Previous</button>
    <span>Page ${page} of ${pageCount}</span>
    <button class="link-btn" type="button" data-page="${page + 1}" ${page >= pageCount ? "disabled" : ""}>Next</button>`;
  pager.querySelectorAll("[data-page]").forEach((button) => {
    button.addEventListener("click", () => {
      page = Number(button.dataset.page);
      loadProducts();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

async function loadProducts() {
  grid.innerHTML = Array.from({ length: 4 }, () => '<div class="pcard skel"></div>').join("");
  pager.innerHTML = "";
  count.textContent = "Loading products…";

  const params = new URLSearchParams({ page: String(page), page_size: "12", sort: sort.value });
  const query = search.value.trim();
  if (query) params.set("q", query);
  if (activeType) params.set("product_type", activeType);
  if (activeCategory) params.set("category", activeCategory);
  if (maxPrice.value) params.set("max_price", maxPrice.value);
  if (minRating.value) params.set("min_rating", minRating.value);
  if (available.checked) params.set("available", "true");
  if (hasOffer.checked) params.set("has_offer", "true");

  try {
    const result = await listProducts(params.toString());
    count.textContent = `${result.total} product${result.total === 1 ? "" : "s"}`;
    if (!result.items.length) {
      grid.innerHTML = '<p class="empty">No products found. Try changing your search or filters.</p>';
      renderPager(result.total, result.page_size);
      return;
    }
    grid.innerHTML = result.items.map(productCard).join("");
    attachFallbacks(grid);
    renderPager(result.total, result.page_size);
  } catch (error) {
    count.textContent = "";
    grid.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function resetFilters() {
  search.value = "";
  sort.value = "name";
  maxPrice.value = "";
  minRating.value = "";
  available.checked = false;
  hasOffer.checked = false;
  activeCategory = "";
  page = 1;
  updateUrl();
  renderCategoryChips();
  loadProducts();
}

sort.addEventListener("change", () => { page = 1; loadProducts(); });
maxPrice.addEventListener("change", () => { page = 1; loadProducts(); });
minRating.addEventListener("change", () => { page = 1; loadProducts(); });
available.addEventListener("change", () => { page = 1; loadProducts(); });
hasOffer.addEventListener("change", () => { page = 1; loadProducts(); });
search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { page = 1; loadProducts(); }, 250);
});
reset.addEventListener("click", resetFilters);

(async () => {
  renderTypeChips();
  renderTitle();
  try {
    categories = await listCategories();
    renderCategoryChips();
    await loadProducts();
  } catch (error) {
    count.textContent = "";
    grid.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
})();
