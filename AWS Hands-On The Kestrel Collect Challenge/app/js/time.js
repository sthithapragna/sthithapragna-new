// Every time a person sees is UK time. Every time we store is UTC.
export const TZ = "Europe/London";
export const FIRST_HOUR = 8;   // first slot starts 08:00 UK time
export const LAST_HOUR = 19;   // last slot starts 19:00 UK time
export const DAYS_AHEAD = 6;   // today plus the next 6 days
export const CLOSE_MINUTES = 60; // booking closes 1 hour before a slot

const partsFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit",
  day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
});

// Minutes the UK is ahead of UTC at a given instant: 0 (GMT) or 60 (BST).
function ukOffsetMinutes(date) {
  const v = Object.fromEntries(partsFmt.formatToParts(date).map(p => [p.type, p.value]));
  const asUtc = Date.UTC(+v.year, +v.month - 1, +v.day, +v.hour, +v.minute, +v.second);
  return Math.round((asUtc - date.getTime()) / 60000);
}

// The UTC instant of a UK wall-clock hour on a UK calendar date (YYYY-MM-DD).
export function ukToUtc(dateStr, hour) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const wall = Date.UTC(y, m - 1, d, hour, 0, 0);
  let t = wall - ukOffsetMinutes(new Date(wall)) * 60000;
  t = wall - ukOffsetMinutes(new Date(t)) * 60000; // settles clock-change days
  return new Date(t);
}

// Today's date in the UK, as YYYY-MM-DD.
export function ukToday(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(now);
}

export function addDays(dateStr, n) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

export function bookableDays(now = new Date()) {
  const today = ukToday(now);
  return Array.from({ length: DAYS_AHEAD + 1 }, (_, i) => addDays(today, i));
}

export function formatTime(date) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatDay(dateStr, style = "short") {
  const noon = new Date(`${dateStr}T12:00:00Z`);
  const opts = style === "long"
    ? { timeZone: TZ, weekday: "long", day: "numeric", month: "long" }
    : { timeZone: TZ, weekday: "short", day: "numeric", month: "short" };
  return new Intl.DateTimeFormat("en-GB", opts).format(noon);
}
