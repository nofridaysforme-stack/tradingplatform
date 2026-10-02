import { z } from "zod";
import { apiError, apiJson, apiUser, unauthorized } from "@/lib/api";
import { activeBroker, listSignals } from "@/lib/signals";

const STATES = ["open", "confirmed", "target_hit", "stop_hit", "expired", "invalidated", "ambiguous"] as const;

const Query = z.object({
  state: z
    .string()
    .optional()
    .transform((v) => (v ? v.split(",").filter(Boolean) : undefined))
    .pipe(z.array(z.enum(STATES)).optional()),
  strategy: z.enum(["three_eight", "fib_pivot"]).optional().or(z.literal("").transform(() => undefined)),
  instrument: z.string().max(20).optional().or(z.literal("").transform(() => undefined)),
});

export async function GET(request: Request) {
  const user = await apiUser();
  if (!user) return unauthorized();
  const parsed = Query.safeParse(Object.fromEntries(new URL(request.url).searchParams));
  if (!parsed.success) return apiError(400, "bad_request", "Check the filters and try again.");
  const broker = await activeBroker(user.activeBrokerId);
  const { state, strategy, instrument } = parsed.data;
  return apiJson({ signals: await listSignals(broker, { states: state, strategy, instrument }) });
}
