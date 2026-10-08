import { expect, test } from "@playwright/test";
import { makeAdmin, resetMarket, resetUser, setForex, withSql } from "./db";
import { E2E_EMAIL } from "./env";
import { expectNoAxeViolations, signIn } from "./helpers";

// Decision 2026-10-08: forex can be paused. Its pages are hidden, nothing is deleted.

test.beforeEach(async ({ page }) => {
  await resetUser();
  await resetMarket();
  await setForex(true);
  await signIn(page);
});

test.afterEach(async () => {
  await setForex(true);
});

test("while forex is paused its pages are hidden and the portal opens on stocks", async ({ page, isMobile }) => {
  await setForex(false);
  for (const path of ["/", "/dashboard", "/levels", "/history", "/econ"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/stocks$/);
  }
  const nav = page.getByRole("navigation", { name: "Main" }).locator("visible=true");
  await expect(nav.getByRole("link", { name: "Stocks" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Holdings" })).toBeVisible();
  for (const name of ["Signals", "Levels", "History"]) await expect(nav.getByRole("link", { name, exact: true })).toHaveCount(0);
  if (!isMobile) await expect(nav.getByRole("link", { name: "Econ events" })).toHaveCount(0);

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Broker" })).toHaveCount(0);
  await page.goto("/health");
  await expect(page.getByText(/Forex paused/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Last completed bar per pair" })).toHaveCount(0);
  await expectNoAxeViolations(page);
});

test("an admin pauses and resumes forex, and both are audit logged", async ({ page }) => {
  await makeAdmin();
  await page.goto("/settings");
  const form = page.getByRole("form", { name: "Forex" });
  await form.getByRole("button", { name: "Pause forex" }).click();
  await expect(form.getByRole("status")).toHaveText("Forex paused");
  const [paused] = await withSql((sql) => sql`select forex_enabled from app_settings`);
  expect(paused).toEqual({ forex_enabled: false });
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/stocks$/);

  await page.goto("/settings");
  await expect(page.getByRole("link", { name: "Pairs" })).toHaveCount(0);
  await expectNoAxeViolations(page);
  await page.getByRole("form", { name: "Forex" }).getByRole("button", { name: "Resume forex" }).click();
  await expect(page.getByRole("form", { name: "Forex" }).getByRole("status")).toHaveText("Forex resumed");
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard$/);
  const actions = await withSql(
    async (sql) =>
      (await sql`select a.after from audit_log a join users u on u.id = a.user_id where u.email = ${E2E_EMAIL} and a.action = 'settings.forex' order by a.id`).map(
        (r) => r.after,
      ),
  );
  expect(actions).toEqual([{ forex_enabled: false }, { forex_enabled: true }]);
});

test("an owner cannot pause forex", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("form", { name: "Forex" })).toHaveCount(0);
});
