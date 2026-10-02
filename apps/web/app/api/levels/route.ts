import { z } from "zod";
import { apiError, apiJson, apiUser, unauthorized } from "@/lib/api";
import { listPairs, pairLevels } from "@/lib/levels";

const Query = z.object({
  instrument: z.string().min(1).max(20),
  day: z.iso.date().optional(),
});

export async function GET(request: Request) {
  if (!(await apiUser())) return unauthorized();
  const parsed = Query.safeParse(Object.fromEntries(new URL(request.url).searchParams));
  if (!parsed.success) return apiError(400, "bad_request", "Give a pair, for example EUR/USD, and an optional day.");
  const pair = (await listPairs()).find((p) => p.symbol === parsed.data.instrument);
  if (!pair) return apiError(404, "not_found", "That pair isn't enabled.");
  return apiJson({ levels: await pairLevels(pair, parsed.data.day) });
}
