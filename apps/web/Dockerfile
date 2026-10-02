# Build context: the repository root (Railway: root directory "/", Dockerfile path "apps/web/Dockerfile").
FROM node:24-slim AS base
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/ .
RUN pnpm build

FROM base AS dbtools
WORKDIR /app/db
COPY db/package.json db/package-lock.json ./
RUN npm ci --omit=dev
COPY db/migrations ./migrations
COPY db/migrate.sh db/seed-admin.mjs db/telegram-webhook.mjs ./

FROM node:24-slim AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=dbtools /app/db ./db
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
# Pre-deploy command: /app/db/migrate.sh
CMD ["node", "server.js"]
