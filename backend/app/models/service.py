"""
CatalogService — persisted service definitions for the Self-Service Catalog (Epic 6/7).
"""
from sqlalchemy import String, ForeignKey, JSON, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CatalogService(BaseModel):
    __tablename__ = "catalog_services"

    tenant_id:       Mapped[str]      = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name:            Mapped[str]      = mapped_column(String(255), nullable=False)
    type:            Mapped[str]      = mapped_column(String(50),  nullable=False)   # Microservice|Database|Worker|Queue|Gateway
    tech_stack:      Mapped[str]      = mapped_column(String(100), nullable=False, default="Other")
    status:          Mapped[str]      = mapped_column(String(50),  nullable=False, default="Pending")  # Pending|Creating|Building|Deploying|Running|Failed|Stopped
    owner:           Mapped[str|None] = mapped_column(String(255))
    description:     Mapped[str|None] = mapped_column(Text)
    repo_url:        Mapped[str|None] = mapped_column(Text)
    git_provider:    Mapped[str]      = mapped_column(String(50),  nullable=False, default="github")   # github|gitlab
    cluster:         Mapped[str]      = mapped_column(String(255), nullable=False, default="")
    namespace:       Mapped[str]      = mapped_column(String(255), nullable=False, default="default")
    replicas:        Mapped[int]      = mapped_column(Integer,     nullable=False, default=1)
    gitops_app_name: Mapped[str|None] = mapped_column(String(255))
    helm_chart_path: Mapped[str|None] = mapped_column(Text)
    last_deployment: Mapped[str|None] = mapped_column(String(64))  # ISO string
    tags:            Mapped[list]     = mapped_column(JSON, default=list)
    meta:            Mapped[dict]     = mapped_column(JSON, default=dict)  # extra metadata / feature flags
