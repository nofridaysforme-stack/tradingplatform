import postgres from "postgres";
import { E2E_EMAIL } from "./env";

export function connect() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is required for the end-to-end tests");
  return postgres(url, { max: 1, onnotice: () => {} });
}

/** A fresh, allowlisted owner who has not seen the notice yet. */
export async function resetUser() {
  const sql = connect();
  try {
    await sql`delete from verification_tokens where identifier = ${E2E_EMAIL}`;
    await sql`delete from users where email = ${E2E_EMAIL}`;
    await sql`insert into allowlist (email) values (${E2E_EMAIL}) on conflict do nothing`;
  } finally {
    await sql.end();
  }
}
