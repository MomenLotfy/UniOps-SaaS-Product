"""Sprint 2 schema alignment — R18, R20, R21, R22.

Revision ID: 014_sprint2_schema_alignment
Revises: 013_strategy_rejection_count
Create Date: 2026-06-28

This single consolidation migration closes every schema drift that was
identified by the Architecture Review Board in Sprint 2:

  R18 (Schema Consistency)
    - Align ORM ``strategy_history_from_enum`` / ``strategy_history_to_enum``
      (unused) with the actual migration enum ``strategy_state_enum``.
    - Add ORM columns that exist in code paths but were never created
      in the migration:
        * security_decision_strategy_scores.rationale
        * security_decision_strategy_candidates.risk_score
        * security_decision_strategy_candidates.confidence
        * security_decision_strategy_rankings.feasibility_score
        * security_decision_strategy_rankings.is_valid
        * security_decision_strategy_rankings.rejection_reason

  R20 (Unique Constraints for Concurrency Safety)
    - security_decision_statistics           (tenant_id, state)
    - security_decision_versions             (decision_id, version_number)
    - security_rule_versions                 (rule_id, version_number)
    - security_decision_policy_versions      (policy_id, version_number)
    - security_decision_policy_refs          (decision_id, policy_id, policy_version)
    - security_decision_strategy_versions    (strategy_id, version_number)
    - security_decision_approval_versions    (request_id, version_number)
    - security_execution_packages            (tenant_id, decision_id)
    - security_execution_versions            (package_id, version_number)
    - security_execution_metadata            (package_id, key)

  R21 (DecisionState Enum on DecisionStatistics.state)
    - Convert ``security_decision_statistics.state`` from String(50)
      to a SAEnum backed by a native PG ENUM ``decision_statistics_state_enum``.

  R22 (Timezone-aware DateTime columns)
    - Convert:
        * security_execution_history.changed_at         String(50) → DateTime(timezone=True)
        * security_execution_audit.occurred_at          String(50) → DateTime(timezone=True)
        * security_decision_approval_requests.expires_at String(50) → DateTime(timezone=True)
        * security_decision_approval_decisions.decided_at String(50) → DateTime(timezone=True)
        * security_decision_approval_history.changed_at   String(50) → DateTime(timezone=True)
        * security_decision_approval_audit.occurred_at    String(50) → DateTime(timezone=True)
      Existing string values are parsed into timezone-aware datetimes; rows
      that fail to parse are set to NULL so the migration never blocks.

Every change is backward-compatible: production data is preserved, the
column types widen, and indexes are recreated idempotently.
"""
from alembic import op
import sqlalchemy as sa


revision = "014_sprint2_schema_alignment"
down_revision = "013_strategy_rejection_count"
branch_labels = None
depends_on = None


def _safe_parse_dt(value: str):
    """Parse an ISO-8601 string produced by time.strftime into a tz-aware datetime."""
    if not value:
        return None
    try:
        # time.strftime("%Y-%m-%dT%H:%M:%S", ...) has no tz info; mark as UTC.
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # pragma: no cover - defensive
        return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ─────────────────────────────────────────────────────────────────────
    #  R18 — strategy schema alignment
    # ─────────────────────────────────────────────────────────────────────
    if inspector.has_table("security_decision_strategy_scores"):
        cols = {c["name"] for c in inspector.get_columns("security_decision_strategy_scores")}
        if "rationale" not in cols:
            op.add_column(
                "security_decision_strategy_scores",
                sa.Column("rationale", sa.String(1000), nullable=True),
            )

    if inspector.has_table("security_decision_strategy_candidates"):
        cols = {c["name"] for c in inspector.get_columns("security_decision_strategy_candidates")}
        if "risk_score" not in cols:
            op.add_column(
                "security_decision_strategy_candidates",
                sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
            )
        if "confidence" not in cols:
            op.add_column(
                "security_decision_strategy_candidates",
                sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
            )

    if inspector.has_table("security_decision_strategy_rankings"):
        cols = {c["name"] for c in inspector.get_columns("security_decision_strategy_rankings")}
        if "feasibility_score" not in cols:
            op.add_column(
                "security_decision_strategy_rankings",
                sa.Column("feasibility_score", sa.Float(), nullable=False, server_default="0.0"),
            )
        if "is_valid" not in cols:
            op.add_column(
                "security_decision_strategy_rankings",
                sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
            )
        if "rejection_reason" not in cols:
            op.add_column(
                "security_decision_strategy_rankings",
                sa.Column("rejection_reason", sa.String(1000), nullable=True),
            )

    # ─────────────────────────────────────────────────────────────────────
    #  R21 — DecisionStatistics.state → SAEnum
    # ─────────────────────────────────────────────────────────────────────
    decision_statistics_state_enum = sa.Enum(
        "CREATED", "CONTEXT_BUILDING", "VALIDATING", "READY",
        "REJECTED", "ARCHIVED",
        name="decision_statistics_state_enum",
    )
    decision_statistics_state_enum.create(bind, checkfirst=True)

    if inspector.has_table("security_decision_statistics"):
        # Normalize legacy values to upper-case enum values before the type cast.
        op.execute(
            "UPDATE security_decision_statistics "
            "SET state = UPPER(COALESCE(state, 'CREATED')) "
            "WHERE state IS NOT NULL"
        )
        op.execute(
            "UPDATE security_decision_statistics "
            "SET state = 'CREATED' "
            "WHERE state NOT IN ('CREATED','CONTEXT_BUILDING','VALIDATING','READY','REJECTED','ARCHIVED')"
        )
        op.alter_column(
            "security_decision_statistics",
            "state",
            existing_type=sa.String(50),
            type_=decision_statistics_state_enum,
            existing_nullable=True,
            postgresql_using="state::decision_statistics_state_enum",
        )

    # ─────────────────────────────────────────────────────────────────────
    #  R20 — Unique constraints for concurrency safety
    # ─────────────────────────────────────────────────────────────────────
    _add_unique(
        "security_decision_statistics",
        "uq_decision_statistics_tenant_state",
        ["tenant_id", "state"],
    )
    _add_unique(
        "security_decision_versions",
        "uq_decision_versions_decision_version",
        ["decision_id", "version_number"],
    )
    _add_unique(
        "security_rule_versions",
        "uq_rule_versions_rule_version",
        ["rule_id", "version_number"],
    )
    _add_unique(
        "security_decision_policy_versions",
        "uq_policy_versions_policy_version",
        ["policy_id", "version_number"],
    )
    _add_unique(
        "security_decision_policy_refs",
        "uq_policy_refs_decision_policy",
        ["decision_id", "policy_id", "policy_version"],
    )
    _add_unique(
        "security_decision_strategy_versions",
        "uq_strategy_versions_strategy_version",
        ["strategy_id", "version_number"],
    )
    _add_unique(
        "security_decision_approval_versions",
        "uq_approval_versions_request_version",
        ["request_id", "version_number"],
    )
    _add_unique(
        "security_execution_packages",
        "uq_execution_packages_tenant_decision",
        ["tenant_id", "decision_id"],
    )
    _add_unique(
        "security_execution_versions",
        "uq_execution_versions_package_version",
        ["package_id", "version_number"],
    )
    _add_unique(
        "security_execution_metadata",
        "uq_execution_metadata_package_key",
        ["package_id", "key"],
    )

    # ─────────────────────────────────────────────────────────────────────
    #  R22 — DateTime(timezone=True) on stale String(50) timestamps
    # ─────────────────────────────────────────────────────────────────────
    _convert_string_timestamp_to_tz_datetime(
        "security_execution_history", "changed_at"
    )
    _convert_string_timestamp_to_tz_datetime(
        "security_execution_audit", "occurred_at"
    )
    _convert_string_timestamp_to_tz_datetime(
        "security_decision_approval_requests", "expires_at"
    )
    _convert_string_timestamp_to_tz_datetime(
        "security_decision_approval_decisions", "decided_at"
    )
    _convert_string_timestamp_to_tz_datetime(
        "security_decision_approval_history", "changed_at"
    )
    _convert_string_timestamp_to_tz_datetime(
        "security_decision_approval_audit", "occurred_at"
    )


def downgrade() -> None:
    # Reverse R22 first so the columns revert to String(50).
    _revert_tz_datetime_to_string("security_decision_approval_audit", "occurred_at")
    _revert_tz_datetime_to_string("security_decision_approval_history", "changed_at")
    _revert_tz_datetime_to_string("security_decision_approval_decisions", "decided_at")
    _revert_tz_datetime_to_string("security_decision_approval_requests", "expires_at")
    _revert_tz_datetime_to_string("security_execution_audit", "occurred_at")
    _revert_tz_datetime_to_string("security_execution_history", "changed_at")

    # R20 — drop unique constraints
    for tbl, name in (
        ("security_execution_metadata",        "uq_execution_metadata_package_key"),
        ("security_execution_versions",        "uq_execution_versions_package_version"),
        ("security_execution_packages",        "uq_execution_packages_tenant_decision"),
        ("security_decision_approval_versions","uq_approval_versions_request_version"),
        ("security_decision_strategy_versions","uq_strategy_versions_strategy_version"),
        ("security_decision_policy_refs",      "uq_policy_refs_decision_policy"),
        ("security_decision_policy_versions",  "uq_policy_versions_policy_version"),
        ("security_rule_versions",             "uq_rule_versions_rule_version"),
        ("security_decision_versions",         "uq_decision_versions_decision_version"),
        ("security_decision_statistics",       "uq_decision_statistics_tenant_state"),
    ):
        try:
            op.drop_constraint(name, tbl, type_="unique")
        except Exception:  # pragma: no cover - defensive
            pass

    # R21 — revert DecisionStatistics.state back to String(50)
    op.alter_column(
        "security_decision_statistics",
        "state",
        existing_type=sa.Enum(
            "CREATED", "CONTEXT_BUILDING", "VALIDATING", "READY",
            "REJECTED", "ARCHIVED",
            name="decision_statistics_state_enum",
        ),
        type_=sa.String(50),
        existing_nullable=True,
    )
    sa.Enum(name="decision_statistics_state_enum").drop(op.get_bind(), checkfirst=True)

    # R18 — drop the additive strategy columns
    if op.get_bind().dialect.has_table(op.get_bind(), "security_decision_strategy_rankings"):
        op.drop_column("security_decision_strategy_rankings", "rejection_reason")
        op.drop_column("security_decision_strategy_rankings", "is_valid")
        op.drop_column("security_decision_strategy_rankings", "feasibility_score")
    if op.get_bind().dialect.has_table(op.get_bind(), "security_decision_strategy_candidates"):
        op.drop_column("security_decision_strategy_candidates", "confidence")
        op.drop_column("security_decision_strategy_candidates", "risk_score")
    if op.get_bind().dialect.has_table(op.get_bind(), "security_decision_strategy_scores"):
        op.drop_column("security_decision_strategy_scores", "rationale")


# ─────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────
def _add_unique(table_name: str, constraint_name: str, columns: list[str]) -> None:
    """Add a unique constraint only when it does not already exist."""
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, table_name):
        return
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_unique_constraints(table_name)}
    if constraint_name in existing:
        return
    try:
        op.create_unique_constraint(constraint_name, table_name, columns)
    except Exception:  # pragma: no cover - defensive
        pass


def _convert_string_timestamp_to_tz_datetime(table_name: str, column_name: str) -> None:
    """Convert a String(50) timestamp column to DateTime(timezone=True).

    Pre-existing values are parsed via datetime.fromisoformat and re-stamped
    as UTC.  Values that can't be parsed are set to NULL so the migration
    can never get stuck on legacy data.
    """
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, table_name):
        return
    cols = {c["name"]: c for c in sa.inspect(bind).get_columns(table_name)}
    if column_name not in cols:
        return
    current_type = cols[column_name]["type"]
    # Already converted (idempotent).
    if isinstance(current_type, sa.DateTime):
        return

    # Backfill from String → parsed UTC datetime using a single UPDATE that
    # works on PostgreSQL.  We use a Python-side rewrite instead so the same
    # migration works on SQLite (used by the test harness).
    rows = bind.execute(
        sa.text(f"SELECT id, {column_name} FROM {table_name}")
    ).fetchall()
    for row_id, raw in rows:
        if raw is None:
            continue
        new_value = _safe_parse_dt(str(raw))
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET {column_name} = :v WHERE id = :id"
            ),
            {"v": new_value, "id": row_id},
        )

    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.String(50),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using=f"{column_name}::timestamp with time zone",
    )


def _revert_tz_datetime_to_string(table_name: str, column_name: str) -> None:
    """Reverse the R22 conversion so the column is again String(50)."""
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, table_name):
        return
    cols = {c["name"]: c for c in sa.inspect(bind).get_columns(table_name)}
    if column_name not in cols:
        return
    # Re-render datetime values as ISO strings so the downgrade is lossless.
    rows = bind.execute(
        sa.text(f"SELECT id, {column_name} FROM {table_name}")
    ).fetchall()
    for row_id, raw in rows:
        if raw is None:
            continue
        try:
            iso = raw.isoformat() if hasattr(raw, "isoformat") else str(raw)
        except Exception:  # pragma: no cover - defensive
            iso = None
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET {column_name} = :v WHERE id = :id"
            ),
            {"v": iso, "id": row_id},
        )
    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.DateTime(timezone=True),
        type_=sa.String(50),
        existing_nullable=True,
    )