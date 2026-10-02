import "server-only";
import { Resend } from "resend";
import { messageHtml, messageText, type AlertMessage } from "@/lib/alert-message";
import { sql } from "@/lib/db";
import { checkHeartbeat, type Senders } from "@/lib/watchdog";

export const CHECK_EVERY_MS = 60_000;

/** Email and Telegram from the environment; a channel without its settings is left out. */
export function configuredSenders(): Senders {
  const senders: Senders = {};
  const key = process.env.RESEND_API_KEY;
  const from = process.env.EMAIL_FROM;
  if (key && from) {
    const resend = new Resend(key);
    senders.email = async (to: string, m: AlertMessage) => {
      const { error } = await resend.emails.send({ from, to, subject: m.title, text: messageText(m), html: messageHtml(m) });
      if (error) throw Object.assign(new Error("Resend rejected the email"), { name: `resend_${error.name}` });
    };
  }
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (token) {
    senders.telegram = async (chatId: number, m: AlertMessage) => {
      const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId, text: messageText(m), disable_web_page_preview: true }),
        signal: AbortSignal.timeout(10_000),
      }).catch(() => null);
      if (!res?.ok) throw Object.assign(new Error("Telegram send failed"), { name: `telegram_${res?.status ?? "unreachable"}` });
    };
  }
  return senders;
}

declare global {
  var __watchdog: ReturnType<typeof setInterval> | undefined;
}

function log(msg: string, extra: Record<string, unknown> = {}) {
  console.log(JSON.stringify({ ts: new Date().toISOString(), level: "info", logger: "watchdog", msg, ...extra }));
}

/** Starts the once-a-minute heartbeat check. HEALTH_WATCHDOG=off turns it off (tests). */
export function startWatchdog(): void {
  if (process.env.HEALTH_WATCHDOG === "off" || globalThis.__watchdog) return;
  const baseUrl = process.env.APP_URL ?? process.env.AUTH_URL ?? "http://localhost:3000";
  const run = async () => {
    try {
      const result = await checkHeartbeat(sql, {
        now: new Date(),
        baseUrl,
        opsEmail: process.env.OPS_ALERT_EMAIL,
        senders: configuredSenders(),
      });
      if (result.step === "send") log("scanner heartbeat late, alert raised", { sent: result.sent, failed: result.failed });
    } catch (err) {
      // A database outage is the uptime monitor's to report; try again next minute.
      log("heartbeat check failed", { level: "warning", error: err instanceof Error ? err.name : "unknown" });
    }
  };
  globalThis.__watchdog = setInterval(run, CHECK_EVERY_MS);
  globalThis.__watchdog.unref();
  log("heartbeat check started", { every_seconds: CHECK_EVERY_MS / 1000 });
}
