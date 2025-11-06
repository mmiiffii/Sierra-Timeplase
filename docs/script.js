// Config
const manifestURL = "./manifest.json";

// Elements
const imgEl = document.getElementById("hero");
const slider = document.getElementById("slider");
const weekBtn = document.getElementById("weekBtn");
const weekMenu = document.getElementById("weekMenu");
const tlBtn = document.getElementById("timelapseBtn");
const loading = document.getElementById("loading");
const themeToggle = document.getElementById("themeToggle");

// State
let manifest = null;
let weekIndex = 0;           // default: latest week (we'll order desc)
let images = [];             // current week image list (array of {raw, name, ...})
let pendingIndex = null;     // requested index to show (debounced via rAF)
let prefetchRadius = 4;      // how many neighbors to prefetch

// THEME
(function initTheme(){
  const saved = localStorage.getItem("sierra-theme");
  if (saved === "light" || saved === "dark") {
    document.documentElement.setAttribute("data-theme", saved);
    themeToggle.textContent = saved === "dark" ? "☾" : "☼";
  }
})();
themeToggle.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("sierra-theme", next);
  themeToggle.textContent = next === "dark" ? "☾" : "☼";
});

// UTILS
function showLoading(on) {
  loading.style.display = on ? "block" : "none";
}
function setSliderMax(n) {
  slider.max = String(Math.max(1, n));
  slider.value = "1";
}
function orderWeeksDesc(data) {
  // latest first by label; your labels are "Week XX - ...", string sort works enough
  data.weeks.sort((a,b) => a.label < b.label ? 1 : -1);
}
function buildWeekMenu() {
  weekMenu.innerHTML = "";
  manifest.weeks.forEach((wk, i) => {
    const btn = document.createElement("button");
    btn.className = "dropdown-item";
    btn.textContent = wk.label;
    btn.addEventListener("click", () => {
      weekIndex = i;
      weekMenu.classList.remove("open");
      loadWeek(weekIndex);
    });
    weekMenu.appendChild(btn);
  });
}
weekBtn.addEventListener("click", () => {
  weekMenu.classList.toggle("open");
});
document.addEventListener("click", (e) => {
  if (!weekMenu.contains(e.target) && e.target !== weekBtn) {
    weekMenu.classList.remove("open");
  }
});

// PREFETCH
const cache = new Map(); // url->Image object (loaded)
function prefetchAround(idx) {
  if (!images.length) return;
  const lo = Math.max(0, idx - prefetchRadius);
  const hi = Math.min(images.length - 1, idx + prefetchRadius);
  for (let i = lo; i <= hi; i++) {
    const url = images[i].raw;
    if (!cache.has(url)) {
      const im = new Image();
      im.src = url;
      cache.set(url, im);
    }
  }
}

// RENDER
let rafId = 0;
function requestShow(index) {
  pendingIndex = index;
  if (!rafId) rafId = requestAnimationFrame(applyShow);
}
function applyShow() {
  rafId = 0;
  if (pendingIndex == null) return;
  const idx = Math.min(Math.max(0, pendingIndex), images.length - 1);
  const url = images[idx].raw;

  // If prefetched, swap instantly; else show loading briefly
  const pref = cache.get(url);
  if (pref && pref.complete) {
    showLoading(false);
    imgEl.src = url;
  } else {
    showLoading(true);
    const temp = new Image();
    temp.onload = () => {
      showLoading(false);
      imgEl.src = url;
      cache.set(url, temp);
    };
    temp.onerror = () => showLoading(false);
    temp.src = url;
  }

  // Warm next/prev
  prefetchAround(idx);
}

// LOAD
async function loadManifest() {
  const res = await fetch(manifestURL, { cache: "no-cache" });
  if (!res.ok) throw new Error("Failed to load manifest.json");
  const data = await res.json();
  if (!data.weeks || !data.weeks.length) throw new Error("No weeks in manifest");
  orderWeeksDesc(data);
  return data;
}

function loadWeek(i) {
  const wk = manifest.weeks[i];
  images = wk.images || [];
  setSliderMax(images.length);
  cache.clear();
  if (images.length) {
    // start near sunrise-ish: 06:00 = index ~ (6*60/5) if 5-min cadence; fall back to 1
    const suggested = Math.min(images.length, 75); // ~6h at 5-min → 72; mild bias
    slider.value = String(Math.max(1, suggested));
    requestShow(Number(slider.value) - 1);
  } else {
    imgEl.removeAttribute("src");
  }
}

// SLIDER
slider.addEventListener("input", () => {
  requestShow(Number(slider.value) - 1);
});

// KEYBOARD
window.addEventListener("keydown", (e) => {
  if (!images.length) return;
  if (e.key === "ArrowLeft") {
    slider.value = String(Math.max(1, Number(slider.value) - 1));
    requestShow(Number(slider.value) - 1);
  }
  if (e.key === "ArrowRight") {
    slider.value = String(Math.min(Number(slider.max), Number(slider.value) + 1));
    requestShow(Number(slider.value) - 1);
  }
});

// INIT
(async function init(){
  try {
    showLoading(true);
    manifest = await loadManifest();
    buildWeekMenu();
    loadWeek(0); // latest week
  } catch (err) {
    showLoading(false);
    imgEl.alt = "Failed to load manifest";
    console.error(err);
  }
})();
 
// Placeholder action
document.getElementById("timelapseBtn").addEventListener("click", () => {
  alert("Timelapse generator coming soon ✨");
});
