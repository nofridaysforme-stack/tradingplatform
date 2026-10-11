import { expect, test } from "@playwright/test";
import { makeAdmin, resetMarket, resetUser, withSql } from "./db";
import { E2E_EMAIL } from "./env";
import { expectNoAxeViolations, signIn } from "./helpers";
import { BROKER_NAME, PAIRS } from "./seed";

const NEW_PAIR = "AUD/JPY";
const NEW_EMAIL = "new-owner@example.com";

test.beforeEach(async ({ page }) => {
  await withSql(async (sql) => {
    await sql`delete from instruments where symbol = ${NEW_PAIR}`;
    await sql`delete from users where email = ${NEW_EMAIL}`;
    await sql`delete from allowlist where email = ${NEW_EMAIL}`;
    await sql`delete from brokers where name = 'E2E second broker'`;
  });
  await resetUser();
  await resetMarket();
  await signIn(page);
});

const audits = () =>
  withSql(async (sql) => (await sql`select action from audit_log a join users u on u.id = a.user_id where u.email = ${E2E_EMAIL} order by a.id`).map((r) => r.action));

test("an owner saves a profile and a broker, and cannot open admin pages", async ({ page }) => {
  await page.goto("/settings");
  const profile = page.getByRole("form", { name: "Profile" });
  await profile.getByLabel("Name").fill("Sam Owner");
  await profile.getByLabel("Time zone").selectOption("Europe/London");
  await profile.getByRole("button", { name: "Save profile" }).click();
  await expect(profile.getByRole("status")).toHaveText("Profile saved");
  const [row] = await withSql((sql) => sql`select name, timezone from users where email = ${E2E_EMAIL}`);
  expect(row).toEqual({ name: "Sam Owner", timezone: "Europe/London" });

  const broker = page.getByRole("form", { name: "Broker for adjusted prices" });
  await broker.getByLabel(BROKER_NAME).check();
  await broker.getByRole("button", { name: "Save broker" }).click();
  await expect(broker.getByRole("status")).toHaveText("Broker saved");
  await page.goto("/dashboard");
  await expect(page.getByText(`Broker ${BROKER_NAME}`)).toBeVisible();

  for (const path of ["/settings/brokers", "/settings/pairs", "/settings/users"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/dashboard$/);
  }
  await page.goto("/health");
  await expect(page.getByRole("heading", { name: "Job runs, last 24 hours" })).toHaveCount(0);
});

test("an admin adds, edits, and deletes a broker", async ({ page }) => {
  await makeAdmin();
  await page.goto("/settings/brokers");
  const add = page.getByRole("form", { name: "Add broker" });
  await add.getByLabel("Name").fill("E2E second broker");
  await add.getByLabel("Chart link (optional)").fill("http://insecure.example.com/{symbol}");
  await add.getByLabel(`${PAIRS[0]} spread in pips`).fill("99");
  await add.getByRole("button", { name: "Add broker" }).click();
  await expect(add.getByText("Use an https link that contains {symbol}.")).toBeVisible();
  await expect(add.getByText("Use 50 or less.")).toBeVisible();
  await expect(add.getByLabel("Name")).toHaveValue("E2E second broker");

  await add.getByLabel("Chart link (optional)").fill("https://second.example.com/chart/{symbol}");
  await add.getByLabel(`${PAIRS[0]} spread in pips`).fill("0.8");
  await add.getByLabel(`${PAIRS[0]} symbol at this broker`).fill("EURGBP.pro");
  await add.getByRole("button", { name: "Add broker" }).click();
  await expect(add.getByRole("status")).toHaveText("E2E second broker added");
  const item = page.getByRole("listitem").filter({ hasText: "E2E second broker" });
  await expect(item).toContainText("Spreads for 1 pair · Used by 0 owners");

  await item.getByText("Edit broker").click();
  const edit = item.getByRole("form", { name: "Edit E2E second broker" });
  await edit.getByLabel(`${PAIRS[1]} spread in pips`).fill("2.1");
  await edit.getByRole("button", { name: "Save broker" }).click();
  await expect(edit.getByRole("status")).toHaveText("Broker saved");
  await expect(item).toContainText("Spreads for 2 pairs");

  page.once("dialog", (d) => d.accept());
  await item.getByRole("button", { name: "Delete E2E second broker" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "E2E second broker" })).toHaveCount(0);
  expect(await audits()).toEqual(["broker.create", "broker.update", "broker.delete"]);
});

test("an admin adds a pair and turns it off", async ({ page }) => {
  await makeAdmin();
  await page.goto("/settings/pairs");
  const add = page.getByRole("form", { name: "Add pair" });
  await add.getByLabel("Pair").fill("audjpy");
  await expect(add.getByLabel("Pip size")).toHaveValue("0.01");
  await add.getByRole("button", { name: "Add pair" }).click();
  await expect(add.getByRole("status")).toContainText(`${NEW_PAIR} added`);
  const [row] = await withSql((sql) => sql`select provider_code, pip_size::text, display_decimals, enabled from instruments where symbol = ${NEW_PAIR}`);
  expect(row).toEqual({ provider_code: "AUD_JPY", pip_size: "0.01000000", display_decimals: 3, enabled: true });

  await add.getByLabel("Pair").fill(NEW_PAIR);
  await add.getByRole("button", { name: "Add pair" }).click();
  await expect(add.getByText(`${NEW_PAIR} is already in the list.`)).toBeVisible();

  const item = page.getByRole("listitem").filter({ hasText: NEW_PAIR });
  await expect(item).toContainText("Pip 0.01 · 3 decimals · History loading");
  await item.getByRole("switch", { name: `Scan ${NEW_PAIR}` }).uncheck();
  await item.getByRole("button", { name: `Save ${NEW_PAIR}` }).click();
  await expect(item.getByRole("status")).toHaveText(`${NEW_PAIR} saved`);
  const [after] = await withSql((sql) => sql`select enabled from instruments where symbol = ${NEW_PAIR}`);
  expect(after?.enabled).toBe(false);
  expect(await audits()).toEqual(["instrument.add", "instrument.update"]);
});

test("an admin creates a sign-in link that signs the person in once", async ({ page, browser }) => {
  await makeAdmin();
  await withSql((sql) => sql`insert into allowlist (email) values (${NEW_EMAIL})`);
  await page.goto("/settings/users");
  const row = page.getByRole("listitem").filter({ hasText: NEW_EMAIL });
  await row.getByRole("button", { name: `Create a sign-in link for ${NEW_EMAIL}` }).click();
  const field = row.getByLabel(`Sign-in link for ${NEW_EMAIL}. Send it only to them. It works once, within 24 hours.`);
  const link = await field.inputValue();
  expect(link).toContain("/api/auth/callback/email");
  // Valid for a day, not 15 minutes; the link itself is not in the audit log.
  const [token] = await withSql((sql) => sql`select extract(epoch from expires - now()) as secs from verification_tokens where identifier = ${NEW_EMAIL}`);
  expect(Number(token!.secs)).toBeGreaterThan(23 * 3600);
  expect(await audits()).toContain("allowlist.sign_in_link");

  const them = await browser.newContext();
  const theirPage = await them.newPage();
  await theirPage.goto(link);
  await expect(theirPage).toHaveURL(/\/notice$/);
  await theirPage.getByRole("button", { name: "I understand" }).click();
  await expect(theirPage).not.toHaveURL(/sign-in/);
  // Used once: the same link no longer signs anyone in.
  const again = await (await browser.newContext()).newPage();
  await again.goto(link);
  await expect(again).toHaveURL(/sign-in/);
  await them.close();
});

test("an admin manages the allowlist, roles, and access", async ({ page, browser }) => {
  await makeAdmin();
  await page.goto("/settings/users");
  const add = page.getByRole("form", { name: "Approve an email" });
  await add.getByLabel("Email").fill("not an email");
  await add.getByRole("button", { name: "Approve email" }).click();
  await expect(add.getByText("Enter an email address.")).toBeVisible();
  await add.getByLabel("Email").fill(` ${NEW_EMAIL.toUpperCase()} `);
  await add.getByRole("button", { name: "Approve email" }).click();
  await expect(add.getByRole("status")).toHaveText(`${NEW_EMAIL} can now sign in`);
  const pending = page.getByRole("listitem").filter({ hasText: NEW_EMAIL });
  await expect(pending).toContainText("Not signed in yet");

  // The admin can't lock themselves out.
  const me = page.getByRole("listitem").filter({ hasText: E2E_EMAIL });
  await expect(me.getByRole("button", { name: /Deactivate/ })).toHaveCount(0);

  // The new owner signs in, then is deactivated and loses the session at once.
  const other = await browser.newContext();
  const theirs = await other.newPage();
  await withSql((sql) => sql`insert into users (email, acknowledged_notice_at) values (${NEW_EMAIL}, now())`);
  const token = "e2e-session-token-for-deactivation-test";
  await withSql(
    (sql) => sql`insert into sessions (session_token, user_id, expires) select ${token}, id, now() + interval '1 day' from users where email = ${NEW_EMAIL}`,
  );
  await other.addCookies([{ name: "authjs.session-token", value: token, url: test.info().project.use.baseURL! }]);
  await theirs.goto("/dashboard");
  await expect(theirs).toHaveURL(/\/dashboard$/);

  await page.reload();
  const them = page.getByRole("listitem").filter({ hasText: NEW_EMAIL });
  await them.getByRole("button", { name: `Deactivate ${NEW_EMAIL}` }).click();
  await expect(them.getByRole("status")).toHaveText(`${NEW_EMAIL} is deactivated and signed out`);
  await theirs.goto("/dashboard");
  await expect(theirs).toHaveURL(/\/sign-in/);
  await other.close();

  await them.getByRole("button", { name: `Reactivate ${NEW_EMAIL}` }).click();
  await expect(them.getByRole("status")).toHaveText(`${NEW_EMAIL} can sign in again`);

  await them.getByLabel(`Role for ${NEW_EMAIL}`, { exact: true }).selectOption("admin");
  await them.getByRole("button", { name: `Save role for ${NEW_EMAIL}` }).click();
  await expect(them.getByRole("status").first()).toHaveText(`${NEW_EMAIL} is now an admin`);
  const [role] = await withSql((sql) => sql`select role::text from users where email = ${NEW_EMAIL}`);
  expect(role?.role).toBe("admin");
  const log = await audits();
  expect(log.slice(0, 1)).toEqual(["allowlist.add"]);
  expect(log).toContain("user.deactivate");
  expect(log).toContain("user.reactivate");
  expect(log.at(-1)).toBe("user.role");
});

test("the last admin cannot be demoted", async ({ page }) => {
  await makeAdmin();
  await withSql((sql) => sql`update users set role = 'owner' where role = 'admin' and email <> ${E2E_EMAIL}`);
  try {
    await page.goto("/settings/users");
    const me = page.getByRole("listitem").filter({ hasText: E2E_EMAIL });
    await me.getByLabel(`Role for ${E2E_EMAIL}`, { exact: true }).selectOption("owner");
    await me.getByRole("button", { name: `Save role for ${E2E_EMAIL}` }).click();
    await expect(me.getByRole("alert")).toHaveText("Keep at least one active admin.");
  } finally {
    await withSql((sql) => sql`update users set role = 'admin' where email = 'admin@example.com'`);
  }
});

test("health shows the worker and pairs, and the public check reports problems", async ({ page, playwright, baseURL }) => {
  await makeAdmin();
  await withSql(
    (sql) => sql`insert into job_runs (job, started_at, finished_at, ok, detail) values ('forex_day_roll', now() - interval '1 hour', now() - interval '1 hour', false, ${sql.json({ error: "E2E provider timeout", e2e: true })})`,
  );
  await page.goto("/health");
  await expect(page.getByRole("link", { name: "Health: warning" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Scanner" })).toContainText("version e2e");
  await expect(page.getByRole("region", { name: "Scanner" })).toContainText(/Last day roll\s*! Failed/);
  await expect(page.getByRole("region", { name: "Last completed bar per pair" })).toContainText("EUR/GBP");
  await expect(page.getByRole("region", { name: "Job runs, last 24 hours" })).toContainText("E2E provider timeout");
  await expect(page.getByRole("region", { name: "Notification delivery, last 24 hours" })).toBeVisible();

  const anon = await playwright.request.newContext({ baseURL });
  // The seeded heartbeat is fresh but GBP/USD is stale while forex is open.
  const res = await anon.get("/api/health");
  expect(res.status()).toBe(503);
  expect(await res.json()).toEqual({ ok: false, reasons: ["pairs_stale"] });
  await withSql(
    (sql) => sql`update worker_heartbeat set market = jsonb_set(market, '{stale}', '[]'::jsonb)`,
  );
  expect(await (await anon.get("/api/health")).json()).toEqual({ ok: true });
  await withSql((sql) => sql`update worker_heartbeat set at = now() - interval '10 minutes'`);
  expect(await (await anon.get("/api/health")).json()).toEqual({ ok: false, reasons: ["heartbeat_stale"] });

  expect((await anon.get("/api/health/detail")).status()).toBe(401);
  const detail = await page.request.get("/api/health/detail");
  expect(detail.status()).toBe(200);
  expect((await detail.json()).heartbeat.version).toBe("e2e");
  await anon.dispose();
});

for (const theme of ["light", "dark"] as const) {
  test(`settings and health pages pass axe checks in the ${theme} theme`, async ({ page, context, baseURL }) => {
    await makeAdmin();
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    for (const path of ["/settings", "/settings/brokers", "/settings/pairs", "/settings/users", "/health"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expectNoAxeViolations(page);
    }
  });
}
