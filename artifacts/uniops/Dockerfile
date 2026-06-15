# Build stage
FROM node:22-alpine AS builder
WORKDIR /workspace
RUN npm install -g pnpm@9.12.0
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY tsconfig.base.json ./
COPY lib/ ./lib/
COPY artifacts/uniops/package.json ./artifacts/uniops/
RUN pnpm install --no-frozen-lockfile
COPY artifacts/uniops/ ./artifacts/uniops/
WORKDIR /workspace/artifacts/uniops
RUN pnpm build:standalone

# Production stage
FROM nginx:1.27-alpine
COPY --from=builder /workspace/artifacts/uniops/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
