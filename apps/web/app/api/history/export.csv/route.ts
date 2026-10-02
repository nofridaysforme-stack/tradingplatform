import { apiUser, unauthorized } from "@/lib/api";
import { csvLine } from "@/lib/csv";
import { allRows, parseFilter } from "@/lib/history";

const HEADER = [
  "trading_day",
  "closed_at_utc",
  "strategy",
  "instrument",
  "direction",
  "outcome",
  "result_pips",
  "reward_risk",
  "provisional",
  "rule_versions",
  "signal_id",
];

export async function GET(request: Request) {
  if (!(await apiUser())) return unauthorized();
  const rows = await allRows(parseFilter(Object.fromEntries(new URL(request.url).searchParams)));
  const lines = [
    csvLine(HEADER),
    ...rows.map((r) =>
      csvLine([
        r.trading_day,
        r.closed_at,
        r.strategy,
        r.instrument,
        r.direction,
        r.outcome,
        r.result_pips,
        r.reward_risk,
        r.has_provisional,
        Object.entries(r.version_set)
          .map(([k, v]) => `${k} v${v}`)
          .join("; "),
        r.id,
      ]),
    ),
  ];
  const stamp = new Date().toISOString().slice(0, 10);
  return new Response(lines.join("\r\n") + "\r\n", {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="signal-history-${stamp}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
