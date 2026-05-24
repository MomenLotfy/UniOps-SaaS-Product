from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Scan(BaseModel):
    """
    Represents a single security scan run triggered by a user.
    One scan → runs multiple scanner engines → produces Threats + Vulnerabilities.
    """
    __tablename__ = "scans"

    tenant_id:      Mapped[str]         = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    repo_id:        Mapped[str]         = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    triggered_by:   Mapped[str | None]  = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    # Git context
    branch:         Mapped[str]         = mapped_column(String(255), default="main")
    commit_sha:     Mapped[str | None]  = mapped_column(String(40))

    # Status lifecycle: queued → cloning → scanning → analyzing → completed | failed
    status:         Mapped[str]         = mapped_column(String(50), default="queued")
    error_message:  Mapped[str | None]  = mapped_column(Text)

    # Timing
    started_at:     Mapped[datetime | None] = mapped_column()
    completed_at:   Mapped[datetime | None] = mapped_column()
    duration_secs:  Mapped[int | None]  = mapped_column(Integer)

    # Which scanners ran and their individual statuses
    # e.g. {"sast": "completed", "deps": "completed", "secrets": "failed", "container": "skipped"}
    scanners_run:   Mapped[dict]        = mapped_column(JSON, default=dict)

    # Aggregated result counts (fast summary without joining)
    critical_count: Mapped[int]         = mapped_column(Integer, default=0)
    high_count:     Mapped[int]         = mapped_column(Integer, default=0)
    medium_count:   Mapped[int]         = mapped_column(Integer, default=0)
    low_count:      Mapped[int]         = mapped_column(Integer, default=0)
    secret_count:   Mapped[int]         = mapped_column(Integer, default=0)
    misconfig_count:Mapped[int]         = mapped_column(Integer, default=0)

    # Computed security score (0–100)
    security_score: Mapped[float | None] = mapped_column(Float)

    # AI-generated summary + suggestions
    ai_summary:     Mapped[str | None]  = mapped_column(Text)
    ai_suggestions: Mapped[list]        = mapped_column(JSON, default=list)

    # Raw aggregated output from all scanners (for debugging / re-processing)
    raw_results:    Mapped[dict]        = mapped_column(JSON, default=dict)


class Repository(BaseModel):
    """
    A Git repository connected to UniOps for scanning.
    """
    __tablename__ = "repositories"

    tenant_id:          Mapped[str]         = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    integration_id:     Mapped[str | None]  = mapped_column(String(36), ForeignKey("integrations.id"), nullable=True)

    # Provider info
    provider:           Mapped[str]         = mapped_column(String(50))   # github | gitlab
    external_id:        Mapped[str]         = mapped_column(String(255))  # provider's repo ID or full_name
    full_name:          Mapped[str]         = mapped_column(String(500))  # owner/repo
    name:               Mapped[str]         = mapped_column(String(255))
    clone_url:          Mapped[str | None]  = mapped_column(Text)
    default_branch:     Mapped[str]         = mapped_column(String(255), default="main")
    is_private:         Mapped[bool]        = mapped_column(Boolean, default=True)
    language:           Mapped[str | None]  = mapped_column(String(100))
    has_dockerfile:     Mapped[bool]        = mapped_column(Boolean, default=False)
    has_cicd:           Mapped[bool]        = mapped_column(Boolean, default=False)

    # Last scan reference
    last_scan_at:       Mapped[datetime | None] = mapped_column()
    last_scan_score:    Mapped[float | None]    = mapped_column(Float)

    def to_dict(self) -> dict:
        result = {}
        for c in self.__table__.columns:
            val = getattr(self, c.name)
            # Serialize datetime → ISO string so JSON serialization never fails
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            result[c.name] = val
        return result
