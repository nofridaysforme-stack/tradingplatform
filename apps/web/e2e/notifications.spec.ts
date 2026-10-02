import { expect, test, type APIRequestContext } from "@playwright/test";
import { resetUser, withSql } from "./db";
import { E2E_EMAIL } from "./env";
import { expectNoAxeViolations, signIn } from "./helpers";

const SECRET = "e2e-webhook-secret-0123456789";

test.beforeEach(async ({ page }) => {
  await resetUser();
  await signIn(page);
});

const json = (
  request: APIRequestContext,
  url: string,
  data: unknown,
  origin?: string,
) =>
  request.post(url, {
    data,
    headers: {
      "Content-Type": "application/json",
      ...(origin ? { Origin: origin } : {}),
    },
  });

test("the app installs: manifest, service worker, icons, and a CSP that allows the worker", async ({
  page,
  request,
}) => {
  const manifest = await (await request.get("/manifest.webmanifest")).json();
  expect(manifest).toMatchObject({
    name: "Trading desk",
    display: "standalone",
    start_url: "/dashboard",
  });
  expect(manifest.icons.map((i: { purpose: string }) => i.purpose)).toEqual([
    "any",
    "any",
    "maskable",
  ]);
  const sw = await request.get("/sw.js");
  expect(sw.status()).toBe(200);
  expect(sw.headers()["cache-control"]).toContain("no-store");
  expect(await sw.text()).toContain('addEventListener("push"');
  expect(
    (await request.get("/apple-touch-icon.png")).headers()["content-type"],
  ).toBe("image/png");
  const res = await page.goto("/settings/notifications");
  expect(res?.headers()["content-security-policy"]).toContain(
    "worker-src 'self'",
  );
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
    "href",
    "/manifest.webmanifest",
  );
});

test("an owner saves notification settings", async ({ page }) => {
  await page.goto("/settings");
  await page
    .getByRole("link", { name: /Channels, alerts, quiet hours/ })
    .click();
  const form = page.getByRole("form", { name: "Notification settings" });
  await expect(form.getByRole("switch", { name: /Telegram/ })).toBeDisabled();
  await form.getByRole("switch", { name: /Push notifications/ }).uncheck();
  await form.getByLabel("Fib Pivot signals").uncheck();
  await form.getByRole("switch", { name: /Updates/ }).uncheck();
  await form.getByLabel("Only these pairs").check();
  await form
    .getByRole("button", { name: "Save notification settings" })
    .click();
  await expect(
    form.getByText("Choose at least one pair, or all pairs."),
  ).toBeVisible();

  await form.getByText("EUR/USD").click();
  await form.getByLabel("Don't send trade alerts during quiet hours").check();
  await form.getByLabel("From").fill("22:30");
  await form.getByLabel("Until").fill("22:30");
  await form
    .getByRole("button", { name: "Save notification settings" })
    .click();
  await expect(
    form.getByText("Quiet hours need different start and end times."),
  ).toBeVisible();
  await form.getByLabel("Until").fill("06:45");
  await form
    .getByRole("button", { name: "Save notification settings" })
    .click();
  await expect(form.getByRole("status")).toHaveText(
    "Notification settings saved",
  );

  const [row] = await withSql(
    (
      sql,
    ) => sql`select channels::text[] as channels, strategies::text[] as strategies,
      array(select symbol from instruments where id = any(p.instrument_ids)) as pairs,
      quiet_start::text, quiet_end::text, include_updates
      from notification_prefs p join users u on u.id = p.user_id where u.email = ${E2E_EMAIL}`,
  );
  expect(row).toEqual({
    channels: ["email"],
    strategies: ["three_eight", "stocks"],
    pairs: ["EUR/USD"],
    quiet_start: "22:30:00",
    quiet_end: "06:45:00",
    include_updates: false,
  });
  await page.reload();
  await expect(form.getByLabel("From")).toHaveValue("22:30");
  await expect(
    form.getByRole("switch", { name: /Push notifications/ }),
  ).not.toBeChecked();
});

test("a test notification is queued on each channel, with a limit", async ({
  page,
}) => {
  await page.goto("/settings/notifications");
  const test_ = page.getByRole("button", { name: "Send test notification" });
  await test_.click();
  await expect(
    page.getByText("Test notification sent. It arrives within a minute."),
  ).toBeVisible();
  const rows = await withSql(
    (
      sql,
    ) => sql`select n.channel::text, n.status::text from notifications n join users u on u.id = n.user_id
      where u.email = ${E2E_EMAIL} and n.kind = 'test' order by n.channel`,
  );
  expect(rows).toEqual([
    { channel: "webpush", status: "queued" },
    { channel: "email", status: "queued" },
  ]);
  await page.reload();
  await expect(
    page.getByRole("listitem").filter({ hasText: "Test · Email · Sending" }),
  ).toBeVisible();
  await test_.click();
  await expect(
    page.getByText("Test notification sent.", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await test_.click();
  await page.reload();
  await test_.click();
  await expect(
    page.getByText("You sent several tests just now. Try again in 10 minutes."),
  ).toBeVisible();
});

test("push subscriptions are stored for the owner only, from the portal only", async ({
  page,
  baseURL,
}) => {
  const sub = {
    endpoint: "https://push.example.com/send/abc123",
    keys: {
      p256dh:
        "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
      auth: "tBHItJI5svbpez7KI4CCXg",
    },
  };
  expect((await json(page.request, "/api/push/subscribe", sub)).status()).toBe(
    403,
  ); // no Origin
  expect(
    (
      await json(
        page.request,
        "/api/push/subscribe",
        { endpoint: "http://insecure" },
        baseURL,
      )
    ).status(),
  ).toBe(400);
  expect(
    (await json(page.request, "/api/push/subscribe", sub, baseURL)).status(),
  ).toBe(200);
  const count = () =>
    withSql(
      async (sql) =>
        (
          await sql`select count(*)::int as n from push_subscriptions where endpoint = ${sub.endpoint}`
        )[0]?.n,
    );
  expect(await count()).toBe(1);
  await page.goto("/settings/notifications");
  await expect(page.getByText("Push is on for 1 device.")).toBeVisible();
  expect(await (await page.request.get("/api/push/public-key")).json()).toEqual(
    { key: null },
  );
  expect(
    (
      await json(
        page.request,
        "/api/push/unsubscribe",
        { endpoint: sub.endpoint },
        baseURL,
      )
    ).status(),
  ).toBe(200);
  expect(await count()).toBe(0);
});

test("without a server key the device button explains itself", async ({
  page,
  context,
}) => {
  // Headless Chromium on CI reports notifications as denied unless granted.
  await context.grantPermissions(["notifications"]);
  await page.goto("/settings/notifications");
  const turnOn = page.getByRole("button", { name: "Turn on notifications" });
  await expect(turnOn).toBeVisible();
  await turnOn.click();
  await expect(
    page.getByText("Push notifications aren't set up on the server yet.", {
      exact: false,
    }),
  ).toBeVisible();
});

test("Telegram connects through the bot link and the webhook, then disconnects", async ({
  page,
  baseURL,
  playwright,
}) => {
  const link = await (
    await json(page.request, "/api/telegram/link", {}, baseURL)
  ).json();
  expect(link.url).toMatch(
    /^https:\/\/t\.me\/e2e_test_bot\?start=[A-Za-z0-9_-]{32}$/,
  );
  const token = new URL(link.url).searchParams.get("start")!;
  const anon = await playwright.request.newContext({ baseURL });
  const update = {
    message: { text: `/start ${token}`, chat: { id: 987654321 } },
  };
  const hook = (secret: string, header: string) =>
    anon.post(`/api/telegram/webhook/${secret}`, {
      data: update,
      headers: { "X-Telegram-Bot-Api-Secret-Token": header },
    });
  expect((await hook("wrong", SECRET)).status()).toBe(404);
  expect((await hook(SECRET, "wrong")).status()).toBe(404);
  expect((await hook(SECRET, SECRET)).status()).toBe(200);
  const [row] = await withSql(
    (sql) =>
      sql`select t.chat_id::text, t.link_token from telegram_links t join users u on u.id = t.user_id where u.email = ${E2E_EMAIL}`,
  );
  expect(row).toEqual({ chat_id: "987654321", link_token: null });
  expect((await hook(SECRET, SECRET)).status()).toBe(200); // the token works once
  await anon.dispose();

  await page.goto("/settings/notifications");
  await expect(page.getByRole("region", { name: "Telegram" })).toContainText(
    "Connected",
  );
  await expect(page.getByRole("switch", { name: /Telegram/ })).toBeEnabled();
  await page.getByRole("button", { name: "Disconnect Telegram" }).click();
  await expect(
    page.getByRole("button", { name: "Connect Telegram" }),
  ).toBeVisible();
  const left = await withSql(
    (sql) =>
      sql`select count(*)::int as n from telegram_links t join users u on u.id = t.user_id where u.email = ${E2E_EMAIL}`,
  );
  expect(left[0]?.n).toBe(0);
});

test("on iPhone Safari before install, the install guide replaces the button", async ({ page, browserName }) => {
  test.skip(browserName !== "chromium");
  // Safari in a browser tab has no PushManager until the portal is added to the Home Screen.
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "userAgent", {
      get: () => "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    });
    // @ts-expect-error simulating a browser without push
    delete window.PushManager;
  });
  await page.goto("/settings/notifications");
  const guide = page.getByLabel("Install guide");
  await expect(guide).toContainText("On iPhone, add the portal to your Home Screen first.");
  await expect(guide.getByRole("listitem")).toHaveCount(3);
  await expect(page.getByRole("button", { name: "Turn on notifications" })).toHaveCount(0);
});

for (const theme of ["light", "dark"] as const) {
  test(`notification settings pass axe checks in the ${theme} theme`, async ({
    page,
    context,
    baseURL,
  }) => {
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    await page.goto("/settings/notifications");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await page.getByLabel("Only these pairs").check();
    await page.getByLabel("Don't send trade alerts during quiet hours").check();
    await expectNoAxeViolations(page);
  });
}
