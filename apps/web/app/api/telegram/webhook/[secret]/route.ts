import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";
import { telegramLinks } from "@/lib/db/schema";
import { CONNECTED, EXPIRED, safeEqual, sendTelegram } from "@/lib/telegram";

const Update = z.object({
  message: z
    .object({
      text: z.string().max(4096).optional(),
      chat: z.object({ id: z.number().int() }),
    })
    .optional(),
});

/** Telegram updates (spec 11). The secret is checked twice: in the path and in Telegram's
 *  X-Telegram-Bot-Api-Secret-Token header. Valid calls always answer 200 so Telegram does
 *  not retry. */
export async function POST(request: Request, ctx: RouteContext<"/api/telegram/webhook/[secret]">) {
  const secret = process.env.TELEGRAM_WEBHOOK_SECRET;
  const { secret: given } = await ctx.params;
  if (!safeEqual(given, secret) || !safeEqual(request.headers.get("x-telegram-bot-api-secret-token"), secret)) {
    return new NextResponse(null, { status: 404 });
  }
  const parsed = Update.safeParse(await request.json().catch(() => null));
  const msg = parsed.success ? parsed.data.message : undefined;
  const match = msg?.text?.match(/^\/start(?:@\w+)?\s+([A-Za-z0-9_-]{16,64})$/);
  if (!msg || !match) return NextResponse.json({ ok: true });
  const [link] = await db
    .update(telegramLinks)
    .set({ chatId: msg.chat.id, linkedAt: new Date(), linkToken: null })
    .where(eq(telegramLinks.linkToken, match[1]!))
    .returning({ userId: telegramLinks.userId });
  await sendTelegram(msg.chat.id, link ? CONNECTED : EXPIRED);
  return NextResponse.json({ ok: true });
}
