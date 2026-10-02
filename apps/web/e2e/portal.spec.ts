import { expect, test } from "@playwright/test";
import { resetUser } from "./db";
import { expectNoAxeViolations, signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await resetUser();
  await signIn(page);
});

test("every nav destination opens", async ({ page }) => {
  for (const path of ["/dashboard", "/levels", "/stocks", "/holdings", "/history", "/econ", "/health", "/settings"]) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(200);
  }
});

test("the theme choice is saved", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("Dark").check();
  await page.getByRole("button", { name: "Save theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("sign out ends the session", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/sign-in/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/sign-in$/);
});

test("responses carry the security headers", async ({ page }) => {
  const response = await page.goto("/dashboard");
  const headers = response?.headers() ?? {};
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["content-security-policy"]).toMatch(/script-src 'self' 'nonce-[^']+' 'strict-dynamic'/);
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-robots-tag"]).toContain("noindex");
});

for (const theme of ["light", "dark"] as const) {
  test(`pages pass axe checks in the ${theme} theme`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    for (const path of ["/dashboard", "/settings", "/stocks"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expectNoAxeViolations(page);
    }
  });
}
