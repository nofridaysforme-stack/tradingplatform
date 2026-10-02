import { expect, test } from "@playwright/test";
import { resetUser } from "./db";
import { latestLink, requestLink } from "./helpers";

test.beforeEach(async () => {
  await resetUser();
});

test("signed-out visitors are sent to sign in", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("button", { name: "Email me a sign-in link" })).toBeVisible();
});

test("an email that is not on the allowlist gets no link", async ({ page }) => {
  await requestLinkExpectingError(page, "stranger@example.org");
  await expect(page.getByText("This email isn't approved. Ask an admin to add it.")).toBeVisible();
});

test("an invalid email is rejected", async ({ page }) => {
  await requestLinkExpectingError(page, "not-an-email");
  await expect(page.locator("#email-error")).toBeVisible();
});

test("a link signs in, shows the notice once, then opens the dashboard", async ({ page, browser }) => {
  await requestLink(page);
  const link = latestLink();
  await page.goto(link);
  await expect(page).toHaveURL(/\/notice$/);
  await page.getByRole("button", { name: "I understand" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Signals" })).toBeVisible();

  // The notice is not shown again.
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/settings$/);

  // A link works once.
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto(link);
  await expect(second).toHaveURL(/\/sign-in/);
  await second.goto("/dashboard");
  await expect(second).toHaveURL(/\/sign-in$/);
  await other.close();
});

async function requestLinkExpectingError(page: import("@playwright/test").Page, email: string) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Email me a sign-in link" }).click();
  await expect(page.locator("#email-error")).toBeVisible();
}
