# Database

Postgres. The schema of record is `docs/specs/09-database-schema.md`. Plain SQL migrations in `db/migrations/` are the single source of truth; the web app reads the schema with Drizzle in query-only mode and never generates migrations.

## Local use

Install [dbmate](https://github.com/amacneil/dbmate) (`brew install dbmate`, or `npm install -g dbmate`), set `DATABASE_URL` (see `.env.example`), then from the repository root:

```
dbmate up                         # apply migrations
dbmate down                       # roll back the latest migration
dbmate new <name>                 # create a migration
```

dbmate reads migrations from `./db/migrations` by default and writes `db/schema.sql` after each run. Commit `db/schema.sql` with the migration that changed it.

## Deploys

Spec 16 runs migrations as the pre-deploy command on the Railway `web` service: `dbmate --wait up`. Open item: the web Docker image is built from `apps/web` only, so it contains neither dbmate nor `db/migrations`. Before the first deploy (Phase 1), either build the web image from the repository root and copy in the dbmate binary and `db/migrations`, or run migrations from a separate one-off step. The scanner checks the schema version at startup and exits with a clear error if it is behind.
