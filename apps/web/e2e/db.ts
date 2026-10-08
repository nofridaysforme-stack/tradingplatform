import postgres from "postgres";
import { E2E_EMAIL } from "./env";
import { clearMarket, seedMarket } from "./seed";

export function connect() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is required for the end-to-end tests");
  return postgres(url, { max: 1, onnotice: () => {} });
}

export async function withSql<T>(fn: (sql: postgres.Sql) => Promise<T>): Promise<T> {
  const sql = connect();
  try {
    return await fn(sql);
  } finally {
    await sql.end();
  }
}

/** A fresh, allowlisted owner who has not seen the notice yet. */
export async function resetUser() {
  await withSql(async (sql) => {
    await sql`delete from verification_tokens where identifier = ${E2E_EMAIL}`;
    await sql`delete from audit_log where user_id in (select id from users where email = ${E2E_EMAIL})`;
    await sql`delete from users where email = ${E2E_EMAIL}`;
    await sql`insert into allowlist (email) values (${E2E_EMAIL}) on conflict do nothing`;
  });
}

export async function makeAdmin() {
  await withSql((sql) => sql`update users set role = 'admin' where email = ${E2E_EMAIL}`);
}

export const resetMarket = () => withSql((sql) => seedMarket(sql));
/** The forex switch. The tests run with forex on; e2e/forex-pause.spec.ts turns it off. */
export const setForex = (enabled: boolean) => withSql((sql) => sql`update app_settings set forex_enabled = ${enabled}, updated_by = null`);
export const removeMarket = () => withSql((sql) => clearMarket(sql));

export interface RulesSnapshot {
  versions: { key: string; current_version: number }[];
  configs: { strategy: string; enabled: boolean; instrument_ids: string[] | null }[];
}

/** Rule state before a test that edits rules, so it can be put back exactly. */
export const snapshotRules = () =>
  withSql(async (sql) => ({
    versions: await sql<RulesSnapshot["versions"]>`select key, current_version from rule_definitions`,
    configs: await sql<RulesSnapshot["configs"]>`select strategy::text, enabled, instrument_ids from strategy_configs`,
  }));

export const restoreRules = (snap: RulesSnapshot) =>
  withSql(async (sql) => {
    for (const v of snap.versions) {
      await sql`update rule_definitions set current_version = ${v.current_version} where key = ${v.key}`;
      await sql`delete from rule_versions where key = ${v.key} and version > ${v.current_version}`;
    }
    for (const c of snap.configs) {
      await sql`update strategy_configs set enabled = ${c.enabled}, instrument_ids = ${c.instrument_ids}, updated_by = null where strategy = ${c.strategy}::strategy_key`;
    }
    await sql`delete from strategy_param_overrides where updated_by in (select id from users where email = ${E2E_EMAIL})`;
  });

export const ruleState = (key: string) =>
  withSql(async (sql) => {
    const [row] = await sql<{ current_version: number; status: string; params: Record<string, unknown>; revision: number }[]>`
      select d.current_version, v.status::text, v.params, (select revision::int from rule_config_revision) as revision
      from rule_definitions d join rule_versions v on v.key = d.key and v.version = d.current_version where d.key = ${key}`;
    const audits = await sql<{ action: string }[]>`select action from audit_log where target like ${key + "%"} order by id`;
    return { ...row!, audits: audits.map((a) => a.action) };
  });
