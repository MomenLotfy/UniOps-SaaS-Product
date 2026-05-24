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

COPY --from=deps /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY . .

RUN mkdir -p logs models && chmod +x entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/entrypoint.sh"]
