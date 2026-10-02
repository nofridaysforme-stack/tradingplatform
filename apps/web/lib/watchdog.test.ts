import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { heartbeatAlert, messageHtml, messageText } from "./alert-message";
import { dedupeKey, nextStep, REPEAT_MS } from "./watchdog";

// Written by the scanner's own message code; the scanner tests check the same file.
const FIXTURE = path.resolve(__dirname, "../../../services/scanner/tests/fixtures/heartbeat_alert.json");
const fixture = JSON.parse(readFileSync(FIXTURE, "utf8")) as Record<string, string>;

describe("heartbeat alert message", () => {
  it("matches the scanner's wording and email layout exactly", () => {
    const m = heartbeatAlert(fixture.base_url);
    expect(m).toEqual({ title: fixture.title, body: fixture.body, url: fixture.url });
    expect(messageText(m)).toBe(fixture.text);
    expect(messageHtml(m)).toBe(fixture.html);
  });

  it("does not double the slash after the base address", () => {
    expect(heartbeatAlert("https://desk.example.com/").url).toBe("https://desk.example.com/health");
  });
});

describe("nextStep", () => {
  const now = new Date("2026-10-07T16:00:00Z");
  const ago = (ms: number) => new Date(now.getTime() - ms);
  const MIN = 60_000;

  it("does nothing while the heartbeat is under 5 minutes old", () => {
    expect(nextStep(ago(4 * MIN), null, now)).toBe("fresh");
    expect(nextStep(ago(5 * MIN), null, now)).toBe("fresh");
  });

  it("alerts when the heartbeat is late or missing and nothing was sent", () => {
    expect(nextStep(ago(5 * MIN + 1000), null, now)).toBe("send");
    expect(nextStep(null, null, now)).toBe("send");
    expect(nextStep(null, { lastSentAt: null, resolvedAt: null }, now)).toBe("send");
  });

  it("repeats at most once an hour", () => {
    expect(nextStep(null, { lastSentAt: ago(59 * MIN), resolvedAt: null }, now)).toBe("wait");
    expect(nextStep(null, { lastSentAt: ago(REPEAT_MS), resolvedAt: null }, now)).toBe("send");
  });

  it("starts over after the scanner resolved the last one", () => {
    expect(nextStep(null, { lastSentAt: ago(10 * MIN), resolvedAt: ago(5 * MIN) }, now)).toBe("send");
  });
});

describe("dedupeKey", () => {
  it("uses the scanner's format, to the UTC minute", () => {
    expect(dedupeKey(new Date("2026-10-02T09:05:59.900Z"))).toBe("health:heartbeat_stale:20261002T0905");
  });
});
