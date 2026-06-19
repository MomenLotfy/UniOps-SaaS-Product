from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Cluster(BaseModel):
    __tablename__ = "clusters"

    tenant_id:            Mapped[str]            = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name:                 Mapped[str]            = mapped_column(String(255), nullable=False)
    provider:             Mapped[str]            = mapped_column(String(50),  nullable=False)   # eks | aks | gke | oke | on-prem
    region:               Mapped[str]            = mapped_column(String(100), nullable=False, default="")
    environment:          Mapped[str]            = mapped_column(String(50),  nullable=False, default="production")  # production | staging | dev
    api_server_url:       Mapped[str | None]     = mapped_column(Text)
    kubeconfig_encrypted: Mapped[str | None]     = mapped_column(Text)          # base64-encoded kubeconfig YAML
    status:               Mapped[str]            = mapped_column(String(50),  nullable=False, default="pending")  # connected | disconnected | error | pending
    k8s_version:          Mapped[str | None]     = mapped_column(String(50))
    node_count:           Mapped[int]            = mapped_column(Integer, default=0)
    pod_count:            Mapped[int]            = mapped_column(Integer, default=0)
    cpu_usage_pct:        Mapped[float]          = mapped_column(Float, default=0.0)
    memory_usage_pct:     Mapped[float]          = mapped_column(Float, default=0.0)
    last_health_check:    Mapped[datetime | None]= mapped_column(DateTime(timezone=True))
    error_message:        Mapped[str | None]     = mapped_column(Text)
    config:               Mapped[dict]           = mapped_column(JSON, default=dict)
