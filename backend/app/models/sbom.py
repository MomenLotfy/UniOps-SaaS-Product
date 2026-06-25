from sqlalchemy import String, ForeignKey, JSON, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SBOM(BaseModel):
    __tablename__ = "sboms"

    tenant_id:       Mapped[str]        = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    repo_id:         Mapped[str]        = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id:         Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    format:          Mapped[str]        = mapped_column(String(50), nullable=False)  # cyclonedx, spdx
    component_count: Mapped[int]        = mapped_column(Integer, default=0)
    content:         Mapped[str | None] = mapped_column(Text, nullable=True)
    meta:            Mapped[dict]       = mapped_column(JSON, default=dict)
