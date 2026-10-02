import { apiError, apiJson, apiUser, unauthorized } from "@/lib/api";
import { healthDetail } from "@/lib/health";

export async function GET() {
  const user = await apiUser();
  if (!user) return unauthorized();
  if (user.role !== "admin") return apiError(403, "forbidden", "Only admins can see health details.");
  return apiJson(await healthDetail(new Date()));
}
