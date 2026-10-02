import { expect, test } from "@playwright/test";
import { makeAdmin, resetUser, restoreRules, ruleState, snapshotRules, type RulesSnapshot, withSql } from "./db";
import { expectNoAxeViolations, signIn } from "./helpers";

const TRENDLINES = "three_eight.trendline_channel";
const PIVOTS = "three_eight.pivot_touch";
let snap: RulesSnapshot;

test.beforeEach(async ({ page }) => {
  snap = await snapshotRules();
  await resetUser();
  await signIn(page);
});

test.afterEach(async () => {
  await restoreRules(snap);
});

test("owners cannot open rule management", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Admin" })).toHaveCount(0);
  await page.goto("/settings/rules");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("an admin saves a new version and then approves the rule", async ({ page }) => {
  await makeAdmin();
  const before = await ruleState(TRENDLINES);
  await page.goto("/settings");
  await page.getByRole("link", { name: "Rules" }).click();
  await page.getByRole("link", { name: /Trendlines and channels/ }).first().click();
  await expect(page).toHaveURL(new RegExp(`rule=${TRENDLINES.replace(".", "\\.")}`));

  const editor = page.getByRole("form", { name: "Edit Trendlines and channels" });
  // Validation: out of range and no note.
  await editor.getByLabel(/^Min touches/).fill("11");
  await editor.getByRole("button", { name: "Save new version" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Save new version" }).click();
  await expect(editor.getByText("Use 10 or less.")).toBeVisible();
  await expect(editor.getByText("Write a change note.")).toBeVisible();
  expect((await ruleState(TRENDLINES)).current_version).toBe(before.current_version);

  await editor.getByLabel(/^Min touches/).fill("4");
  await editor.getByLabel("Change note").fill("Fewer false lines in the backtest");
  await editor.getByRole("button", { name: "Save new version" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText(`Save Trendlines and channels v${before.current_version + 1}?`);
  await expect(dialog).toContainText(/The scanner will use the change from the next bar, \d\d:\d\d NY\./);
  await dialog.getByRole("button", { name: "Save new version" }).click();
  await expect(page.getByRole("status")).toHaveText("Version saved");

  const saved = await ruleState(TRENDLINES);
  expect(saved.current_version).toBe(before.current_version + 1);
  expect(saved.status).toBe("provisional");
  expect(saved.params.min_touches).toBe(4);
  expect(saved.revision).toBe(before.revision + 1);
  expect(saved.audits.at(-1)).toBe("rule.update");
  const history = page.getByRole("region", { name: "Version history" });
  await expect(history).toContainText(/Min touches: 3\s*→?\s*changed to\s*4/);
  await expect(history).toContainText("Fewer false lines in the backtest");

  // Nothing changed: refused.
  await editor.getByLabel("Change note").fill("No real change");
  await editor.getByRole("button", { name: "Save new version" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Save new version" }).click();
  await expect(editor.getByText("Nothing changed. Edit a value before saving a new version.")).toBeVisible();

  await editor.getByLabel("Change note").fill("Owners approved after review");
  await editor.getByRole("button", { name: "Approve rule" }).click();
  await expect(page.getByRole("dialog")).toContainText("The provisional badge comes off this rule.");
  await page.getByRole("dialog").getByRole("button", { name: "Approve rule" }).click();
  await expect(page.getByRole("status")).toHaveText("Rule approved");
  await expect(editor.getByRole("button", { name: "Approve rule" })).toHaveCount(0);
  const approved = await ruleState(TRENDLINES);
  expect(approved.status).toBe("approved");
  expect(approved.audits.at(-1)).toBe("rule.approve");
});

test("an admin sets and removes a per-pair override", async ({ page }) => {
  await makeAdmin();
  const before = await ruleState(PIVOTS);
  await page.goto(`/settings/rules?rule=${PIVOTS}`);
  const form = page.getByRole("form", { name: "Set a per-pair override" });
  await form.getByLabel("Pair").selectOption({ label: "USD/JPY" });
  await form.getByRole("button", { name: "Save override" }).click();
  await expect(form.getByText("Fill in at least one value, or remove the override.")).toBeVisible();

  await form.getByLabel(/^Daily tolerance/).fill("20");
  await form.getByRole("button", { name: "Save override" }).click();
  await expect(form.getByRole("status")).toHaveText("Override for USD/JPY saved");
  const overrides = page.getByRole("region", { name: "Per-pair overrides" });
  await expect(overrides.getByRole("listitem").filter({ hasText: "USD/JPY" })).toContainText("Daily tolerance 20");
  const stored = await withSql((sql) => sql`select params from strategy_param_overrides o join instruments i on i.id = o.instrument_id where key = ${PIVOTS} and i.symbol = 'USD/JPY'`);
  expect(stored[0]?.params).toEqual({ daily_tolerance_pips: 20 });
  expect((await ruleState(PIVOTS)).revision).toBe(before.revision + 1);

  await overrides.getByRole("button", { name: "Remove override for USD/JPY" }).click();
  await expect(overrides.getByText("No overrides. Every pair uses the rule's values.")).toBeVisible();
  expect((await ruleState(PIVOTS)).audits.slice(-2)).toEqual(["rule.override", "rule.override.remove"]);
});

test("an admin switches a strategy off and limits its pairs", async ({ page }) => {
  await makeAdmin();
  await page.goto("/settings/rules");
  const fib = page.getByRole("form", { name: "Fib Pivot settings" });
  await fib.getByRole("switch", { name: /Scan with the Fib Pivot/ }).uncheck();
  await fib.getByLabel("Only these pairs").check();
  await fib.getByRole("button", { name: "Save Fib Pivot settings" }).click();
  await expect(fib.getByRole("alert")).toHaveText("Choose at least one pair, or scan all pairs.");
  await fib.getByLabel("EUR/USD").check();
  await fib.getByRole("button", { name: "Save Fib Pivot settings" }).click();
  await expect(fib.getByRole("status")).toHaveText("Strategy settings saved");
  const [row] = await withSql(
    (sql) => sql`select c.enabled, array(select symbol from instruments where id = any(c.instrument_ids)) as pairs from strategy_configs c where strategy = 'fib_pivot'`,
  );
  expect(row).toEqual({ enabled: false, pairs: ["EUR/USD"] });
});

for (const theme of ["light", "dark"] as const) {
  test(`rules pages pass axe checks in the ${theme} theme`, async ({ page, context, baseURL }) => {
    await makeAdmin();
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    await page.goto("/settings/rules");
    await expectNoAxeViolations(page);
    await page.goto(`/settings/rules?rule=${TRENDLINES}`);
    await expectNoAxeViolations(page);
    await page.getByRole("form", { name: "Edit Trendlines and channels" }).getByRole("button", { name: "Approve rule" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expectNoAxeViolations(page);
  });
}
