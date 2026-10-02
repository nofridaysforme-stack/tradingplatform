import "server-only";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

declare global {
  // One pool per process, kept across hot reloads in development.
  var __sql: ReturnType<typeof postgres> | undefined;
}

// postgres.js connects on the first query, so importing this during a build is safe.
export const sql = (globalThis.__sql ??= postgres(process.env.DATABASE_URL ?? "", {
  max: 5,
  onnotice: () => {},
}));

export const db = drizzle({ client: sql, schema });
