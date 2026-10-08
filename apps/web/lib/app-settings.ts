import "server-only";
import { redirect } from "next/navigation";
import { cache } from "react";
import { db } from "@/lib/db";
import { appSettings } from "@/lib/db/schema";

/** The forex switch (decision 2026-10-08). While it is off the scanner runs no forex jobs and
 *  the portal hides the forex pages; nothing is deleted. */
export const forexEnabled = cache(async (): Promise<boolean> => {
  const [row] = await db.select({ forexEnabled: appSettings.forexEnabled }).from(appSettings);
  return row?.forexEnabled ?? true;
});

/** The home page while forex is paused. */
export const STOCKS_HOME = "/stocks";

/** For forex-only pages: sends the viewer to the stock pages while forex is paused. */
export async function requireForex(): Promise<void> {
  if (!(await forexEnabled())) redirect(STOCKS_HOME);
}
