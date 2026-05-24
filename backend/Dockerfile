# ── Stage 1: dependency builder ────────────────────────────────────────────────
FROM python:3.12-alpine3.20 AS deps

WORKDIR /build

RUN apk add --no-cache \
    build-base \
    postgresql-dev \
    musl-dev \
    libffi-dev \
    openssl-dev

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: production image ──────────────────────────────────────────────────
FROM python:3.12-alpine3.20 AS production

WORKDIR /app

RUN apk add --no-cache \
    libpq \
    curl \
    wget \
    git \
    docker-cli

# ── gitleaks: secrets scanner ──────────────────────────────────────────────────
RUN GITLEAKS_VERSION=8.18.4 && \
    wget -qO- "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    | tar xz -C /usr/local/bin/ gitleaks && \
    chmod +x /usr/local/bin/gitleaks && \
    gitleaks version || echo "gitleaks install skipped (network unavailable in build)"

# ── trivy: container + dependency scanner ──────────────────────────────────────
RUN TRIVY_VERSION=0.51.2 && \
    wget -qO /tmp/trivy.tar.gz \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" && \
    tar xz -C /usr/local/bin/ -f /tmp/trivy.tar.gz trivy && \
    rm /tmp/trivy.tar.gz && \
    chmod +x /usr/local/bin/trivy || echo "trivy install skipped (network unavailable in build)"

COPY --from=deps /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY . .

RUN mkdir -p logs models && chmod +x entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/entrypoint.sh"]
