# ── Stage 1: build ─────────────────────────────────────────────────────────────
# Build context MUST be the project root (not artifacts/uniops/)
# docker-compose sets: context: . dockerfile: artifacts/uniops/Dockerfile
FROM node:22-alpine AS builder
WORKDIR /workspace

# Install pnpm
RUN npm install -g pnpm@9.12.0

# Copy workspace manifests first (cache layer)
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY tsconfig.base.json ./

# Copy all lib packages the frontend depends on
COPY lib/ ./lib/

# Copy frontend package.json for dependency resolution
COPY artifacts/uniops/package.json ./artifacts/uniops/

# Install all workspace dependencies (resolves catalog: entries)
RUN pnpm install --no-frozen-lockfile

# Copy frontend source
COPY artifacts/uniops/ ./artifacts/uniops/

# Build standalone bundle (no Replit plugins, no @assets alias)
WORKDIR /workspace/artifacts/uniops
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN pnpm build:standalone

# ── Stage 2: serve with nginx ──────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production

COPY --from=builder /workspace/artifacts/uniops/dist /usr/share/nginx/html
COPY artifacts/uniops/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- --tries=1 http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
