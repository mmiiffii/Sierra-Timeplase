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
const speedSelect = document.getElementById("speedSelect");
const playToggle = document.getElementById("playToggle");
const fabPlay = document.getElementById("fabPlay");
const sheetBackdrop = document.getElementById("sheetBackdrop");

// State
let manifest = null;
let weekIndex = 0;      // ASC order: oldest -> newest
let images = [];
let pendingIndex = null;
let prefetchRadius = 4;
let playing = false;
let playTimer = null;
let ipsBase = 6;        // images per second at 1×

/* ---------------- THEME ---------------- */
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

/* ---------------- UTILS ---------------- */
function showLoading(on) { loading.style.display = on ? "block" : "none"; }
function setSliderMax(n) { slider.max = String(Math.max(1, n)); slider.value = "1"; }
function orderWeeksAsc(data) { data.weeks.sort((a,b) => a.label > b.label ? 1 : -1); }

function updateWeekButtonLabel() {
  const wk = manifest?.weeks?.[weekIndex];
  if (wk) weekBtn.textContent = wk.label + " ▾";
}

function buildWeekMenu() {
  weekMenu.innerHTML = "";
  manifest.weeks.forEach((wk, i) => {
    const btn = document.createElement("button");
    btn.className = "dropdown-item";
    btn.textContent = wk.label;
    btn.addEventListener("click", () => {
      weekIndex = i;
      closeWeekMenu();
      stopPlayback();
      loadWeek(weekIndex);
    });
    weekMenu.appendChild(btn);
  });
}

function openWeekMenu() {
  weekBtn.setAttribute("aria-expanded", "true");
  weekMenu.classList.add("open");
  if (window.matchMedia("(max-width: 719px)").matches) {
    sheetBackdrop.classList.add("open");
  }
}
function closeWeekMenu() {
  weekBtn.setAttribute("aria-expanded", "false");
  weekMenu.classList.remove("open");
  sheetBackdrop.classList.remove("open");
}

weekBtn.addEventListener("click", (e) => {
  const isOpen = weekMenu.classList.contains("open");
  isOpen ? closeWeekMenu() : openWeekMenu();
  e.stopPropagation();
});
document.addEventListener("click", (e) => {
  if (!weekMenu.contains(e.target) && e.target !== weekBtn) {
    closeWeekMenu();
  }
});
sheetBackdrop.addEventListener("click", closeWeekMenu);

/* ---------------- PREFETCH ---------------- */
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

/* ---------------- RENDER ---------------- */
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
  prefetchAround(idx);
}

/* ---------------- LOAD ---------------- */
async function loadManifest() {
  const res = await fetch(manifestURL, { cache: "no-cache" });
  if (!res.ok) throw new Error("Failed to load manifest.json");
  const data = await res.json();
  if (!data.weeks || !data.weeks.length) throw new Error("No weeks in manifest");
  orderWeeksAsc(data);
  return data;
}

function loadWeek(i) {
  const wk = manifest.weeks[i];
  images = wk.images || [];
  setSliderMax(images.length);
  cache.clear();
  updateWeekButtonLabel();
  if (images.length) {
    slider.value = "1";
    requestShow(0);
  } else {
    imgEl.removeAttribute("src");
  }
}

/* ---------------- SLIDER ---------------- */
slider.addEventListener("input", () => {
  stopPlayback();
  requestShow(Number(slider.value) - 1);
});

/* ---------------- PLAYBACK ---------------- */
function currentRateIPS() {
  const mult = parseFloat(speedSelect.value || "1");
  return Math.max(0.1, ipsBase * mult);
}
function startPlayback() {
  if (playing || !images.length) return;
  playing = true;
  playToggle.textContent = "❚❚";
  playToggle.setAttribute("aria-pressed", "true");
  fabPlay.textContent = "❚❚";
  const stepMs = Math.max(5, 1000 / currentRateIPS());
  playTimer = setInterval(tickForward, stepMs);
}
function stopPlayback() {
  playing = false;
  if (playTimer) { clearInterval(playTimer); playTimer = null; }
  playToggle.textContent = "▶";
  playToggle.setAttribute("aria-pressed", "false");
  fabPlay.textContent = "▶";
}
function tickForward() {
  if (!images.length) return;
  let idx = Number(slider.value) - 1;
  idx += 1;
  if (idx >= images.length) {
    // advance to next week (wrap after newest)
    weekIndex = (weekIndex + 1) % manifest.weeks.length;
    loadWeek(weekIndex);
    idx = 0;
  }
  slider.value = String(idx + 1);
  requestShow(idx);
}
speedSelect.addEventListener("change", () => {
  if (playing) { stopPlayback(); startPlayback(); }
});
function togglePlayback() { playing ? stopPlayback() : startPlayback(); }
playToggle.addEventListener("click", togglePlayback);
fabPlay.addEventListener("click", togglePlayback);

// Tap image toggles playback on mobile
imgEl.addEventListener("click", () => {
  if (window.matchMedia("(max-width: 719px)").matches) togglePlayback();
});

/* ---------------- KEYBOARD (desktop) ---------------- */
window.addEventListener("keydown", (e) => {
  if (e.code === "Space") { e.preventDefault(); togglePlayback(); return; }
  if (!images.length) return;
  if (e.key === "ArrowLeft") {
    stopPlayback();
    slider.value = String(Math.max(1, Number(slider.value) - 1));
    requestShow(Number(slider.value) - 1);
  }
  if (e.key === "ArrowRight") {
    stopPlayback();
    slider.value = String(Math.min(Number(slider.max), Number(slider.value) + 1));
    requestShow(Number(slider.value) - 1);
  }
});

/* ---------------- INIT ---------------- */
(async function init() {
  try {
    showLoading(true);
    manifest = await loadManifest();
    buildWeekMenu();
    // Start with newest
    weekIndex = manifest.weeks.length - 1;
    loadWeek(weekIndex);
    showLoading(false);
  } catch (err) {
    showLoading(false);
    imgEl.alt = "Failed to load manifest";
    console.error(err);
  }
})();

/* Placeholder */
tlBtn?.addEventListener("click", () => alert("Timelapse generator coming soon ✨"));
