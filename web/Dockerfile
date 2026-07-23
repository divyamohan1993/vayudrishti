# Multi-stage: build the Next.js static export, serve it with unprivileged nginx.
# Runs as non-root, listens on 8080 (Cloud Run default PORT).

FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 8080
