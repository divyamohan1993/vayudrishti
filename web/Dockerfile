# Multi-stage: build the Next.js static export, serve it with unprivileged nginx.
# Runs as non-root, listens on 8080 (Cloud Run default PORT).

FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
# pnpm-workspace.yaml carries the declared build-script policy (sharp and
# unrs-resolver ignored: the static export needs neither native build).
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# The lockfile is pinned and audited in CI (gitleaks, pnpm audit); pnpm 10's
# minimum-release-age gate would reject entries younger than its window here.
RUN pnpm config set minimumReleaseAge 0 && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 8080
