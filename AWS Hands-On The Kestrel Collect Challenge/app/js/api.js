import { MODE, API_BASE } from "../config.js";
import { ukToUtc, FIRST_HOUR, LAST_HOUR } from "./time.js";

export const isSample = MODE === "sample";

async function getJson(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} from ${path}`);
  return res.json();
}

export async function getStores() {
  const stores = isSample
    ? await getJson("/sample/stores.json")
    : await getJson(`${API_BASE}/api/stores`);
  return stores.filter(s => !s.hidden);
}

// Slots for one store on one UK date: [{ slot_start: "2026-10-24T08:00:00Z", capacity, booked }]
export async function getSlots(store, dateStr) {
  if (!isSample) {
    return getJson(`${API_BASE}/api/stores/${encodeURIComponent(store.store_id)}/slots?date=${dateStr}`);
  }
  const slots = [];
  for (let hour = FIRST_HOUR; hour <= LAST_HOUR; hour++) {
    const start = ukToUtc(dateStr, hour);
    slots.push({
      slot_start: start.toISOString().replace(".000Z", "Z"),
      capacity: store.capacity,
      booked: sampleBooked(`${store.store_id}|${dateStr}|${hour}`, store.capacity),
    });
  }
  return slots;
}

// Repeatable made-up demand, so the sample screens look the same every run.
function sampleBooked(key, capacity) {
  let h = 2166136261;
  for (const ch of key) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b); h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35); h ^= h >>> 16;
  const r = (h >>> 0) / 4294967296;
  return r > 0.82 ? capacity : Math.floor(r * capacity * 1.1);
}
