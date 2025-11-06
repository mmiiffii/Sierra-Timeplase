const manifestUrl = "./manifest.json";

const els = {
  weekSelect: document.getElementById("weekSelect"),
  gallery: document.getElementById("gallery"),
  countBadge: document.getElementById("countBadge"),
  prevBtn: document.getElementById("prevBtn"),
  nextBtn: document.getElementById("nextBtn"),
};

let manifest = null;
let currentWeekIdx = 0;

// Simple lazy loader
const io = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      const img = e.target;
      const src = img.getAttribute("data-src");
      if (src) {
        img.src = src;
        img.removeAttribute("data-src");
      }
      io.unobserve(img);
    }
  });
}, { rootMargin: "600px" });

async function loadManifest() {
  const res = await fetch(manifestUrl, { cache: "no-cache" });
  if (!res.ok) throw new Error("Failed to load manifest.json");
  const data = await res.json();
  // Sort weeks by label descending (latest first) by default
  data.weeks.sort((a,b) => a.label < b.label ? 1 : -1);
  return data;
}

function populateWeeks() {
  els.weekSelect.innerHTML = "";
  manifest.weeks.forEach((wk, idx) => {
    const opt = document.createElement("option");
    opt.value = idx;
    opt.textContent = `${wk.label} (${wk.count})`;
    els.weekSelect.appendChild(opt);
  });
  els.weekSelect.value = String(currentWeekIdx);
}

function renderWeek(idx) {
  const wk = manifest.weeks[idx];
  if (!wk) return;
  els.countBadge.textContent = wk.count;
  els.gallery.innerHTML = "";

  wk.images.forEach((img, i) => {
    const card = document.createElement("div");
    card.className = "card";

    const image = document.createElement("img");
    image.alt = img.name;
    image.setAttribute("data-src", img.raw); // lazy
    io.observe(image);

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = img.name;

    card.appendChild(image);
    card.appendChild(meta);
    els.gallery.appendChild(card);
  });
}

function goPrev() {
  const firstVisible = [...document.querySelectorAll(".card")].findIndex(c => {
    const r = c.getBoundingClientRect();
    return r.top >= 0 && r.top < window.innerHeight*0.6;
  });
  const idx = Math.max(0, firstVisible - 1);
  document.querySelectorAll(".card")[idx]?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function goNext() {
  const cards = [...document.querySelectorAll(".card")];
  const firstVisible = cards.findIndex(c => {
    const r = c.getBoundingClientRect();
    return r.top >= 0 && r.top < window.innerHeight*0.6;
  });
  const idx = Math.min(cards.length - 1, firstVisible + 1);
  cards[idx]?.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function init() {
  try {
    manifest = await loadManifest();
    if (!manifest.weeks || manifest.weeks.length === 0) {
      els.gallery.innerHTML = "<p>No weeks found. Run the manifest workflow after adding images.</p>";
      return;
    }
    populateWeeks();
    renderWeek(currentWeekIdx);

    els.weekSelect.addEventListener("change", (e) => {
      currentWeekIdx = Number(e.target.value);
      renderWeek(currentWeekIdx);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    els.prevBtn.addEventListener("click", goPrev);
    els.nextBtn.addEventListener("click", goNext);

    // Keyboard shortcuts
    window.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
    });
  } catch (err) {
    els.gallery.innerHTML = `<p style="color:#f66">Error loading manifest: ${err.message}</p>`;
  }
}

init();
