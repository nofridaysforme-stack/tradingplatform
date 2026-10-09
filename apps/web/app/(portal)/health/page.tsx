import type { Metadata } from "next";
import { HealthDot } from "@/components/health-dot";
import { forexEnabled } from "@/lib/app-settings";
import { age, nyDateTime } from "@/lib/format";
import { healthDetail, type JobView } from "@/lib/health";
import { marketView } from "@/lib/market";
import { requireUser } from "@/lib/session";

export const metadata: Metadata = { title: "Health · Trading desk" };

const JOB_NAMES: Record<string, string> = {
  forex_bar_close: "15-minute bar check",
  forex_day_roll: "Day roll (levels)",
  stock_eod: "Stock screen",
  backfill: "Backfill",
  ticker_refresh: "Ticker refresh",
  retention: "Clean-up",
  heartbeat: "Heartbeat",
};

export default async function HealthPage() {
  const user = await requireUser();
  const now = new Date();
  const [h, forex] = await Promise.all([healthDetail(now), forexEnabled()]);
  const view = marketView(h.heartbeat ? new Date(h.heartbeat.at) : null, h.market, now, forex);
  const admin = user.role === "admin";
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <div className="flex items-center justify-between gap-3">
          <h1 className="m-0 text-[22px] font-semibold leading-tight">Health</h1>
          <HealthDot health={view.health} />
        </div>
        <p className="m-0 mt-1 text-[13px] text-ink-2">{view.line}</p>
      </header>

      <section aria-labelledby="worker-h" className="border-t border-rule px-5 py-4">
        <h2 id="worker-h" className="m-0 mb-2 text-base font-semibold">
          Scanner
        </h2>
        <dl className="m-0 text-sm">
          <Row label="Heartbeat" value={h.heartbeat ? `${age(new Date(h.heartbeat.at), now)} (version ${h.heartbeat.version ?? "unknown"})` : "Never reported. Check the scanner service in Railway."} warn={view.health === "down"} />
          {forex && <Row label="Last day roll" value={jobText(h.latest.forex_day_roll, now)} warn={h.latest.forex_day_roll?.ok === false} />}
          <Row label="Last stock screen" value={jobText(h.latest.stock_eod, now)} warn={h.latest.stock_eod?.ok === false} />
          <Row label="Last backfill" value={jobText(h.latest.backfill, now)} warn={h.latest.backfill?.ok === false} />
        </dl>
      </section>

      <section aria-labelledby="providers-h" className="border-t border-rule px-5 py-4">
        <h2 id="providers-h" className="m-0 mb-2 text-base font-semibold">
          Data providers
        </h2>
        <dl className="m-0 text-sm">
          {forex ? (
            <Row
              label="OANDA (forex)"
              value={h.latest.forex_bar_close ? jobText(h.latest.forex_bar_close, now) : "No bar checks yet. The scanner needs OANDA_API_TOKEN in its settings."}
              warn={h.latest.forex_bar_close?.ok === false}
            />
          ) : (
            <Row label="OANDA (forex)" value="Not used while forex is paused." warn={false} />
          )}
          <Row
            label="Massive (stocks)"
            value={h.latest.stock_eod ? jobText(h.latest.stock_eod, now) : "No stock screens yet. The scanner needs MASSIVE_API_KEY in its settings."}
            warn={h.latest.stock_eod?.ok === false}
          />
        </dl>
      </section>

      {forex && (
        <section aria-labelledby="pairs-h" className="border-t border-rule px-5 py-4">
          <h2 id="pairs-h" className="m-0 mb-2 text-base font-semibold">
            Last completed bar per pair
          </h2>
          <dl className="m-0 text-sm">
            {h.pairs.map((p) => (
              <Row
                key={p.symbol}
                label={p.symbol}
                value={p.lastBar ? `${nyDateTime(new Date(new Date(p.lastBar).getTime() + 15 * 60_000))} NY${p.stale ? " · Stale: alerts paused" : ""}` : "No bars yet"}
                warn={p.stale}
              />
            ))}
          </dl>
        </section>
      )}

      {admin && (
        <>
          <section aria-labelledby="runs-h" className="border-t border-rule px-5 py-4">
            <h2 id="runs-h" className="m-0 mb-2 text-base font-semibold">
              Job runs, last 24 hours
            </h2>
            {h.runs.length === 0 ? (
              <p className="m-0 text-sm text-ink-2">No job runs in the last 24 hours.</p>
            ) : (
              <ul className="m-0 list-none p-0 text-sm">
                {h.runs.map((r) => (
                  <li key={r.id} className="border-b border-rule-soft py-2">
                    {r.ok === false ? (
                      <details open>
                        <summary className="cursor-pointer">
                          <RunLine r={r} now={now} />
                        </summary>
                        <pre className="m-0 mt-1.5 overflow-x-auto rounded-control border border-rule-soft bg-input p-2 text-xs whitespace-pre-wrap text-ink-2">
                          {JSON.stringify(r.detail, null, 2)}
                        </pre>
                      </details>
                    ) : (
                      <RunLine r={r} now={now} />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="delivery-h" className="border-t border-rule px-5 py-4">
            <h2 id="delivery-h" className="m-0 mb-2 text-base font-semibold">
              Notification delivery, last 24 hours
            </h2>
            {h.deliveries.length === 0 ? (
              <p className="m-0 text-sm text-ink-2">No notifications in the last 24 hours.</p>
            ) : (
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="text-xs text-mute">
                    <th scope="col" className="pb-1.5 text-left font-normal">
                      Channel
                    </th>
                    <th scope="col" className="pb-1.5 text-left font-normal">
                      Status
                    </th>
                    <th scope="col" className="pb-1.5 text-right font-normal">
                      Count
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {h.deliveries.map((d) => (
                    <tr key={`${d.channel}-${d.status}`} className="border-t border-rule-soft">
                      <td className="py-1.5">{d.channel}</td>
                      <td className="py-1.5">{d.status}</td>
                      <td className="py-1.5 text-right">{d.n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function jobText(j: JobView | null, now: Date): string {
  if (!j) return "Not run yet";
  const when = `${age(new Date(j.startedAt), now)} (${nyDateTime(new Date(j.startedAt))} NY)`;
  if (j.ok === false) return `Failed ${when}`;
  if (j.ok === null) return `Running since ${when}`;
  return `Finished ${when}`;
}

function RunLine({ r, now }: { r: JobView; now: Date }) {
  return (
    <span className="inline-flex flex-wrap justify-between gap-x-3">
      <span className={r.ok === false ? "font-semibold" : ""}>
        {JOB_NAMES[r.job] ?? r.job}
        {r.ok === false ? " · Failed" : r.ok === null ? " · Running" : ""}
      </span>
      <span className="text-[13px] text-mute">{age(new Date(r.startedAt), now)}</span>
    </span>
  );
}

function Row({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 border-b border-rule-soft py-2">
      <dt className="text-ink-2">{label}</dt>
      <dd className={`m-0 text-right ${warn ? "font-semibold text-ink" : "text-ink"}`}>
        {warn && <span aria-hidden="true">! </span>}
        {value}
      </dd>
    </div>
  );
}
