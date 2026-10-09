import { expect, test } from "@playwright/test";
import { makeAdmin, resetMarket, resetUser, withSql } from "./db";
import { E2E_EMAIL } from "./env";
import { expectNoAxeViolations, signIn } from "./helpers";
import { PREV_SESSION, SESSION } from "./seed";

test.beforeEach(async ({ page }) => {
  await resetUser();
  await resetMarket();
  await signIn(page);
});

const tickers = (page: import("@playwright/test").Page) =>
  page.getByRole("table", { name: /Screen results/ }).getByRole("row").locator("td:first-child a").allTextContents();

test("stock results sort, filter, search, and switch sessions", async ({ page }) => {
  await page.goto("/stocks");
  await expect(page.getByText(`Screen for the ${SESSION} session · 3 qualified · 1 on the watch list · 1 open buys`)).toBeVisible();
  expect(await tickers(page)).toEqual(["E2EA", "E2EB", "E2EC"]); // APR 20 descending by default
  await expect(page.getByRole("columnheader", { name: /APR 20/ })).toHaveAttribute("aria-sort", "descending");

  await page.getByRole("link", { name: "Ticker", exact: true }).click();
  await page.waitForURL(/sort=ticker&dir=asc/);
  expect(await tickers(page)).toEqual(["E2EA", "E2EB", "E2EC"]);
  await page.getByRole("link", { name: /^Ticker/ }).click();
  await page.waitForURL(/sort=ticker&dir=desc/);
  expect(await tickers(page)).toEqual(["E2EC", "E2EB", "E2EA"]);

  await page.goto("/stocks");
  await page.getByLabel("Trend").selectOption("trend_confirmed");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await page.waitForURL(/status=trend_confirmed/);
  expect(await tickers(page)).toEqual(["E2EA"]);

  await page.goto("/stocks?q=gamma");
  expect(await tickers(page)).toEqual(["E2EC"]);

  await page.goto(`/stocks?session=${PREV_SESSION}`);
  await expect(page.getByText(`Screen for the ${PREV_SESSION} session · 1 qualified`)).toBeVisible();
  await expect(page.getByRole("row", { name: /E2EA.*Watching/ })).toBeVisible();

  await page.goto("/stocks");
  await page.getByLabel("Stage").selectOption("watching");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await page.waitForURL(/stage=watching/);
  expect(await tickers(page)).toEqual(["E2EB"]);
});

test("stock detail shows the five line chart, checks, and status history", async ({ page }) => {
  await page.goto("/stocks/E2EA");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("E2EA");
  await expect(page.getByText("E2E Alpha Industries")).toBeVisible();
  const five = page.getByRole("region", { name: "Five line chart" });
  await expect(five.getByRole("row", { name: /Today 50\.65/ })).toBeVisible();
  await expect(five.getByRole("row", { name: /50-day 33\.90 49\.4%/ })).toBeVisible();
  const checks = page.getByRole("region", { name: "Qualification" });
  await expect(checks).toContainText("needs 46.80 or more (90% of the high)");
  await expect(checks).toContainText("needs 40.00 or more (2 times the low)");
  const history = page.getByRole("region", { name: "Trend history" }).getByRole("listitem");
  await expect(history).toHaveText([/Trend confirmed\s*From 2026-09-30/, /Qualified\s*From 2026-09-29/]);
  await expect(page.locator("canvas").first()).toBeVisible();
  expect((await page.goto("/stocks/NOPE"))?.status()).toBe(404);
});

test("the stocks page shows open buys, the watch list, and closed buys", async ({ page }) => {
  await page.goto("/stocks");
  const open = page.getByRole("region", { name: "Open buys" }).getByRole("listitem");
  await expect(open).toHaveCount(1);
  await expect(open).toContainText("Buy");
  await expect(open).toContainText(`E2EA${PREV_SESSION} at 50.30`);
  await expect(open).toContainText("Stop now47.79Fixed 5%");
  await expect(open).toContainText("Projection (35%)67.91In 20 sessions");
  await expect(open).toContainText("So far+0.7%");
  await expect(open).toContainText("3 of 5 voted to buy: Price and candle (engulfing), MACD crossover, Pivot point crossover.");
  await expect(open.getByText("Provisional")).toBeVisible();

  const watch = page.getByRole("table", { name: /Watch list/ });
  await expect(watch.getByRole("row", { name: /E2EB.*29\.80.*6\.9%.*2 of 5/ })).toBeVisible();
  await expect(watch).toContainText("Price and candle, MACD crossover");

  const closed = page.getByRole("region", { name: "Closed buys" }).getByRole("listitem");
  await expect(closed).toContainText("Sell signal 2026-09-29");
  await expect(closed).toContainText("Result+17.3%");
  await expect(closed).toContainText("Sold on: Price and candle, MACD crossover, Pivot point crossover.");
});

test("stock detail shows momentum, the indicators, and the stock's buys", async ({ page }) => {
  await page.goto("/stocks/E2EB");
  const funnel = page.getByRole("region", { name: "Momentum and watch list" });
  await expect(funnel).toContainText("10-day APR 512%, needs 455% or more");
  await expect(funnel).toContainText("Waiting for a buy: 3 of 5 indicators within 3 sessions");
  const ind = page.getByRole("region", { name: "Indicators" });
  await expect(ind).toContainText(`After the ${SESSION} session: 2 of 5 for a buy, 0 of 5 for a sell`);
  await expect(ind.getByRole("row", { name: /Price and candle.*Fired 2026-09-30.*No/ })).toBeVisible();
  await expect(ind.getByRole("row", { name: /^RSI.*No.*No.*RSI 48\.20/ })).toBeVisible();
  await expect(ind.getByRole("row", { name: /^RSI/ }).getByText("Provisional")).toBeVisible();

  await page.goto("/stocks/E2EA");
  await expect(page.getByRole("region", { name: "Momentum and watch list" })).toContainText("Not watched while a buy is open.");
  const buys = page.getByRole("region", { name: "Buys" }).getByRole("listitem").first();
  await expect(buys).toContainText(`Bought${PREV_SESSION} at 50.30`);
  const stages = page.getByRole("region", { name: "Stage history" }).getByRole("listitem");
  await expect(stages).toHaveText([/Qualified\s*From 2026-09-30/, /Watching\s*From 2026-09-29/]);
  await expectNoAxeViolations(page);
});

test("an owner adds, edits, and closes a holding", async ({ page }) => {
  await page.goto("/stocks/E2EA");
  const add = page.getByRole("form", { name: "Add to holdings" });
  await expect(add.getByLabel("Purchase price")).toHaveValue("50.65");
  await expect(add.getByLabel("Projection")).toHaveValue("35");
  await add.getByLabel("Purchase price").fill("50");
  await add.getByLabel("Purchase date").fill("2026-09-25");
  await add.getByRole("button", { name: "Add to holdings" }).click();
  await expect(add.getByRole("status")).toHaveText("E2EA added");

  await page.goto("/holdings");
  const row = page.getByRole("region", { name: "Open" }).getByRole("listitem").filter({ hasText: "E2EA" });
  await expect(row).toContainText("Projection67.50");
  await expect(row).toContainText("Total earnings17.50");
  await expect(row).toContainText("Daily target0.875");
  await expect(row).toContainText("Weekly target4.375");
  await expect(row).toContainText("Last close50.65");
  await expect(row).toContainText("3 of 20 sessions"); // bars after Sept 25: 28, 29, 30
  await expect(row.getByRole("meter")).toHaveAttribute("aria-valuenow", "4");

  await row.getByText("Edit holding").click();
  const edit = row.getByRole("form", { name: "Save changes" });
  await edit.getByLabel("Projection").fill("0");
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(edit.getByText("Use 1 or more.")).toBeVisible();
  await expect(edit.getByLabel("Purchase price")).toHaveValue("50");
  await edit.getByLabel("Projection").fill("10");
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(row).toContainText("Projection55.00");

  // The scanner writes where the holding stands after each close (spec 08).
  await withSql((sql) => sql`update holdings set tracked_session = ${SESSION}, highest_close = 52, trailing_active = true, stop_now = 49.4,
    sell_reason = 'trailing_stopped', sell_session = ${SESSION}, sell_price = 49.3 where ticker = 'E2EA'`);
  await page.reload();
  await expect(row).toContainText("Stop now49.40Trailing");
  await expect(row.getByRole("note")).toHaveText(`Sell: trailing stop on ${SESSION} at 49.30. Close the holding here once you have sold.`);

  await row.getByRole("button", { name: "Close holding E2EA" }).click();
  await expect(page.getByRole("region", { name: "Closed" })).toContainText("E2EA bought 2026-09-25 at 50.00");
  await expect(page.getByRole("region", { name: "Open" })).toContainText("No open holdings.");
});

test("holdings are private to their owner and validated", async ({ page }) => {
  // Another owner's holding is never shown or editable.
  const otherId = await withSql(async (sql) => {
    const [u] = await sql`insert into users (email) values ('other-owner@example.com') on conflict (email) do update set email = excluded.email returning id`;
    const [h] = await sql`insert into holdings (user_id, ticker, purchase_price, purchase_date) values (${u!.id}, 'E2EB', 20, '2026-09-01') returning id`;
    return h!.id as string;
  });
  try {
    await page.goto("/holdings");
    await expect(page.getByText("E2EB")).toHaveCount(0);

    const add = page.getByRole("form", { name: "Add holding" });
    await add.getByLabel("Ticker").fill("not a ticker");
    await add.getByLabel("Purchase date").fill("2999-01-01");
    await add.getByRole("button", { name: "Add holding" }).click();
    await expect(add.getByText("Enter a ticker, for example AAPL.")).toBeVisible();
    await expect(add.getByText("Enter the price you paid.")).toBeVisible();
    await expect(add.getByText("The purchase date can't be in the future.")).toBeVisible();
  } finally {
    await withSql(async (sql) => {
      await sql`delete from holdings where id = ${otherId}`;
      await sql`delete from users where email = 'other-owner@example.com'`;
    });
  }
  const mine = await withSql((sql) => sql`select count(*)::int as n from holdings h join users u on u.id = h.user_id where u.email = ${E2E_EMAIL}`);
  expect(mine[0]?.n).toBe(0);
});

test("econ events: owners read, admins add and delete", async ({ page }) => {
  await page.goto("/econ");
  await expect(page.getByRole("region", { name: "Upcoming" })).toContainText("E2E Nonfarm payrolls");
  await expect(page.getByRole("region", { name: "Last 7 days" })).toContainText("E2E ECB rate decision");
  await expect(page.getByRole("form", { name: "Add event" })).toHaveCount(0);

  await makeAdmin();
  await page.reload();
  const form = page.getByRole("form", { name: "Add event" });
  await form.getByRole("button", { name: "Add event" }).click();
  await expect(form.getByText("Enter a date and time in New York time.")).toBeVisible();
  const inAWeek = new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10);
  await form.getByLabel("Time (New York)").fill(`${inAWeek}T08:30`);
  await form.getByLabel("Currency").fill("usd");
  await form.getByLabel("Event").fill("E2E CPI");
  await form.getByRole("button", { name: "Add event" }).click();
  await expect(form.getByRole("status")).toHaveText("Event added");
  const row = page.getByRole("region", { name: "Upcoming" }).getByRole("row").filter({ hasText: "E2E CPI" });
  await expect(row).toContainText("08:30");
  await expect(row).toContainText("USD");
  const stored = await withSql((sql) => sql`select at, currency from econ_events where title = 'E2E CPI'`);
  expect(stored[0]?.currency.trim()).toBe("USD");
  expect([12, 13]).toContain((stored[0]?.at as Date).getUTCHours()); // 08:30 New York

  await row.getByRole("button", { name: "Delete USD E2E CPI" }).click();
  await expect(page.getByText("E2E CPI")).toHaveCount(0);
  const audits = await withSql((sql) => sql`select action from audit_log a join users u on u.id = a.user_id where u.email = ${E2E_EMAIL} order by a.id`);
  expect(audits.map((a) => a.action)).toEqual(["econ.create", "econ.delete"]);
});

test("stock APIs need a session", async ({ page, playwright, baseURL }) => {
  const res = await (await page.request.get("/api/stocks/results?status=qualified")).json();
  expect(res.rows.map((r: { ticker: string }) => r.ticker)).toEqual(["E2EB"]);
  const one = await (await page.request.get("/api/stocks/E2EA")).json();
  expect(one.stock.latest.status).toBe("trend_confirmed");
  expect((await page.request.get("/api/stocks/NOPE")).status()).toBe(404);
  const anon = await playwright.request.newContext({ baseURL });
  expect((await anon.get("/api/stocks/results")).status()).toBe(401);
  expect((await anon.get("/api/stocks/E2EA")).status()).toBe(401);
  await anon.dispose();
});

for (const theme of ["light", "dark"] as const) {
  test(`stocks, holdings, and econ pass axe checks in the ${theme} theme`, async ({ page, context, baseURL }) => {
    await makeAdmin();
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    await withSql(
      (sql) => sql`insert into holdings (user_id, ticker, purchase_price, purchase_date) select id, 'E2EA', 45, '2026-09-20' from users where email = ${E2E_EMAIL}`,
    );
    for (const path of ["/stocks", "/stocks/E2EA", "/holdings", "/econ"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expectNoAxeViolations(page);
    }
  });
}
