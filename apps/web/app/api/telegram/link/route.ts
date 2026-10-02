import { randomBytes } from "node:crypto";
import { apiError, apiJson, apiUser, sameOriginJson, unauthorized } from "@/lib/api";
import { db } from "@/lib/db";
import { telegramLinks } from "@/lib/db/schema";

/** Creates a one-time link token and returns the bot deep link (spec 11, spec 14). */
export async function POST(request: Request) {
  const user = await apiUser();
  if (!user) return unauthorized();
  if (!sameOriginJson(request)) return apiError(403, "forbidden", "Send this from the portal.");
  const bot = process.env.TELEGRAM_BOT_USERNAME;
  if (!bot || !/^[A-Za-z0-9_]{5,32}$/.test(bot)) {
    return apiError(503, "not_configured", "Telegram isn't set up yet. An admin needs to add the bot.");
  }
  const token = randomBytes(24).toString("base64url");
  await db
    .insert(telegramLinks)
    .values({ userId: user.id, linkToken: token })
    .onConflictDoUpdate({ target: telegramLinks.userId, set: { linkToken: token } });
  return apiJson({ url: `https://t.me/${bot}?start=${token}` });
}
