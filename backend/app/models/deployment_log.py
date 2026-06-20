"""
DeploymentLog — per-step audit log for the Deployment Engine pipeline (Epic 7).
"""
from sqlalchemy import String, ForeignKey, JSON, Float, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class DeploymentLog(BaseModel):
    __tablename__ = "deployment_logs"

    tenant_id:    Mapped[str]      = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    service_id:   Mapped[str]      = mapped_column(String(36), nullable=False, index=True)
    service_name: Mapped[str]      = mapped_column(String(255), nullable=False)
    step:         Mapped[str]      = mapped_column(String(100), nullable=False)    # validate|create_db|gen_repo|gen_ci|gen_helm|gitops|deploy|track
    status:       Mapped[str]      = mapped_column(String(50),  nullable=False)    # started|success|failed|skipped
    message:      Mapped[str|None] = mapped_column(Text)
    error:        Mapped[str|None] = mapped_column(Text)
    duration_ms:  Mapped[float|None] = mapped_column(Float)
    meta:         Mapped[dict]     = mapped_column(JSON, default=dict)
