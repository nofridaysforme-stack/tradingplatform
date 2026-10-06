import { afterEach, describe, expect, it, vi } from "vitest";
import { emailConfigured } from "./mail";

describe("emailConfigured", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("needs both the Resend key and a sender address", () => {
    vi.stubEnv("AUTH_TEST_MAILBOX", "");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("EMAIL_FROM", "");
    expect(emailConfigured()).toBe(false);
    vi.stubEnv("RESEND_API_KEY", "re_test");
    expect(emailConfigured()).toBe(false);
    vi.stubEnv("EMAIL_FROM", "Trading desk <alerts@example.com>");
    expect(emailConfigured()).toBe(true);
  });

  it("counts the test mailbox used by the end-to-end tests", () => {
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("AUTH_TEST_MAILBOX", "/tmp/mailbox");
    expect(emailConfigured()).toBe(true);
  });
});
