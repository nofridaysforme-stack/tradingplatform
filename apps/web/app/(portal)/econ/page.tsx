import type { Metadata } from "next";
import { requireForex } from "@/lib/app-settings";
import { econWindow, type EconEvent } from "@/lib/econ";
import { nyDateTime } from "@/lib/format";
import { requireUser } from "@/lib/session";
import { AddEventForm, DeleteEvent } from "./forms";

export const metadata: Metadata = { title: "Econ events · Trading desk" };

const IMPACT: Record<EconEvent["impact"], string> = { high: "High", medium: "Medium", low: "Low" };

export default async function EconPage() {
  const user = await requireUser();
  await requireForex();
  const admin = user.role === "admin";
  const { upcoming, recent } = await econWindow(new Date());
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Econ events</h1>
        <p className="m-0 mt-1 max-w-[62ch] text-[13px] text-mute">
          Scheduled reports the 3/8 system watches around entries. Times are New York.
        </p>
      </header>
      <Events id="upcoming" title="Upcoming" events={upcoming} admin={admin} empty="No events in the next month." />
      <Events id="recent" title="Last 7 days" events={recent} admin={admin} empty="No events in the last week." />
      {admin && (
        <section aria-labelledby="add-h" className="border-t border-rule px-5 py-5">
          <h2 id="add-h" className="m-0 mb-3 text-base font-semibold">
            Add event
          </h2>
          <AddEventForm />
        </section>
      )}
    </main>
  );
}

function Events({ id, title, events, admin, empty }: { id: string; title: string; events: EconEvent[]; admin: boolean; empty: string }) {
  return (
    <section aria-labelledby={`${id}-h`} className="border-t border-rule">
      <h2 id={`${id}-h`} className="m-0 px-5 pt-4 text-base font-semibold">
        {title}
      </h2>
      {events.length === 0 ? (
        <p className="m-0 px-5 py-4 text-sm text-ink-2">{empty}</p>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead>
              <tr className="text-xs text-mute">
                <th scope="col" className="border-b border-rule px-2 py-2 pl-5 text-left font-normal">
                  Time
                </th>
                <th scope="col" className="border-b border-rule px-2 py-2 text-left font-normal">
                  Currency
                </th>
                <th scope="col" className="border-b border-rule px-2 py-2 text-left font-normal">
                  Event
                </th>
                <th scope="col" className="border-b border-rule px-2 py-2 text-left font-normal">
                  Impact
                </th>
                {admin && (
                  <th scope="col" className="border-b border-rule px-2 py-2 pr-5 font-normal">
                    <span className="sr-only">Actions</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-b border-rule-soft">
                  <td className="px-2 py-2 pl-5 whitespace-nowrap">{nyDateTime(new Date(e.at))}</td>
                  <td className="px-2 py-2">{e.currency}</td>
                  <td className="px-2 py-2">{e.title}</td>
                  <td className={`px-2 py-2 ${e.impact === "high" ? "font-semibold" : ""}`}>{IMPACT[e.impact]}</td>
                  {admin && (
                    <td className="px-2 py-2 pr-5 text-right">
                      <DeleteEvent id={e.id} title={`${e.currency} ${e.title}`} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
