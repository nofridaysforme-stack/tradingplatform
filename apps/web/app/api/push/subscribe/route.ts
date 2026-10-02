import { z } from "zod";
import { apiError, apiJson, apiUser, sameOriginJson, unauthorized } from "@/lib/api";
import { db } from "@/lib/db";
import { pushSubscriptions } from "@/lib/db/schema";

const B64URL = /^[A-Za-z0-9_=-]+$/;

const Subscription = z.object({
  endpoint: z.url().max(1000).refine((u) => u.startsWith("https://"), "https only"),
  keys: z.object({
    p256dh: z.string().min(16).max(200).regex(B64URL),
    auth: z.string().min(8).max(100).regex(B64URL),
  }),
});

/** Stores this device's push subscription for the signed-in owner (spec 11). */
export async function POST(request: Request) {
  const user = await apiUser();
  if (!user) return unauthorized();
  if (!sameOriginJson(request)) return apiError(403, "forbidden", "Send this from the portal.");
  const parsed = Subscription.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return apiError(400, "bad_request", "This browser sent a subscription the portal can't use.");
  const { endpoint, keys } = parsed.data;
  const userAgent = request.headers.get("user-agent")?.slice(0, 300) ?? null;
  await db
    .insert(pushSubscriptions)
    .values({ userId: user.id, endpoint, p256dh: keys.p256dh, auth: keys.auth, userAgent })
    .onConflictDoUpdate({
      target: pushSubscriptions.endpoint,
      set: { userId: user.id, p256dh: keys.p256dh, auth: keys.auth, userAgent },
    });
  return apiJson({ ok: true });
}
