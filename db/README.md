# Database

Postgres. The schema of record is `docs/specs/09-database-schema.md`. Plain SQL migrations in `db/migrations/` are the single source of truth; the web app reads the schema with Drizzle in query-only mode and never generates migrations.

| File | Purpose |
|---|---|
| `migrations/` | dbmate migrations: the schema, then the seed (instruments, strategies, rules version 1, singletons) |
| `schema.sql` | Schema dump written by dbmate after each local run. Commit it with the migration that changed it. |
| `seed-admin.mjs` | Adds `SEED_ADMIN_EMAIL` to the allowlist and creates that user as admin. Idempotent. |
| `migrate.sh` | Applies migrations, then runs the admin seed. The Railway pre-deploy command. |

## Local use

Set `DATABASE_URL` (see `.env.example`), then from the repository root:

```
cd db && npm install              # installs dbmate and the Postgres client for the seed
cd db && ./migrate.sh             # apply migrations and the admin seed

# dbmate directly, from the repository root (reads ./db/migrations)
db/node_modules/.bin/dbmate up
db/node_modules/.bin/dbmate down  # roll back the latest migration
db/node_modules/.bin/dbmate new <name>
```

## Deploys

The web image is built from the repository root (Railway: root directory `/`, Dockerfile path `apps/web/Dockerfile`) and carries dbmate, the migrations, and the seed script under `/app/db`. Set the web service's pre-deploy command to `/app/db/migrate.sh`. The scanner checks the schema version at startup and exits with a clear error if it is behind.
