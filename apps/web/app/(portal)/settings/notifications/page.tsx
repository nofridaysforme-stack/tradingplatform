import { asc, desc, eq } from "drizzle-orm";
import type { Metadata } from "next";
import Link from "next/link";
import { forexEnabled } from "@/lib/app-settings";
import { db } from "@/lib/db";
import {
  instruments,
  notificationPrefs,
  notifications,
  pushSubscriptions,
  telegramLinks,
} from "@/lib/db/schema";
import { age } from "@/lib/format";
import { requireUser } from "@/lib/session";
import {
  PrefsForm,
  TelegramControl,
  TestButton,
  type PrefsValues,
} from "./forms";
import { PushControl } from "./push-control";

export const metadata: Metadata = { title: "Notifications · Trading desk" };

const STATUS: Record<string, string> = {
  queued: "Sending",
  sent: "Sent",
  failed: "Failed",
  skipped: "Skipped",
};
const CHANNEL: Record<string, string> = {
  webpush: "Push",
  email: "Email",
  telegram: "Telegram",
};
const REASONS: Record<string, string> = {
  not_configured: "channel not set up on the server yet",
  no_subscription: "no device has notifications turned on",
  telegram_not_linked: "Telegram not connected",
  quiet_hours: "quiet hours",
  updates_off: "updates are off",
  strategy_off: "that strategy is off",
  pair_off: "that pair is off",
};
const KINDS: Record<string, string> = {
  signal: "Signal",
  update: "Update",
  digest: "Stock digest",
  holding: "Holding",
  health: "Health",
  test: "Test",
};

export default async function NotificationsPage() {
  const user = await requireUser();
  const now = new Date();
  const forex = await forexEnabled();
  const [[prefs], pairs, [link], devices, recent] = await Promise.all([
    db
      .select()
      .from(notificationPrefs)
      .where(eq(notificationPrefs.userId, user.id)),
    db
      .select({ id: instruments.id, symbol: instruments.symbol })
      .from(instruments)
      .where(eq(instruments.enabled, true))
      .orderBy(asc(instruments.sortOrder), asc(instruments.symbol)),
    db.select().from(telegramLinks).where(eq(telegramLinks.userId, user.id)),
    db
      .select({ id: pushSubscriptions.id })
      .from(pushSubscriptions)
      .where(eq(pushSubscriptions.userId, user.id)),
    db
      .select()
      .from(notifications)
      .where(eq(notifications.userId, user.id))
      .orderBy(desc(notifications.createdAt))
      .limit(8),
  ]);
  const linked = Boolean(link?.chatId);
  const values: PrefsValues = {
    webpush: prefs ? prefs.channels.includes("webpush") : true,
    telegram: prefs ? prefs.channels.includes("telegram") : false,
    strategies: prefs?.strategies ?? ["three_eight", "fib_pivot", "stocks"],
    instrumentIds: prefs?.instrumentIds ?? null,
    quietStart: prefs?.quietStart?.slice(0, 5) ?? null,
    quietEnd: prefs?.quietEnd?.slice(0, 5) ?? null,
    includeUpdates: prefs?.includeUpdates ?? true,
  };
  return (
    <main>
      <nav className="px-5 pt-4">
        <Link
          href="/settings"
          className="inline-flex min-h-11 items-center text-sm text-link"
        >
          <span aria-hidden="true">‹&nbsp;</span>Settings
        </Link>
      </nav>
      <header className="px-5 pt-1.5 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">
          Notifications
        </h1>
        <p className="m-0 mt-1 max-w-[62ch] text-[13px] text-mute">
          Alerts for new signals, updates, the evening stock digest, and your
          holdings. Email always works; push and Telegram are faster on phones.
        </p>
      </header>

      <section
        aria-labelledby="device-h"
        className="border-t border-rule px-5 py-5"
      >
        <h2 id="device-h" className="m-0 mb-1 text-[15px] font-semibold">
          This device
        </h2>
        <p className="m-0 mb-3 text-[13px] text-mute">
          Push is on for {devices.length} device
          {devices.length === 1 ? "" : "s"}.
        </p>
        <PushControl />
      </section>

      <section
        aria-labelledby="telegram-h"
        className="border-t border-rule px-5 py-5"
      >
        <h2 id="telegram-h" className="m-0 mb-3 text-[15px] font-semibold">
          Telegram
        </h2>
        <TelegramControl
          linked={linked}
          configured={Boolean(process.env.TELEGRAM_BOT_USERNAME)}
        />
      </section>

      <section
        aria-labelledby="prefs-h"
        className="border-t border-rule px-5 py-5"
      >
        <h2 id="prefs-h" className="sr-only">
          Preferences
        </h2>
        <PrefsForm values={values} pairs={pairs} telegramLinked={linked} forex={forex} />
      </section>

      <section
        aria-labelledby="test-h"
        className="border-t border-rule px-5 py-5"
      >
        <h2 id="test-h" className="m-0 mb-3 text-[15px] font-semibold">
          Test
        </h2>
        <TestButton />
        <h3 className="m-0 mt-5 mb-1 text-sm font-semibold">
          Recent deliveries
        </h3>
        {recent.length === 0 ? (
          <p className="m-0 text-[13px] text-ink-2">Nothing sent to you yet.</p>
        ) : (
          <ul className="m-0 list-none p-0 text-[13px]">
            {recent.map((n) => (
              <li
                key={n.id}
                className="flex flex-wrap justify-between gap-x-3 border-b border-rule-soft py-2"
              >
                <span>
                  {KINDS[n.kind] ?? n.kind} · {CHANNEL[n.channel] ?? n.channel}{" "}
                  · {STATUS[n.status] ?? n.status}
                  {n.status !== "sent" && n.error ? (
                    <span className="text-ink-2">
                      {" "}
                      ({REASONS[n.error] ?? n.error})
                    </span>
                  ) : null}
                </span>
                <span className="text-mute">{age(n.createdAt, now)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
