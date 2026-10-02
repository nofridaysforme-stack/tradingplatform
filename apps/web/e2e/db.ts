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
export const removeMarket = () => withSql((sql) => clearMarket(sql));
