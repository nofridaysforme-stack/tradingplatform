// The one health alert the scanner cannot send itself: "scanner heartbeat is late" (spec 11).
// While the scanner is stopped nothing else is running to notice, so the web service checks the
// heartbeat every minute and alerts admins (email always, Telegram when linked) and
// OPS_ALERT_EMAIL. It shares the scanner's health_alerts row: at most one alert an hour, and
// when the scanner comes back its own health check sees the row and sends "Resolved".
// No database or environment imports here so the end-to-end tests can drive it directly.
import type postgres from "postgres";
import { HEARTBEAT_CONDITION, heartbeatAlert, type AlertMessage } from "@/lib/alert-message";
import { HEARTBEAT_STALE_MS } from "@/lib/market";

export const REPEAT_MS = 60 * 60_000;
// Owners who never saved notification settings get the scanner's defaults (spec 11).
const DEFAULT_CHANNELS = ["webpush", "email"];

export interface AlertState {
  lastSentAt: Date | null;
  resolvedAt: Date | null;
}

export type Step = "fresh" | "send" | "wait";

/** Whether to alert now. A resolved or never-sent condition starts over. */
export function nextStep(heartbeatAt: Date | null, state: AlertState | null, now: Date): Step {
  if (heartbeatAt && now.getTime() - heartbeatAt.getTime() <= HEARTBEAT_STALE_MS) return "fresh";
  if (!state || state.resolvedAt || !state.lastSentAt) return "send";
  return now.getTime() - state.lastSentAt.getTime() >= REPEAT_MS ? "send" : "wait";
}

export interface Senders {
  email?: (to: string, message: AlertMessage) => Promise<void>;
  telegram?: (chatId: number, message: AlertMessage) => Promise<void>;
}

interface Delivery {
  userId: string | null;
  channel: "email" | "telegram";
  to: string | null;
  chatId: number | null;
  status: "sent" | "failed" | "skipped";
  error: string | null;
}

/** "health:heartbeat_stale:20261002T1431", the scanner's dedupe key format (UTC minute). */
export function dedupeKey(now: Date): string {
  const s = now.toISOString();
  return `health:${HEARTBEAT_CONDITION}:${s.slice(0, 4)}${s.slice(5, 7)}${s.slice(8, 10)}T${s.slice(11, 13)}${s.slice(14, 16)}`;
}

function errorText(err: unknown): string {
  // Never the raw error: provider errors can carry request URLs, and the Telegram URL holds the token.
  return err instanceof Error && err.name && err.name !== "Error" ? err.name : "send_failed";
}

// The app's client is shared with Drizzle, which reads timestamps as strings and sends Date
// and JSON parameters unconverted; so read through toDate and send ISO strings and JSON text.
const toDate = (v: Date | string | null | undefined): Date | null => (v == null ? null : new Date(v));

export interface CheckResult {
  step: Step;
  sent: number;
  failed: number;
}

export async function checkHeartbeat(
  sql: postgres.Sql,
  opts: { now: Date; baseUrl: string; opsEmail?: string | null; senders: Senders },
): Promise<CheckResult> {
  const { now, senders } = opts;
  const at = now.toISOString();
  const [hb] = await sql<{ at: Date | string }[]>`SELECT at FROM worker_heartbeat LIMIT 1`;
  if (nextStep(toDate(hb?.at), null, now) === "fresh") return { step: "fresh", sent: 0, failed: 0 };

  return sql.begin(async (tx) => {
    // The row lock keeps two web instances, or web and scanner, from both alerting.
    await tx`INSERT INTO health_alerts (condition, first_seen_at, detail)
             VALUES (${HEARTBEAT_CONDITION}, ${at}, '{}'::jsonb) ON CONFLICT (condition) DO NOTHING`;
    const [row] = await tx<{ last_sent_at: Date | string | null; resolved_at: Date | string | null }[]>`
      SELECT last_sent_at, resolved_at FROM health_alerts WHERE condition = ${HEARTBEAT_CONDITION} FOR UPDATE`;
    // Read again under the lock: the scanner may have just come back.
    const [again] = await tx<{ at: Date | string }[]>`SELECT at FROM worker_heartbeat LIMIT 1`;
    const state = { lastSentAt: toDate(row.last_sent_at), resolvedAt: toDate(row.resolved_at) };
    const step = nextStep(toDate(again?.at), state, now);
    if (step !== "send") return { step, sent: 0, failed: 0 };

    const message = heartbeatAlert(opts.baseUrl);
    if (state.resolvedAt) {
      await tx`UPDATE health_alerts SET first_seen_at = ${at}, last_sent_at = NULL, resolved_at = NULL
               WHERE condition = ${HEARTBEAT_CONDITION}`;
    }
    await tx`UPDATE health_alerts SET detail = ${JSON.stringify({ text: message.body, source: "web" })}::jsonb
             WHERE condition = ${HEARTBEAT_CONDITION}`;

    const admins = await tx<{ id: string; email: string; channels: string[] | null; chat_id: string | null }[]>`
      SELECT u.id, u.email, p.channels::text[] AS channels, t.chat_id::text AS chat_id
      FROM users u
      LEFT JOIN notification_prefs p ON p.user_id = u.id
      LEFT JOIN telegram_links t ON t.user_id = u.id AND t.chat_id IS NOT NULL
      WHERE u.active AND u.role = 'admin'
      ORDER BY u.email`;
    const planned: Delivery[] = [];
    for (const a of admins) {
      planned.push({ userId: a.id, channel: "email", to: a.email, chatId: null, status: "sent", error: null });
      if ((a.channels ?? DEFAULT_CHANNELS).includes("telegram")) {
        planned.push({
          userId: a.id,
          channel: "telegram",
          to: null,
          chatId: a.chat_id ? Number(a.chat_id) : null,
          status: "sent",
          error: a.chat_id ? null : "telegram_not_linked",
        });
      }
    }
    const ops = opts.opsEmail?.trim();
    if (ops && !admins.some((a) => a.email.toLowerCase() === ops.toLowerCase())) {
      planned.push({ userId: null, channel: "email", to: ops, chatId: null, status: "sent", error: null });
    }

    await Promise.all(
      planned.map(async (d) => {
        if (d.error) {
          d.status = "skipped";
          return;
        }
        const send =
          d.channel === "email"
            ? senders.email && d.to && senders.email.bind(null, d.to)
            : senders.telegram && d.chatId !== null && senders.telegram.bind(null, d.chatId);
        if (!send) {
          [d.status, d.error] = ["skipped", "not_configured"];
          return;
        }
        try {
          await send(message);
        } catch (err) {
          [d.status, d.error] = ["failed", errorText(err)];
        }
      }),
    );

    const key = dedupeKey(now);
    for (const d of planned) {
      const payload = { title: message.title, body: message.body, url: message.url, ...(d.userId ? {} : { to: d.to }) };
      await tx`INSERT INTO notifications (user_id, kind, channel, status, attempts, error, payload, dedupe_key, sent_at)
               VALUES (${d.userId}, 'health', ${d.channel}, ${d.status}, ${d.status === "skipped" ? 0 : 1},
                       ${d.error}, ${JSON.stringify(payload)}::jsonb, ${key}, ${d.status === "sent" ? at : null})
               ON CONFLICT DO NOTHING`;
    }
    await tx`UPDATE health_alerts SET last_sent_at = ${at} WHERE condition = ${HEARTBEAT_CONDITION}`;
    return {
      step,
      sent: planned.filter((d) => d.status === "sent").length,
      failed: planned.filter((d) => d.status === "failed").length,
    };
  });
}
