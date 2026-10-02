import { apiError, apiJson, apiUser, unauthorized } from "@/lib/api";
import { stockDetail } from "@/lib/stocks";

export async function GET(_: Request, ctx: RouteContext<"/api/stocks/[ticker]">) {
  if (!(await apiUser())) return unauthorized();
  const ticker = decodeURIComponent((await ctx.params).ticker).toUpperCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(ticker)) return apiError(404, "not_found", "That ticker isn't stored.");
  const stock = await stockDetail(ticker);
  if (!stock) return apiError(404, "not_found", "That ticker isn't stored.");
  return apiJson({ stock });
}
