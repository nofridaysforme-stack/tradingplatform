import type { Metadata } from "next";
import { requireForex } from "@/lib/app-settings";
import { marketView } from "@/lib/market";
import { requireUser } from "@/lib/session";
import { activeBroker, dailyGoal, heartbeat, listBrokers, listSignals, stockDigest } from "@/lib/signals";
import { Dashboard } from "./dashboard";

export const metadata: Metadata = { title: "Signals · Trading desk" };

export default async function DashboardPage() {
  const user = await requireUser();
  await requireForex();
  const now = new Date();
  const [broker, brokers, hb, digest] = await Promise.all([
    activeBroker(user.activeBrokerId),
    listBrokers(),
    heartbeat(),
    stockDigest(),
  ]);
  const [signals, goal] = await Promise.all([listSignals(broker), dailyGoal(hb?.market?.trading_day ?? null)]);
  return (
    <Dashboard
      serverNow={now.toISOString()}
      signals={signals}
      market={marketView(hb?.at ?? null, hb?.market ?? null, now)}
      broker={broker ? { id: broker.id, name: broker.name } : null}
      brokers={brokers.map((b) => ({ id: b.id, name: b.name }))}
      goal={goal}
      digest={digest}
    />
  );
}
