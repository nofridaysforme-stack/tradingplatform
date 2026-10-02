"use server";

import { and, count, eq, gt, inArray, sql as dsql } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { db } from "@/lib/db";
import {
  instruments,
  notificationPrefs,
  notifications,
  telegramLinks,
  type ChannelKind,
} from "@/lib/db/schema";
import { requireUser } from "@/lib/session";
import { GOODBYE, sendTelegram } from "@/lib/telegram";

export interface PrefsState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
}

const STRATEGIES = ["three_eight", "fib_pivot", "stocks"] as const;
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;
const TEST_LIMIT = 3; // per 10 minutes

/** Spec 11 preferences. Email is always on: it is the fallback channel. */
export async function savePrefs(
  _: PrefsState,
  form: FormData,
): Promise<PrefsState> {
  const user = await requireUser();
  const channels: ChannelKind[] = ["email"];
  if (form.get("webpush") === "on") channels.unshift("webpush");
  if (form.get("telegram") === "on") channels.push("telegram");
  const strategies = form
    .getAll("strategies")
    .map(String)
    .filter((s): s is (typeof STRATEGIES)[number] =>
      (STRATEGIES as readonly string[]).includes(s),
    );
  const fieldErrors: Record<string, string> = {};
  let instrumentIds: string[] | null = null;
  if (form.get("pairs") === "some") {
    const ids = z.array(z.uuid()).safeParse(form.getAll("instrumentIds"));
    if (!ids.success || ids.data.length === 0)
      fieldErrors.pairs = "Choose at least one pair, or all pairs.";
    else {
      const found = await db
        .select({ id: instruments.id })
        .from(instruments)
        .where(inArray(instruments.id, ids.data));
      if (found.length !== ids.data.length)
        fieldErrors.pairs = "One of those pairs no longer exists.";
      instrumentIds = ids.data;
    }
  }
  const quiet = form.get("quiet") === "on";
  const start = String(form.get("quietStart") ?? "");
  const end = String(form.get("quietEnd") ?? "");
  if (quiet) {
    if (!HHMM.test(start))
      fieldErrors.quietStart = "Use 24-hour time, for example 22:00.";
    if (!HHMM.test(end))
      fieldErrors.quietEnd = "Use 24-hour time, for example 07:00.";
    if (HHMM.test(start) && start === end)
      fieldErrors.quietEnd = "Quiet hours need different start and end times.";
  }
  if (Object.keys(fieldErrors).length)
    return { error: "Check the highlighted fields.", fieldErrors };
  const includeUpdates = form.get("includeUpdates") === "on";
  // Enum arrays and times need explicit casts.
  await db.execute(dsql`
    insert into notification_prefs (user_id, channels, strategies, instrument_ids, quiet_start, quiet_end, include_updates, updated_at)
    values (${user.id}, ${`{${channels.join(",")}}`}::channel_kind[], ${`{${strategies.join(",")}}`}::strategy_key[],
            ${instrumentIds ? `{${instrumentIds.join(",")}}` : null}::uuid[], ${quiet ? start : null}::time, ${quiet ? end : null}::time,
            ${includeUpdates}, now())
    on conflict (user_id) do update set channels = excluded.channels, strategies = excluded.strategies,
      instrument_ids = excluded.instrument_ids, quiet_start = excluded.quiet_start, quiet_end = excluded.quiet_end,
      include_updates = excluded.include_updates, updated_at = now()`);
  revalidatePath("/settings/notifications");
  return { ok: true, message: "Notification settings saved" };
}

/** Queues a test on each channel the owner has on; the scanner sends it within seconds. */
export async function sendTestNotification(): Promise<PrefsState> {
  const user = await requireUser();
  const [recent] = await db
    .select({ n: count() })
    .from(notifications)
    .where(
      and(
        eq(notifications.userId, user.id),
        eq(notifications.kind, "test"),
        gt(notifications.createdAt, new Date(Date.now() - 10 * 60_000)),
      ),
    );
  const [prefs] = await db
    .select({ channels: notificationPrefs.channels })
    .from(notificationPrefs)
    .where(eq(notificationPrefs.userId, user.id));
  const channels: ChannelKind[] = prefs?.channels ?? ["webpush", "email"];
  if ((recent?.n ?? 0) + channels.length > TEST_LIMIT * channels.length) {
    return {
      error: "You sent several tests just now. Try again in 10 minutes.",
    };
  }
  await db.insert(notifications).values(
    channels.map((channel) => ({
      userId: user.id,
      kind: "test",
      channel,
      payload: {},
    })),
  );
  revalidatePath("/settings/notifications");
  return {
    ok: true,
    message: "Test notification sent. It arrives within a minute.",
  };
}

export async function disconnectTelegram(): Promise<PrefsState> {
  const user = await requireUser();
  const [link] = await db
    .delete(telegramLinks)
    .where(eq(telegramLinks.userId, user.id))
    .returning();
  if (link?.chatId) await sendTelegram(link.chatId, GOODBYE);
  revalidatePath("/settings/notifications");
  return { ok: true, message: "Telegram disconnected" };
}
