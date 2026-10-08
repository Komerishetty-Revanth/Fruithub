import { renderHeader } from "./components/header.js";

renderHeader("");

const FRUITS = ["🍎", "🥭", "🍊", "🍌", "🍇", "🍉"];
const intro = document.getElementById("intro");
const seen = sessionStorage.getItem("fh_intro_seen");
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function startPage() {
  document.body.classList.add("ready");
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
  intro.querySelector(".drops").innerHTML = FRUITS
    .map((f, i) => `<span style="--i:${i};--y:${window.innerHeight * 0.55 + (i % 2 ? 50 : 10)};left:${6 + i * 16}%">${f}</span>`)
    .join("");
  const timer = setTimeout(finishIntro, 3600);
  intro.querySelector(".skip").addEventListener("click", () => {
    clearTimeout(timer);
    finishIntro();
  });
}