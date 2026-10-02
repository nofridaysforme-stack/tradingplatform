import { defineConfig, devices } from "@playwright/test";
import { BASE_URL, MAILBOX, PORT } from "./e2e/env";

// End-to-end tests run the production build against a migrated database.
//   pnpm build && pnpm test:e2e
// Needs DATABASE_URL. Sign-in links are written to AUTH_TEST_MAILBOX instead of being emailed.

export default defineConfig({
  testDir: "e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  projects: [
    { name: "mobile", use: { ...devices["Pixel 7"] } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
  ],
  webServer: {
    // The standalone server needs the static files next to it, as in the Docker image.
    command:
      "cp -r .next/static .next/standalone/.next/ && cp -r public .next/standalone/ && node .next/standalone/server.js",
    url: `${BASE_URL}/sign-in`,
    reuseExistingServer: !process.env.CI,
    env: {
      PORT: String(PORT),
      HOSTNAME: "localhost",
      DATABASE_URL: process.env.DATABASE_URL ?? "",
      AUTH_SECRET: "e2e-secret-not-for-production-0123456789",
      AUTH_URL: BASE_URL,
      AUTH_TEST_MAILBOX: MAILBOX,
      AUTH_IP_LIMIT: "1000",
    },
  },
});
