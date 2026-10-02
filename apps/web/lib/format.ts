// Display formatting. Times are stored in UTC and shown in New York time (CLAUDE.md rule 5).
import type { SignalState, Strategy } from "@/lib/db/schema";

export const NY = "America/New_York";

export const STRATEGY_NAMES: Record<Strategy, string> = { three_eight: "3/8 system", fib_pivot: "Fib Pivot" };

export const STATE_NAMES: Record<SignalState, string> = {
  open: "Open",
  confirmed: "Confirmed",
  target_hit: "Target hit",
  stop_hit: "Stop hit",
  expired: "Expired",
  invalidated: "Invalidated",
  ambiguous: "Ambiguous",
};

/** A price at the instrument's display decimals. */
export function price(value: string | number | null | undefined, decimals: number): string {
  if (value === null || value === undefined || value === "") return "";
  return Number(value).toFixed(decimals);
}

export function ratio(value: string | number): string {
  return Number(value).toFixed(2);
}

/** Signed pips with one decimal when needed: "+41", "-12.5". */
export function pips(value: string | number): string {
  const n = Math.round(Number(value) * 10) / 10;
  const text = Number.isInteger(n) ? Math.abs(n).toFixed(0) : Math.abs(n).toFixed(1);
  return `${n > 0 ? "+" : n < 0 ? "-" : ""}${text}`;
}

const nyTimeFmt = new Intl.DateTimeFormat("en-US", { timeZone: NY, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const nyDayFmt = new Intl.DateTimeFormat("en-US", { timeZone: NY, weekday: "long" });
const nyDateFmt = new Intl.DateTimeFormat("en-US", { timeZone: NY, month: "short", day: "numeric" });

/** "09:30" in New York. */
export function nyTime(at: Date): string {
  return nyTimeFmt.format(at);
}

/** "Sunday 17:00" in New York. */
export function nyDayTime(at: Date): string {
  return `${nyDayFmt.format(at)} ${nyTime(at)}`;
}

/** "Oct 7, 09:30" in New York. */
export function nyDateTime(at: Date): string {
  return `${nyDateFmt.format(at)}, ${nyTime(at)}`;
}

/** "Just now", "12 min ago", "3 h ago", "2 days ago". */
export function age(at: Date, now: Date): string {
  const min = Math.floor((now.getTime() - at.getTime()) / 60_000);
  if (min < 1) return "Just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.floor(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

/** The next 15-minute bar close, when the worker picks up a rule change (spec 05). */
export function nextBarClose(now: Date): Date {
  const bar = 15 * 60_000;
  return new Date(Math.floor(now.getTime() / bar) * bar + bar);
}

const pctSmall = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const pctLarge = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 });

/** A ratio as a percentage: 0.392 -> "39.2%", 20.39 -> "2,039%". */
export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "";
  return Math.abs(value) >= 10 ? pctLarge.format(value) : pctSmall.format(value);
}

/** Stock prices: two decimals (spec 08). */
export function money(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : value.toFixed(2);
}
