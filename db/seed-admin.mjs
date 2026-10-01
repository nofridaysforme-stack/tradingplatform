// Adds SEED_ADMIN_EMAIL to the allowlist and creates that user with role 'admin'
// (spec 15: "The first admin comes from the seed"). Idempotent; runs after migrations
// on each web deploy. An existing user row is left as is, so a later role change made
// in Settings is not undone.
import postgres from "postgres";

const email = process.env.SEED_ADMIN_EMAIL?.trim().toLowerCase();
if (!email) {
  console.log("seed-admin: SEED_ADMIN_EMAIL not set, skipping");
  process.exit(0);
}
if (!process.env.DATABASE_URL) {
  console.error("seed-admin: DATABASE_URL is required");
  process.exit(1);
}

const sql = postgres(process.env.DATABASE_URL, { max: 1, onnotice: () => {} });
try {
  await sql.begin(async (tx) => {
    await tx`INSERT INTO allowlist (email) VALUES (${email}) ON CONFLICT (email) DO NOTHING`;
    await tx`INSERT INTO users (email, role) VALUES (${email}, 'admin') ON CONFLICT (email) DO NOTHING`;
  });
  console.log("seed-admin: admin email is on the allowlist");
} finally {
  await sql.end();
}
