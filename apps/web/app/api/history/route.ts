import { apiJson, apiUser, unauthorized } from "@/lib/api";
import { historyPage, parseFilter } from "@/lib/history";

export async function GET(request: Request) {
  if (!(await apiUser())) return unauthorized();
  const filter = parseFilter(Object.fromEntries(new URL(request.url).searchParams));
  const page = await historyPage(filter);
  return apiJson({ filter, ...page });
}
