import { renderHeader } from "./components/header.js";
import { detectTier } from "./3d/PerformanceManager.js";

renderHeader("");

const PRODUCT_ICONS = ["🍎", "🥭", "🧃", "🥜", "🍊", "🍇", "🍉", "🥤"];
const intro = document.getElementById("intro");
const seen = sessionStorage.getItem("fh_intro_seen");
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let scene3d = null;
let revealed = false;

function startPage() {
  document.body.classList.add("ready");
  revealed = true;
  if (scene3d) scene3d.reveal();
}

function finishIntro() {
  sessionStorage.setItem("fh_intro_seen", "1");
  intro.classList.add("hide");
  startPage();
}

if (seen || reduce) {
  intro.remove();
  startPage();
} else {
  intro.querySelector(".logo").innerHTML = "FruitHub"
    .split("")
    .map((c, i) => `<span style="--i:${i}">${c}</span>`)
    .join("");
  intro.querySelector(".drops").innerHTML = PRODUCT_ICONS
    .map((f, i) => `<span style="--i:${i};--y:${window.innerHeight * 0.55 + (i % 2 ? 50 : 10)};left:${6 + i * 14}%">${f}</span>`)
    .join("");
  const timer = setTimeout(finishIntro, 3600);
  intro.querySelector(".skip").addEventListener("click", () => {
    clearTimeout(timer);
    finishIntro();
  });
}

// ---------- 3D hero (loaded lazily, with a safe fallback) ----------
async function init3d() {
  const canvas = document.getElementById("hero-canvas");
  const fallback = document.getElementById("hero-fallback");
  const showFallback = () => {
    document.body.classList.remove("has3d");
    fallback.hidden = false;
  };

  const tier = detectTier();
  if (tier === "static") return showFallback();

  try {
    const { FruitScene } = await import("./3d/FruitScene.js");
    scene3d = new FruitScene(canvas, tier, {
      onFail: () => {
        scene3d = null;
        showFallback();
      },
    });
    document.body.classList.add("has3d");
    if (revealed) scene3d.reveal();
  } catch (err) {
    console.warn("3D scene unavailable, using the fallback:", err);
    showFallback();
  }
}

init3d();