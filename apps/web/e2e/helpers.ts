import { readFileSync } from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { E2E_EMAIL, MAILBOX } from "./env";

/** The newest sign-in link written for an email. */
export function latestLink(email = E2E_EMAIL): string {
  const file = path.join(MAILBOX, `${email}.json`);
  return (JSON.parse(readFileSync(file, "utf8")) as { url: string }).url;
}

export async function requestLink(page: Page, email = E2E_EMAIL) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Email me a sign-in link" }).click();
  await expect(page.getByRole("status")).toHaveText("Check your email for a sign-in link.");
}

/** Signs in and acknowledges the notice if it is shown. */
export async function signIn(page: Page) {
  await requestLink(page);
  await page.goto(latestLink());
  if (new URL(page.url()).pathname === "/notice") {
    await page.getByRole("button", { name: "I understand" }).click();
  }
  await page.waitForURL("**/dashboard");
}

export async function expectNoAxeViolations(page: Page) {
  // Next streams page metadata, so the <title> can land just after the page loads.
  await expect(page).toHaveTitle(/\S/);
  // Wide tables scroll inside their own box; the page itself never scrolls sideways.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`)).toEqual([]);
}
