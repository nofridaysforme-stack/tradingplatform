import Link from "next/link";
import type { Health } from "@/lib/market";

const COLOR: Record<Health, string> = { ok: "bg-health-ok", warn: "bg-short", down: "bg-error" };
const WORD: Record<Health, string> = { ok: "working", warn: "warning", down: "not reporting" };

export function HealthDot({ health }: { health: Health }) {
  return (
    <Link
      href="/health"
      aria-label={`Health: ${WORD[health]}`}
      className="inline-flex min-h-11 items-center gap-1.5 text-[13px] text-mute no-underline"
    >
      <span aria-hidden="true" className={`size-2 rounded-full ${COLOR[health]}`} />
      Health
    </Link>
  );
}
