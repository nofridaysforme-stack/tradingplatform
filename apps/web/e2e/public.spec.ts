import { expect, test } from "@playwright/test";
import { E2E_EMAIL } from "./env";
import { resetUser } from "./db";
import { expectNoAxeViolations, latestLink, requestLink } from "./helpers";

for (const theme of ["light", "dark"] as const) {
  test(`sign-in and notice pass axe checks in the ${theme} theme`, async ({ page, context, baseURL }) => {
    await resetUser();
    await context.addCookies([{ name: "theme", value: theme, url: baseURL! }]);
    await page.goto("/sign-in");
    await expectNoAxeViolations(page);
    await requestLink(page);
    await expectNoAxeViolations(page);
    await page.goto(latestLink(E2E_EMAIL));
    await expect(page).toHaveURL(/\/notice$/);
    await expectNoAxeViolations(page);
  });
}
