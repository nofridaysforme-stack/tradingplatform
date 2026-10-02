import { expect, test } from "@playwright/test";
import { resetMarket, resetUser } from "./db";
import { expectNoAxeViolations, signIn } from "./helpers";
import { SIGNAL_CLOSED, SIGNAL_LOSS, SIGNAL_VOID } from "./seed";

test.beforeEach(async ({ page }) => {
  await resetUser();
  await resetMarket();
  await signIn(page);
});

test("levels show floor pivots, previous day, and the Fib Pivot ladder", async ({ page, isMobile }) => {
  await page.goto("/levels?pair=EUR%2FGBP");
  const eur = page.getByRole("region", { name: "EUR/GBP" }).first();
  const pivots = eur.getByRole("table", { name: "Floor pivots for EUR/GBP" });
  await expect(pivots.getByRole("row", { name: /^P 0\.86320 0\.86510 0\.85880$/ })).toBeVisible();
  await expect(eur.getByText("PDH")).toBeVisible();

  if (isMobile) {
    await page.getByRole("link", { name: "GBP/JPY" }).click();
    await expect(page.getByRole("link", { name: "GBP/JPY" })).toHaveAttribute("aria-current", "page");
  }
  const jpy = page.getByRole("region", { name: "GBP/JPY" }).first();
  await expect(jpy.getByText("Range 66 pips · Fibonacci 55")).toBeVisible();
  const rungs = jpy.getByRole("listitem");
  await expect(rungs.first()).toContainText("Reset up");
  await expect(rungs.filter({ hasText: "Pivot" })).toContainText("199.520");
  await expect(rungs.last()).toContainText("Reset down");
});

test("levels API returns the sets for a pair", async ({ page }) => {
  const res = await page.request.get("/api/levels?instrument=EUR/GBP");
  expect(res.status()).toBe(200);
  const { levels } = await res.json();
  expect(levels.daily.P).toBe(0.8632);
  expect(levels.prev_day).toEqual({ PDH: 0.8674, PDL: 0.8612 });
  expect(levels.last_price).toBeGreaterThan(0);
  expect((await page.request.get("/api/levels?instrument=XXX/YYY")).status()).toBe(404);
  expect((await page.request.get("/api/levels")).status()).toBe(400);
});

test("history lists closed signals with metrics that leave invalidated ones out", async ({ page }) => {
  await page.goto("/history");
  const summary = page.getByRole("region", { name: "Summary" });
  await expect(summary).toContainText("Trades2");
  await expect(summary).toContainText("Win rate50%");
  await expect(summary).toContainText("Net-14pips");
  await expect(summary).toContainText("Expectancy-7pips");
  await expect(summary).toContainText("Profit factor0.75");

  const rows = page.getByRole("table").getByRole("row");
  await expect(rows).toHaveCount(4); // header plus three closed signals
  await expect(page.getByRole("link", { name: /\d{4}-\d\d-\d\d/ }).first()).toHaveAttribute("href", `/signals/${SIGNAL_CLOSED}`);
  await expect(page.getByRole("group", { name: /Cumulative pips over 2 closed signals, ending at -14/ })).toBeVisible();
});

test("history filters narrow the table and the metrics", async ({ page }) => {
  await page.goto("/history");
  await page.getByLabel("Outcome").selectOption("stop_hit");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/outcome=stop_hit/);
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Summary" })).toContainText("Trades1");

  await page.goto("/history?provisional=yes&strategy=fib_pivot");
  await expect(page.getByRole("link", { name: /\d{4}-\d\d-\d\d/ })).toHaveAttribute("href", `/signals/${SIGNAL_LOSS}`);
  await page.goto("/history?outcome=invalidated");
  await expect(page.getByRole("link", { name: /\d{4}-\d\d-\d\d/ })).toHaveAttribute("href", `/signals/${SIGNAL_VOID}`);
  await expect(page.getByRole("region", { name: "Summary" })).toContainText("Trades0");

  await page.goto("/history?outcome=bogus&from=not-a-date");
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(4);
});

test("CSV export follows the filter and needs a session", async ({ page, playwright, baseURL }) => {
  const res = await page.request.get("/api/history/export.csv?outcome=target_hit");
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toContain("text/csv");
  expect(res.headers()["content-disposition"]).toMatch(/attachment; filename="signal-history-\d{4}-\d\d-\d\d\.csv"/);
  const lines = (await res.text()).trim().split("\r\n");
  expect(lines[0]).toBe(
    "trading_day,closed_at_utc,strategy,instrument,direction,outcome,result_pips,reward_risk,provisional,rule_versions,signal_id",
  );
  expect(lines).toHaveLength(2);
  expect(lines[1]).toContain(`,three_eight,EUR/GBP,short,target_hit,41,1.783,false,,${SIGNAL_CLOSED}`);

  const json = await (await page.request.get("/api/history?direction=short")).json();
  expect(json.total).toBe(3);
  expect(json.summary).toMatchObject({ trades: 2, wins: 1, netPips: -14 });

  const anonymous = await playwright.request.newContext({ baseURL });
  expect((await anonymous.get("/api/history/export.csv")).status()).toBe(401);
  expect((await anonymous.get("/api/history")).status()).toBe(401);
  expect((await anonymous.get("/api/levels?instrument=EUR/GBP")).status()).toBe(401);
  await anonymous.dispose();
});

for (const theme of ["light", "dark"] as const) {
  test(`levels and history pass axe checks in the ${theme} theme`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    for (const path of ["/levels?pair=EUR%2FGBP", "/levels?pair=GBP%2FJPY", "/history"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expectNoAxeViolations(page);
    }
  });
}
