import { expect, test } from "@playwright/test";
import { drizzle } from "drizzle-orm/postgres-js";
import type { AlertMessage } from "../lib/alert-message";
import { checkHeartbeat, type Senders } from "../lib/watchdog";
import { connect, withSql } from "./db";

// The web service's scanner heartbeat alert (spec 11) against the real schema, with recording
// senders in place of Resend and Telegram. The server under test runs with HEALTH_WATCHDOG=off,
// so only this test touches the alert state. The check gets a client that Drizzle has wrapped,
// as in the app (Drizzle turns off postgres.js date parsing and serializing on its client).

const ADMIN_TG = "watchdog-admin-tg@example.com";
const ADMIN_NO_LINK = "watchdog-admin-nolink@example.com";
const OWNER = "watchdog-owner@example.com";
const OPS = "watchdog-ops@example.com";
const BASE = "https://desk.example.com";
const MIN = 60_000;

interface Calls {
  email: string[];
  telegram: number[];
}

function recording(calls: Calls, opts: { failEmail?: boolean } = {}): Senders {
  return {
    email: async (to: string, m: AlertMessage) => {
      expect(m.title).toBe("Health alert: scanner heartbeat is late");
      if (opts.failEmail) throw Object.assign(new Error("boom"), { name: "resend_validation_error" });
      calls.email.push(to);
    },
    telegram: async (chatId: number, m: AlertMessage) => {
      expect(m.url).toBe(`${BASE}/health`);
      calls.telegram.push(chatId);
    },
  };
}

const ours = (c: Calls): Calls => ({
  email: c.email.filter((e) => e.startsWith("watchdog-")).sort(),
  telegram: c.telegram.filter((id) => id === 777001),
});

test.describe.configure({ mode: "serial" });

test("a late heartbeat alerts admins and ops once an hour, then starts over after Resolved", async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "database test; runs once");
  await withSql(async (sql) => {
    const [saved] = await sql<{ at: Date; version: string | null; market: unknown }[]>`SELECT at, version, market FROM worker_heartbeat`;
    const [savedAlert] = await sql`SELECT * FROM health_alerts WHERE condition = 'heartbeat_stale'`;
    const cleanup = async () => {
      await sql`DELETE FROM users WHERE email IN (${ADMIN_TG}, ${ADMIN_NO_LINK}, ${OWNER})`;
      await sql`DELETE FROM notifications WHERE user_id IS NULL AND payload->>'to' = ${OPS}`;
      await sql`DELETE FROM health_alerts WHERE condition = 'heartbeat_stale'`;
    };
    await cleanup();
    const app = connect();
    drizzle({ client: app });
    try {
      const [tg] = await sql<{ id: string }[]>`INSERT INTO users (email, role) VALUES (${ADMIN_TG}, 'admin') RETURNING id`;
      const [noLink] = await sql<{ id: string }[]>`INSERT INTO users (email, role) VALUES (${ADMIN_NO_LINK}, 'admin') RETURNING id`;
      await sql`INSERT INTO users (email, role) VALUES (${OWNER}, 'owner')`;
      await sql`INSERT INTO notification_prefs (user_id, channels) VALUES
                (${tg.id}, '{email,telegram}'), (${noLink.id}, '{email,telegram}')`;
      await sql`INSERT INTO telegram_links (user_id, chat_id, linked_at) VALUES (${tg.id}, 777001, now())`;

      const t0 = new Date();
      const setHeartbeat = (at: Date) =>
        sql`INSERT INTO worker_heartbeat (id, at, version) VALUES (true, ${at}, 'e2e')
            ON CONFLICT (id) DO UPDATE SET at = EXCLUDED.at`;
      const run = (now: Date, senders: Senders) => checkHeartbeat(app, { now, baseUrl: BASE, opsEmail: OPS, senders });

      // Fresh heartbeat: nothing happens.
      await setHeartbeat(new Date(t0.getTime() - 2 * MIN));
      let calls: Calls = { email: [], telegram: [] };
      expect((await run(t0, recording(calls))).step).toBe("fresh");
      expect(calls).toEqual({ email: [], telegram: [] });

      // Late by 10 minutes: email to both admins and ops, Telegram to the linked admin only.
      await setHeartbeat(new Date(t0.getTime() - 10 * MIN));
      expect((await run(t0, recording(calls))).step).toBe("send");
      expect(ours(calls)).toEqual({ email: [ADMIN_NO_LINK, ADMIN_TG, OPS], telegram: [777001] });
      const [alert] = await sql<{ last_sent_at: Date; resolved_at: Date | null }[]>`
        SELECT last_sent_at, resolved_at FROM health_alerts WHERE condition = 'heartbeat_stale'`;
      expect(alert.last_sent_at.getTime()).toBe(t0.getTime());
      expect(alert.resolved_at).toBeNull();
      const rows = await sql<{ email: string | null; channel: string; status: string; error: string | null }[]>`
        SELECT coalesce(u.email, n.payload->>'to') AS email, n.channel::text, n.status::text, n.error
        FROM notifications n LEFT JOIN users u ON u.id = n.user_id
        WHERE n.kind = 'health' AND coalesce(u.email, n.payload->>'to') LIKE 'watchdog-%'
        ORDER BY 1, 2`;
      expect(rows).toEqual([
        { email: ADMIN_NO_LINK, channel: "email", status: "sent", error: null },
        { email: ADMIN_NO_LINK, channel: "telegram", status: "skipped", error: "telegram_not_linked" },
        { email: ADMIN_TG, channel: "email", status: "sent", error: null },
        { email: ADMIN_TG, channel: "telegram", status: "sent", error: null },
        { email: OPS, channel: "email", status: "sent", error: null },
      ]);

      // Still down 30 minutes later: no repeat yet. An hour after the first: one repeat.
      calls = { email: [], telegram: [] };
      expect((await run(new Date(t0.getTime() + 30 * MIN), recording(calls))).step).toBe("wait");
      expect(ours(calls)).toEqual({ email: [], telegram: [] });
      expect((await run(new Date(t0.getTime() + 60 * MIN), recording(calls))).step).toBe("send");
      expect(ours(calls).email).toHaveLength(3);

      // The scanner came back and sent "Resolved"; a new outage alerts again straight away,
      // and a failed email is recorded without the provider's raw message.
      const t1 = new Date(t0.getTime() + 120 * MIN);
      await sql`UPDATE health_alerts SET resolved_at = ${new Date(t1.getTime() - 20 * MIN)} WHERE condition = 'heartbeat_stale'`;
      await setHeartbeat(new Date(t1.getTime() - 6 * MIN));
      calls = { email: [], telegram: [] };
      const failed = await run(t1, recording(calls, { failEmail: true }));
      expect(failed.step).toBe("send");
      expect(ours(calls).telegram).toEqual([777001]);
      const [restart] = await sql<{ first_seen_at: Date; resolved_at: Date | null }[]>`
        SELECT first_seen_at, resolved_at FROM health_alerts WHERE condition = 'heartbeat_stale'`;
      expect(restart.first_seen_at.getTime()).toBe(t1.getTime());
      expect(restart.resolved_at).toBeNull();
      const [bad] = await sql<{ status: string; error: string }[]>`
        SELECT n.status::text, n.error FROM notifications n JOIN users u ON u.id = n.user_id
        WHERE u.email = ${ADMIN_TG} AND n.channel = 'email' AND n.created_at >= now() - interval '1 minute'
        ORDER BY n.id DESC LIMIT 1`;
      expect(bad).toEqual({ status: "failed", error: "resend_validation_error" });

      // Without email or Telegram configured, the rows say so and the alert still counts as sent.
      await sql`UPDATE health_alerts SET resolved_at = now() WHERE condition = 'heartbeat_stale'`;
      expect((await run(new Date(t1.getTime() + MIN), {})).step).toBe("send");
      const skipped = await sql<{ error: string }[]>`
        SELECT DISTINCT n.error FROM notifications n JOIN users u ON u.id = n.user_id
        WHERE u.email = ${ADMIN_TG} AND n.status = 'skipped'`;
      expect(skipped.map((r) => r.error)).toEqual(["not_configured"]);
    } finally {
      await app.end();
      await cleanup();
      if (savedAlert) await sql`INSERT INTO health_alerts ${sql(savedAlert)}`;
      if (saved) {
        await sql`UPDATE worker_heartbeat SET at = ${saved.at}, version = ${saved.version}`;
      } else {
        await sql`DELETE FROM worker_heartbeat`;
      }
    }
  });
});
