import { apiJson, apiUser, unauthorized } from "@/lib/api";

/** The VAPID public key the browser needs to subscribe (spec 14). Null until it is set. */
export async function GET() {
  if (!(await apiUser())) return unauthorized();
  return apiJson({ key: process.env.VAPID_PUBLIC_KEY || null });
}
