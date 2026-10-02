import "server-only";
import { db } from "@/lib/db";
import { auditLog } from "@/lib/db/schema";

type Tx = Parameters<Parameters<typeof db.transaction>[0]>[0];

/** Spec 15: admin changes are audit logged with who, what, and the before and after. */
export async function audit(
  tx: Tx | typeof db,
  entry: { userId: string; action: string; target: string; before?: unknown; after?: unknown },
) {
  await tx.insert(auditLog).values({
    userId: entry.userId,
    action: entry.action,
    target: entry.target,
    before: entry.before ?? null,
    after: entry.after ?? null,
  });
}
