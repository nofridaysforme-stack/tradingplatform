import { z } from "zod";
import { apiError, apiJson, apiUser, unauthorized } from "@/lib/api";
import { activeBroker, getSignal } from "@/lib/signals";

export async function GET(_: Request, ctx: RouteContext<"/api/signals/[id]">) {
  const user = await apiUser();
  if (!user) return unauthorized();
  const { id } = await ctx.params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "This signal doesn't exist.");
  const signal = await getSignal(id, await activeBroker(user.activeBrokerId));
  if (!signal) return apiError(404, "not_found", "This signal doesn't exist.");
  return apiJson({ signal });
}
