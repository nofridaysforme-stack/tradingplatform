import "server-only";
import { timingSafeEqual } from "node:crypto";
import { sql } from "drizzle-orm";
import { db } from "@/lib/db";

/** Sends a plain message when the bot token is set. Never logs or returns the token, which
 *  sits in the request URL. Returns whether Telegram accepted it. */
export async function sendTelegram(chatId: number, text: string): Promise<boolean> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) return false;
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text, disable_web_page_preview: true }),
      signal: AbortSignal.timeout(10_000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export function safeEqual(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false;
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export const CONNECTED = "Connected. You will receive trade alerts here.";
export const EXPIRED =
  "This link has expired or was already used. In the portal, open Settings, Notifications, and tap Connect Telegram again.";
export const GOODBYE = "Disconnected. You will not receive trade alerts here any more.";

/** Connecting Telegram turns it on as an alert channel, and disconnecting turns it off, so an
 *  owner never has to tick the box separately. A missing preferences row is created with the
 *  usual defaults first. */
export async function setTelegramChannel(userId: string, on: boolean): Promise<void> {
  if (!on) {
    await db.execute(
      sql`UPDATE notification_prefs SET channels = array_remove(channels, 'telegram'), updated_at = now()
          WHERE user_id = ${userId} AND 'telegram' = ANY(channels)`,
    );
    return;
  }
  await db.transaction(async (tx) => {
    await tx.execute(
      sql`INSERT INTO notification_prefs (user_id) VALUES (${userId}) ON CONFLICT (user_id) DO NOTHING`,
    );
    await tx.execute(
      sql`UPDATE notification_prefs SET channels = array_append(channels, 'telegram'), updated_at = now()
          WHERE user_id = ${userId} AND NOT ('telegram' = ANY(channels))`,
    );
  });
}
