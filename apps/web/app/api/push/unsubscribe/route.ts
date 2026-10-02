import { and, eq } from "drizzle-orm";
import { z } from "zod";
import { apiError, apiJson, apiUser, sameOriginJson, unauthorized } from "@/lib/api";
import { db } from "@/lib/db";
import { pushSubscriptions } from "@/lib/db/schema";

const Body = z.object({ endpoint: z.url().max(1000) });

/** Removes one of the caller's own devices. */
export async function POST(request: Request) {
  const user = await apiUser();
  if (!user) return unauthorized();
  if (!sameOriginJson(request)) return apiError(403, "forbidden", "Send this from the portal.");
  const parsed = Body.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return apiError(400, "bad_request", "Missing the device address.");
  await db
    .delete(pushSubscriptions)
    .where(and(eq(pushSubscriptions.endpoint, parsed.data.endpoint), eq(pushSubscriptions.userId, user.id)));
  return apiJson({ ok: true });
}
