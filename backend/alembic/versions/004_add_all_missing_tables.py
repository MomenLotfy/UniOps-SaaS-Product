"""Add all missing tables: integrations, pipelines, pods, threats, vulnerabilities,
cost_metrics, cost_anomalies, savings, alerts, audit_logs, webhooks,
ml_patterns, ml_predictions, ml_recommendations, ml_correlations,
compliance, subscriptions, roles, permissions.

Revision ID: 004
Revises: 003
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── integrations ──────────────────────────────────────────────────────────
    op.create_table(
        "integrations",
        sa.Column("id",            sa.String(36),  primary_key=True),
        sa.Column("tenant_id",     sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name",          sa.String(255), nullable=False),
        sa.Column("type",          sa.String(50),  nullable=False),
        sa.Column("status",        sa.String(50),  server_default="pending"),
        sa.Column("credentials",   sa.JSON,        server_default="{}"),
        sa.Column("config",        sa.JSON,        server_default="{}"),
        sa.Column("last_sync",     sa.DateTime(timezone=True)),
        sa.Column("is_active",     sa.Boolean,     server_default=sa.text("true")),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at",    sa.DateTime(timezone=True)),
        sa.Column("updated_at",    sa.DateTime(timezone=True)),
    )

    # ── pipelines ─────────────────────────────────────────────────────────────
    op.create_table(
        "pipelines",
        sa.Column("id",             sa.String(36),  primary_key=True),
        sa.Column("tenant_id",      sa.String(36),  sa.ForeignKey("tenants.id"),    nullable=False),
        sa.Column("integration_id", sa.String(36),  sa.ForeignKey("integrations.id")),
        sa.Column("external_id",    sa.String(255)),
        sa.Column("name",           sa.String(255), nullable=False),
        sa.Column("repository",     sa.String(255)),
        sa.Column("branch",         sa.String(255), server_default="main"),
        sa.Column("status",         sa.String(50),  server_default="unknown"),
        sa.Column("stage",          sa.String(100)),
        sa.Column("duration",       sa.Integer),
        sa.Column("triggered_by",   sa.String(255)),
        sa.Column("commit_sha",     sa.String(40)),
        sa.Column("commit_message", sa.Text),
        sa.Column("started_at",     sa.DateTime(timezone=True)),
        sa.Column("finished_at",    sa.DateTime(timezone=True)),
        sa.Column("logs_url",       sa.Text),
        sa.Column("metadata",       sa.JSON, server_default="{}"),
        sa.Column("created_at",     sa.DateTime(timezone=True)),
        sa.Column("updated_at",     sa.DateTime(timezone=True)),
    )

    # ── pods ──────────────────────────────────────────────────────────────────
    op.create_table(
        "pods",
        sa.Column("id",             sa.String(36), primary_key=True),
        sa.Column("tenant_id",      sa.String(36), sa.ForeignKey("tenants.id"),    nullable=False),
        sa.Column("integration_id", sa.String(36), sa.ForeignKey("integrations.id")),
        sa.Column("name",           sa.String(255), nullable=False),
        sa.Column("namespace",      sa.String(255), server_default="default"),
        sa.Column("cluster",        sa.String(255)),
        sa.Column("status",         sa.String(50)),
        sa.Column("phase",          sa.String(50)),
        sa.Column("node",           sa.String(255)),
        sa.Column("cpu_request",    sa.Float),
        sa.Column("cpu_limit",      sa.Float),
        sa.Column("cpu_usage",      sa.Float),
        sa.Column("memory_request", sa.Integer),
        sa.Column("memory_limit",   sa.Integer),
        sa.Column("memory_usage",   sa.Integer),
        sa.Column("restart_count",  sa.Integer, server_default="0"),
        sa.Column("containers",     sa.JSON, server_default="[]"),
        sa.Column("labels",         sa.JSON, server_default="{}"),
        sa.Column("created_at",     sa.DateTime(timezone=True)),
        sa.Column("updated_at",     sa.DateTime(timezone=True)),
    )

    # ── threats ───────────────────────────────────────────────────────────────
    op.create_table(
        "threats",
        sa.Column("id",              sa.String(36),  primary_key=True),
        sa.Column("tenant_id",       sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title",           sa.String(500), nullable=False),
        sa.Column("description",     sa.Text),
        sa.Column("severity",        sa.String(50),  nullable=False),
        sa.Column("category",        sa.String(100)),
        sa.Column("source",          sa.String(100)),
        sa.Column("status",          sa.String(50),  server_default="open"),
        sa.Column("resource",        sa.String(500)),
        sa.Column("namespace",       sa.String(255)),
        sa.Column("ip",              sa.String(50)),
        sa.Column("mitre_tactic",    sa.String(100)),
        sa.Column("mitre_technique", sa.String(100)),
        sa.Column("raw_data",        sa.JSON, server_default="{}"),
        sa.Column("detected_at",     sa.DateTime(timezone=True)),
        sa.Column("resolved_at",     sa.DateTime(timezone=True)),
        sa.Column("created_at",      sa.DateTime(timezone=True)),
        sa.Column("updated_at",      sa.DateTime(timezone=True)),
    )

    # ── vulnerabilities ───────────────────────────────────────────────────────
    op.create_table(
        "vulnerabilities",
        sa.Column("id",              sa.String(36),  primary_key=True),
        sa.Column("tenant_id",       sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("cve_id",          sa.String(50)),
        sa.Column("title",           sa.String(500), nullable=False),
        sa.Column("description",     sa.Text),
        sa.Column("severity",        sa.String(50),  nullable=False),
        sa.Column("cvss_score",      sa.Float),
        sa.Column("status",          sa.String(50),  server_default="open"),
        sa.Column("package_name",    sa.String(255)),
        sa.Column("package_version", sa.String(100)),
        sa.Column("fixed_version",   sa.String(100)),
        sa.Column("target",          sa.String(500)),
        sa.Column("image",           sa.String(500)),
        sa.Column("references",      sa.JSON, server_default="[]"),
        sa.Column("created_at",      sa.DateTime(timezone=True)),
        sa.Column("updated_at",      sa.DateTime(timezone=True)),
    )

    # ── cost_metrics ──────────────────────────────────────────────────────────
    op.create_table(
        "cost_metrics",
        sa.Column("id",             sa.String(36),  primary_key=True),
        sa.Column("tenant_id",      sa.String(36),  sa.ForeignKey("tenants.id"),    nullable=False),
        sa.Column("integration_id", sa.String(36),  sa.ForeignKey("integrations.id")),
        sa.Column("provider",       sa.String(50),  nullable=False),
        sa.Column("service",        sa.String(255)),
        sa.Column("region",         sa.String(100)),
        sa.Column("amount",         sa.Float,       nullable=False),
        sa.Column("currency",       sa.String(10),  server_default="USD"),
        sa.Column("period_start",   sa.Date,        nullable=False),
        sa.Column("period_end",     sa.Date,        nullable=False),
        sa.Column("tags",           sa.JSON, server_default="{}"),
        sa.Column("breakdown",      sa.JSON, server_default="{}"),
        sa.Column("created_at",     sa.DateTime(timezone=True)),
        sa.Column("updated_at",     sa.DateTime(timezone=True)),
    )

    # ── cost_anomalies ────────────────────────────────────────────────────────
    op.create_table(
        "cost_anomalies",
        sa.Column("id",            sa.String(36),  primary_key=True),
        sa.Column("tenant_id",     sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("service",       sa.String(255)),
        sa.Column("expected_cost", sa.Float),
        sa.Column("actual_cost",   sa.Float),
        sa.Column("deviation",     sa.Float),
        sa.Column("severity",      sa.String(50)),
        sa.Column("status",        sa.String(50),  server_default="open"),
        sa.Column("detected_date", sa.Date),
        sa.Column("description",   sa.Text),
        sa.Column("created_at",    sa.DateTime(timezone=True)),
        sa.Column("updated_at",    sa.DateTime(timezone=True)),
    )

    # ── savings ───────────────────────────────────────────────────────────────
    op.create_table(
        "savings",
        sa.Column("id",                sa.String(36),  primary_key=True),
        sa.Column("tenant_id",         sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title",             sa.String(500), nullable=False),
        sa.Column("description",       sa.Text),
        sa.Column("category",          sa.String(100)),
        sa.Column("provider",          sa.String(50)),
        sa.Column("potential_savings", sa.Float),
        sa.Column("currency",          sa.String(10),  server_default="USD"),
        sa.Column("effort",            sa.String(50),  server_default="medium"),
        sa.Column("status",            sa.String(50),  server_default="open"),
        sa.Column("resource",          sa.String(500)),
        sa.Column("recommendation",    sa.Text),
        sa.Column("created_at",        sa.DateTime(timezone=True)),
        sa.Column("updated_at",        sa.DateTime(timezone=True)),
    )

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("tenant_id",   sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title",       sa.String(500), nullable=False),
        sa.Column("message",     sa.Text),
        sa.Column("severity",    sa.String(50),  nullable=False),
        sa.Column("category",    sa.String(100)),
        sa.Column("source",      sa.String(100)),
        sa.Column("status",      sa.String(50),  server_default="active"),
        sa.Column("is_read",     sa.Boolean,     server_default=sa.text("false")),
        sa.Column("resource",    sa.String(500)),
        sa.Column("metadata",    sa.JSON, server_default="{}"),
        sa.Column("fired_at",    sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at",  sa.DateTime(timezone=True)),
        sa.Column("updated_at",  sa.DateTime(timezone=True)),
    )

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("tenant_id",   sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id",     sa.String(36),  sa.ForeignKey("users.id")),
        sa.Column("action",      sa.String(100), nullable=False),
        sa.Column("resource",    sa.String(100)),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("ip",          sa.String(50)),
        sa.Column("user_agent",  sa.Text),
        sa.Column("details",     sa.JSON, server_default="{}"),
        sa.Column("status",      sa.String(50), server_default="success"),
        sa.Column("created_at",  sa.DateTime(timezone=True)),
        sa.Column("updated_at",  sa.DateTime(timezone=True)),
    )

    # ── webhooks ──────────────────────────────────────────────────────────────
    op.create_table(
        "webhooks",
        sa.Column("id",                 sa.String(36),  primary_key=True),
        sa.Column("tenant_id",          sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name",               sa.String(255), nullable=False),
        sa.Column("url",                sa.Text,        nullable=False),
        sa.Column("secret",             sa.String(255)),
        sa.Column("events",             sa.JSON, server_default="[]"),
        sa.Column("is_active",          sa.Boolean, server_default=sa.text("true")),
        sa.Column("headers",            sa.JSON, server_default="{}"),
        sa.Column("last_response_code", sa.Integer),
        sa.Column("failure_count",      sa.Integer, server_default="0"),
        sa.Column("created_at",         sa.DateTime(timezone=True)),
        sa.Column("updated_at",         sa.DateTime(timezone=True)),
    )

    # ── compliance ────────────────────────────────────────────────────────────
    op.create_table(
        "compliance",
        sa.Column("id",        sa.String(36),  primary_key=True),
        sa.Column("tenant_id", sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("framework", sa.String(100), nullable=False),
        sa.Column("score",     sa.Float,       server_default="0.0"),
        sa.Column("passed",    sa.Integer,     server_default="0"),
        sa.Column("failed",    sa.Integer,     server_default="0"),
        sa.Column("total",     sa.Integer,     server_default="0"),
        sa.Column("status",    sa.String(50),  server_default="in_progress"),
        sa.Column("details",   sa.JSON, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ── subscriptions ─────────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id",                     sa.String(36),  primary_key=True),
        sa.Column("tenant_id",              sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("plan",                   sa.String(50),  nullable=False),
        sa.Column("status",                 sa.String(50),  server_default="active"),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("stripe_customer_id",     sa.String(255)),
        sa.Column("current_period_start",   sa.DateTime(timezone=True)),
        sa.Column("current_period_end",     sa.DateTime(timezone=True)),
        sa.Column("seats",                  sa.Integer, server_default="5"),
        sa.Column("cancel_at_period_end",   sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at",             sa.DateTime(timezone=True)),
        sa.Column("updated_at",             sa.DateTime(timezone=True)),
    )

    # ── roles ─────────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("tenant_id",   sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name",        sa.String(100), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("permissions", sa.JSON, server_default="[]"),
        sa.Column("is_system",   sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at",  sa.DateTime(timezone=True)),
        sa.Column("updated_at",  sa.DateTime(timezone=True)),
    )

    # ── permissions ───────────────────────────────────────────────────────────
    op.create_table(
        "permissions",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("name",        sa.String(100), unique=True, nullable=False),
        sa.Column("resource",    sa.String(100), nullable=False),
        sa.Column("action",      sa.String(50),  nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("created_at",  sa.DateTime(timezone=True)),
        sa.Column("updated_at",  sa.DateTime(timezone=True)),
    )

    # ── ml_patterns ───────────────────────────────────────────────────────────
    op.create_table(
        "ml_patterns",
        sa.Column("id",           sa.String(36),  primary_key=True),
        sa.Column("tenant_id",    sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name",         sa.String(255), nullable=False),
        sa.Column("pattern_type", sa.String(100)),
        sa.Column("description",  sa.Text),
        sa.Column("confidence",   sa.Float),
        sa.Column("frequency",    sa.String(100)),
        sa.Column("data",         sa.JSON, server_default="{}"),
        sa.Column("created_at",   sa.DateTime(timezone=True)),
        sa.Column("updated_at",   sa.DateTime(timezone=True)),
    )

    # ── ml_predictions ────────────────────────────────────────────────────────
    op.create_table(
        "ml_predictions",
        sa.Column("id",              sa.String(36),  primary_key=True),
        sa.Column("tenant_id",       sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("model_name",      sa.String(100), nullable=False),
        sa.Column("model_version",   sa.String(50),  server_default="1.0.0"),
        sa.Column("prediction_type", sa.String(100)),
        sa.Column("input_data",      sa.JSON, server_default="{}"),
        sa.Column("output_data",     sa.JSON, server_default="{}"),
        sa.Column("confidence",      sa.Float),
        sa.Column("predicted_at",    sa.DateTime(timezone=True)),
        sa.Column("target_date",     sa.DateTime(timezone=True)),
        sa.Column("is_accurate",     sa.Boolean),
        sa.Column("notes",           sa.Text),
        sa.Column("created_at",      sa.DateTime(timezone=True)),
        sa.Column("updated_at",      sa.DateTime(timezone=True)),
    )

    # ── ml_recommendations ────────────────────────────────────────────────────
    op.create_table(
        "ml_recommendations",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("tenant_id",   sa.String(36),  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title",       sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("category",    sa.String(100)),
        sa.Column("priority",    sa.Integer,     server_default="5"),
        sa.Column("confidence",  sa.Float),
        sa.Column("impact",      sa.String(50),  server_default="medium"),
        sa.Column("effort",      sa.String(50),  server_default="medium"),
        sa.Column("status",      sa.String(50),  server_default="pending"),
        sa.Column("action",      sa.Text),
        sa.Column("created_at",  sa.DateTime(timezone=True)),
        sa.Column("updated_at",  sa.DateTime(timezone=True)),
    )

    # ── ml_correlations ───────────────────────────────────────────────────────
    op.create_table(
        "ml_correlations",
        sa.Column("id",                sa.String(36),   primary_key=True),
        sa.Column("tenant_id",         sa.String(36),   sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("metric_a",          sa.String(255),  nullable=False),
        sa.Column("metric_b",          sa.String(255),  nullable=False),
        sa.Column("correlation_score", sa.Float),
        sa.Column("method",            sa.String(50),   server_default="pearson"),
        sa.Column("insight",           sa.String(1000)),
        sa.Column("data_points",       sa.JSON, server_default="{}"),
        sa.Column("created_at",        sa.DateTime(timezone=True)),
        sa.Column("updated_at",        sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    tables = [
        "ml_correlations",
        "ml_recommendations",
        "ml_predictions",
        "ml_patterns",
        "permissions",
        "roles",
        "subscriptions",
        "compliance",
        "webhooks",
        "audit_logs",
        "alerts",
        "savings",
        "cost_anomalies",
        "cost_metrics",
        "vulnerabilities",
        "threats",
        "pods",
        "pipelines",
        "integrations",
    ]
    for table in tables:
        op.drop_table(table)
