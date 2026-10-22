import { getStores, getSlots, isSample } from "./api.js";
import { bookableDays, formatDay, formatTime, CLOSE_MINUTES } from "./time.js";

const view = document.getElementById("view");
let storesCache = null;

const routes = [
  [/^\/$/, home],
  [/^\/stores\/(\d{4})\/?$/, store],
  [/^\/bookings\/?$/, bookings],
  [/^\/assistant\/?$/, assistant],
];

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function stores() {
  storesCache ??= await getStores();
  return storesCache;
}

async function render() {
  const path = location.pathname;
  document.querySelectorAll("nav a").forEach(a =>
    a.toggleAttribute("aria-current", a.getAttribute("href") === path ||
      (a.getAttribute("href") === "/" && path.startsWith("/stores"))));
  for (const [re, fn] of routes) {
    const m = path.match(re);
    if (m) {
      try { await fn(...m.slice(1)); }
      catch (err) { failed(err); }
      window.scrollTo(0, 0);
      return;
    }
  }
  notFound();
}

async function home() {
  const list = await stores();
  document.title = "Kestrel Collect";
  view.innerHTML = `
    <section class="intro">
      <h1>Book a collection slot</h1>
      <p>Choose your store, pick a one-hour slot, and collect your shopping when it suits you. Collection is free.</p>
    </section>
    <ul class="stores">
      ${list.map(s => `
        <li><a class="store-card" href="/stores/${s.store_id}" data-link>
          <span class="store-name">${esc(s.name)}</span>
          <span class="store-meta">${esc(s.region)} &middot; ${esc(s.format)}</span>
          <span class="store-go">See slots</span>
        </a></li>`).join("")}
    </ul>`;
}

async function store(id, day) {
  const s = (await stores()).find(x => x.store_id === id);
  if (!s) return notFound();
  const days = bookableDays();
  const chosen = new URLSearchParams(location.search).get("day");
  day = days.includes(chosen) ? chosen : days[0];
  document.title = `${s.name} - Kestrel Collect`;
  const slots = await getSlots(s, day);
  const now = Date.now();
  view.innerHTML = `
    <a class="back" href="/" data-link>All stores</a>
    <h1>${esc(s.name)}</h1>
    <p class="sub">Slots are one hour. Booking closes an hour before each slot. All times are UK time.</p>
    <div class="days" role="tablist" aria-label="Day">
      ${days.map(d => `<a role="tab" href="/stores/${id}?day=${d}" data-link aria-selected="${d === day}">${d === days[0] ? "Today" : formatDay(d)}</a>`).join("")}
    </div>
    <h2 class="day-head">${formatDay(day, "long")}</h2>
    <ul class="slots">
      ${slots.map(slot => {
        const start = new Date(slot.slot_start);
        const end = new Date(start.getTime() + 3600_000);
        const left = slot.capacity - slot.booked;
        const closed = start.getTime() - now < CLOSE_MINUTES * 60_000;
        const state = closed ? "closed" : left <= 0 ? "full" : "open";
        const label = state === "closed" ? "Closed" : state === "full" ? "Full" : `${left} left`;
        return `<li class="slot ${state}">
          <span class="slot-time">${formatTime(start)} - ${formatTime(end)}</span>
          <span class="slot-left">${label}</span>
          <button type="button" ${state === "open" ? "" : "disabled"} data-book="${slot.slot_start}">Book</button>
        </li>`;
      }).join("")}
    </ul>`;
  view.querySelectorAll("[data-book]").forEach(b => b.addEventListener("click", () =>
    toast("Booking needs you to sign in. Sign-in arrives in episode 16.")));
}

function bookings() {
  document.title = "My bookings - Kestrel Collect";
  view.innerHTML = `
    <h1>My bookings</h1>
    <div class="placeholder">
      <p>Sign in to see your bookings.</p>
      <p class="muted">Sign-in arrives in Level 2, episode 16.</p>
    </div>`;
}

function assistant() {
  document.title = "Ask Kestrel - Kestrel Collect";
  view.innerHTML = `
    <h1>Ask Kestrel</h1>
    <div class="placeholder">
      <p>Questions about collection, refunds or opening hours, answered from Kestrel's own policies.</p>
      <p class="muted">Ask Kestrel arrives in Level 3, episode 24.</p>
    </div>`;
}

function notFound() {
  document.title = "Page not found - Kestrel Collect";
  view.innerHTML = `
    <h1>We can't find that page</h1>
    <p><a href="/" data-link>Go to the store list</a></p>`;
}

function failed(err) {
  view.innerHTML = `
    <h1>Something went wrong</h1>
    <p>We couldn't load this page. Try again in a moment.</p>
    <pre class="error">${esc(err.message)}</pre>`;
}

let toastTimer;
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4000);
}

document.addEventListener("click", e => {
  const a = e.target.closest("a[data-link]");
  if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
  e.preventDefault();
  history.pushState({}, "", a.getAttribute("href"));
  render();
});
window.addEventListener("popstate", render);

document.getElementById("mode").textContent = isSample ? "Sample data" : "Live";
document.getElementById("mode").dataset.mode = isSample ? "sample" : "live";
render();
