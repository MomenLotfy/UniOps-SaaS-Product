from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, DateTime, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Threat(BaseModel):
    __tablename__ = "threats"

    tenant_id:       Mapped[str]           = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    scan_id:         Mapped[str | None]    = mapped_column(String(36), nullable=True, index=True)
    # ── Repo isolation: every finding must carry repo_id so queries can be
    #    scoped to a single repository. Nullable for backward-compat with
    #    threats created before this column was added (e.g. AWS Security Hub).
    repo_id:         Mapped[str | None]    = mapped_column(String(36), nullable=True, index=True)
    title:           Mapped[str]           = mapped_column(String(500), nullable=False)
    description:     Mapped[str | None]    = mapped_column(Text)
    severity:        Mapped[str]           = mapped_column(String(50), nullable=False)
    category:        Mapped[str]           = mapped_column(String(100))
    source:          Mapped[str]           = mapped_column(String(100))
    status:          Mapped[str]           = mapped_column(String(50), default="open")
    resource:        Mapped[str | None]    = mapped_column(String(500))
    namespace:       Mapped[str | None]    = mapped_column(String(255))
    ip:              Mapped[str | None]    = mapped_column(String(50))
    mitre_tactic:    Mapped[str | None]    = mapped_column(String(100))
    mitre_technique: Mapped[str | None]    = mapped_column(String(100))
    raw_data:        Mapped[dict]          = mapped_column(JSON, default=dict)
    detected_at:     Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    resolved_at:     Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

    # ── Deduplication support ──────────────────────────────────────────────
    # `fingerprint` is sha256(tenant_id|repo_id|scanner|rule_id|file_path|line)
    # — 64-char hex. Indexed uniquely with tenant_id so dedup is O(log n).
    fingerprint:     Mapped[str | None]    = mapped_column(String(64), nullable=True, index=True)
    occurrence_count:Mapped[int]           = mapped_column(Integer, default=1, nullable=False)
    first_seen_at:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    last_seen_at:    Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Composite index that powers `_upsert_threat` lookups
        Index("ix_threats_tenant_repo_fingerprint", "tenant_id", "repo_id", "fingerprint"),
    )
