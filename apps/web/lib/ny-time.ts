import { NY } from "@/lib/format";

const parts = new Intl.DateTimeFormat("en-US", {
  timeZone: NY,
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/** "2026-10-07T08:30" as New York wall time for an instant. */
export function toNyLocal(at: Date): string {
  const p = Object.fromEntries(parts.formatToParts(at).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

/** The UTC instant for a New York wall time ("2026-10-07T08:30"), across daylight saving.
 *  Returns null for a malformed value. */
export function nyLocalToUtc(local: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(local);
  if (!m) return null;
  const [, y, mo, d, h, mi] = m.map(Number) as [number, number, number, number, number, number];
  const wall = Date.UTC(y, mo - 1, d, h, mi);
  if (Number.isNaN(wall)) return null;
  // Guess with the offset at the wall time, then correct once with the offset at the guess.
  let guess = wall;
  for (let i = 0; i < 2; i++) {
    const seen = toNyLocal(new Date(guess));
    const seenMs = Date.UTC(+seen.slice(0, 4), +seen.slice(5, 7) - 1, +seen.slice(8, 10), +seen.slice(11, 13), +seen.slice(14, 16));
    guess += wall - seenMs;
  }
  return toNyLocal(new Date(guess)) === local ? new Date(guess) : null;
}
