import { apiJson, apiUser, unauthorized } from "@/lib/api";
import { parseResultsQuery, results } from "@/lib/stocks";

export async function GET(request: Request) {
  if (!(await apiUser())) return unauthorized();
  return apiJson(await results(parseResultsQuery(Object.fromEntries(new URL(request.url).searchParams))));
}
