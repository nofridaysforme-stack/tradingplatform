#!/bin/sh
# Railway pre-deploy command for the web service: apply migrations, then the admin seed.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
PATH="$here/node_modules/.bin:$PATH"
dbmate --wait --no-dump-schema --migrations-dir "$here/migrations" up
node "$here/seed-admin.mjs"
