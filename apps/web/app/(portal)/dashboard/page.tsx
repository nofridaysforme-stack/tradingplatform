import type { Metadata } from "next";
import { IndicatorRing } from "@/components/ring";

export const metadata: Metadata = { title: "Signals · Trading desk" };

const EMPTY = Array(8).fill("off") as "off"[];

// The live dashboard (signals, status line, daily goal, stock digest) arrives in the next
// pull request. Until then it shows the designed empty state.
export default function DashboardPage() {
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Signals</h1>
      </header>
      <section className="flex flex-col items-center gap-4 border-t border-rule px-5 py-14 text-center">
        <IndicatorRing states={EMPTY} direction="long" size={72} showCount={false} label="No signals" />
        <p className="m-0 max-w-[280px] text-sm text-ink-2">
          No open signals. The scanner checks every 15 minutes while the market is open.
        </p>
      </section>
    </main>
  );
}
