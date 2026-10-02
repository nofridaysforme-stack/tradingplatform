import { expect, test } from "@playwright/test";
import { makeAdmin, removeMarket, resetMarket, resetUser } from "./db";
import { expectNoAxeViolations, signIn } from "./helpers";
import { BROKER_NAME, SIGNAL_38, SIGNAL_FIB } from "./seed";

test.beforeEach(async ({ page }) => {
  await resetUser();
  await resetMarket();
  await signIn(page);
});

test("the dashboard lists live signals newest first with the market status", async ({ page }) => {
  await page.goto("/dashboard");
  const rows = page.getByRole("region", { name: "Live signals" }).getByRole("link");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toHaveAccessibleName(/^Short GBP\/JPY, entry 198\.970, Fib Pivot, Open$/);
  await expect(rows.nth(1)).toHaveAccessibleName(/^Long EUR\/GBP, entry 0\.86420, 3\/8 system, Confirmed$/);
  await expect(rows.nth(1).getByText("Provisional")).toBeVisible();
  await expect(rows.nth(1).getByRole("img", { name: "4 of 8 indicators fired" })).toBeVisible();

  await expect(page.getByText(/^Forex open · In 3\/8 window until 10:30 · \d\d:\d\d NY$/)).toBeVisible();
  await expect(page.getByText("Prices for GBP/USD haven't updated for 30 minutes.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "Health: warning" })).toBeVisible();
  await expect(page.getByRole("meter", { name: "Pips today" })).toHaveAttribute("aria-valuenow", "41");
  await expect(page.getByText("From 1 closed 3/8 signal")).toBeVisible();
  await expect(page.getByText(/newly confirmed after Tuesday's session/)).toBeVisible();
});

test("with no live signals the dashboard shows the empty state", async ({ page }) => {
  await removeMarket();
  await page.goto("/dashboard");
  await expect(page.getByText("No open signals. The scanner checks every 15 minutes while the market is open.")).toBeVisible();
});

test("choosing a broker shows adjusted prices", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText("No broker selected")).toBeVisible();
  const eurgbp = page.getByRole("link", { name: /EUR\/GBP/ });
  await expect(eurgbp).toHaveAccessibleName(/entry 0\.86420/);

  await page.getByRole("button", { name: "Choose" }).click();
  await page.getByLabel(BROKER_NAME).check();
  await page.getByRole("button", { name: "Save broker" }).click();
  await expect(page.getByText(`Broker ${BROKER_NAME}`)).toBeVisible();
  // Long: entry plus half the 1.0 pip spread.
  await expect(eurgbp).toHaveAccessibleName(/entry 0\.86425/);
});

test("signal detail explains the signal", async ({ page }) => {
  await page.goto(`/signals/${SIGNAL_38}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Long\s*EUR\/GBP/);
  await expect(page.locator("header").getByText("Confirmed", { exact: true })).toBeVisible();

  const plan = page.getByRole("region", { name: "Trade plan" });
  await expect(plan.getByRole("row", { name: /Entry 0\.86420/ })).toBeVisible();
  await expect(plan.getByRole("row", { name: /Alternative target 0\.87220/ })).toBeVisible();
  await expect(plan.getByText("Choose a broker in Settings", { exact: false })).toBeVisible();

  const why = page.getByRole("region", { name: "Why" });
  await expect(why.getByRole("img", { name: "4 of 8 indicators fired" })).toBeVisible();
  await expect(why.getByRole("listitem").filter({ hasText: "Trendlines and channels" })).toContainText(
    "Provisional: this definition is waiting for owner approval.",
  );
  await expect(why.getByRole("listitem").filter({ hasText: "Pivots" })).toContainText("Daily S1");
  await expect(why.getByText("Trading hours passed")).toBeVisible();
  await expect(why.getByText("Long at the daily S1 with 4 of 8 indicators in an uptrend.")).toBeVisible();

  await expect(page.locator("canvas").first()).toBeVisible();
  const timeline = page.getByRole("region", { name: "Timeline" });
  await expect(timeline.getByRole("listitem")).toHaveText([/Created/, /Confirmed/]);
  await expect(page.getByRole("region", { name: "Admin" })).toHaveCount(0);
});

test("the broker button opens the broker's chart for the pair", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Choose" }).click();
  await page.getByLabel(BROKER_NAME).check();
  await page.getByRole("button", { name: "Save broker" }).click();
  await expect(page.getByText(`Broker ${BROKER_NAME}`)).toBeVisible();
  await page.goto(`/signals/${SIGNAL_FIB}`);
  await expect(page.getByRole("link", { name: `Open in ${BROKER_NAME}` })).toHaveAttribute(
    "href",
    "https://trade.example.com/chart?symbol=GBPJPY",
  );
  // Short: entry minus half the 1.6 pip spread.
  await expect(page.getByRole("row", { name: /Entry 198\.970 198\.962/ })).toBeVisible();
});

test("an admin can mark a signal invalid and add a note", async ({ page }) => {
  await makeAdmin();
  await page.goto(`/signals/${SIGNAL_38}`);
  const admin = page.getByRole("region", { name: "Admin" });
  await admin.getByRole("button", { name: "Mark invalid" }).click();
  await expect(admin.getByText("Write a reason first.")).toBeVisible();
  await admin.getByLabel("Reason for marking invalid").fill("Data gap on the trigger bar");
  await admin.getByRole("button", { name: "Mark invalid" }).click();
  await expect(page.locator("header").getByText("Invalidated", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Timeline" })).toContainText("Data gap on the trigger bar");

  await admin.getByLabel("Note").fill("Checked with the owners");
  await admin.getByRole("button", { name: "Add note" }).click();
  await expect(page.getByRole("region", { name: "Timeline" })).toContainText("Checked with the owners");

  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: "Live signals" }).getByRole("link")).toHaveCount(1);
});

test("the read endpoints need a session and follow the spec 14 shape", async ({ page, playwright, baseURL }) => {
  const res = await page.request.get("/api/signals?state=open,confirmed");
  expect(res.status()).toBe(200);
  const { signals } = (await res.json()) as { signals: Record<string, unknown>[] };
  expect(signals.map((s) => s.id)).toEqual([SIGNAL_FIB, SIGNAL_38]);
  expect(signals[1]).toMatchObject({
    strategy: "three_eight",
    instrument: "EUR/GBP",
    direction: "long",
    state: "confirmed",
    indicator_count: 4,
    has_provisional: true,
    confluence: false,
    reference: { entry: "0.86420", stop: "0.86190", target: "0.87050", reward_risk: 2.739 },
    adjusted: null,
  });

  expect((await page.request.get("/api/signals?state=bogus")).status()).toBe(400);
  expect((await page.request.get(`/api/signals/${SIGNAL_38}`)).status()).toBe(200);
  expect((await page.request.get("/api/signals/not-a-uuid")).status()).toBe(404);
  const market = await (await page.request.get("/api/market-status")).json();
  expect(market).toMatchObject({ health: "warn", forex_open: true, in_window: true, stale: ["GBP/USD"] });

  const anonymous = await playwright.request.newContext({ baseURL });
  for (const path of ["/api/signals", `/api/signals/${SIGNAL_38}`, "/api/market-status"]) {
    const r = await anonymous.get(path);
    expect(r.status(), path).toBe(401);
    expect(await r.json()).toEqual({ error: { code: "unauthorized", message: "Sign in to continue." } });
  }
  await anonymous.dispose();
});

for (const theme of ["light", "dark"] as const) {
  test(`dashboard and signal detail pass axe checks in the ${theme} theme`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    for (const path of ["/dashboard", `/signals/${SIGNAL_38}`, `/signals/${SIGNAL_FIB}`]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expectNoAxeViolations(page);
    }
  });
}
