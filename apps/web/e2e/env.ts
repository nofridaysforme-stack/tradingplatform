import path from "node:path";

export const PORT = 3100;
export const BASE_URL = `http://localhost:${PORT}`;
// Sign-in links land here as <email>.json instead of being emailed.
export const MAILBOX = path.resolve(__dirname, "../test-results/mailbox");
export const E2E_EMAIL = "e2e-owner@example.com";
