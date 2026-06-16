from sqlalchemy import BigInteger, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Pod(BaseModel):
    __tablename__ = "pods"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    integration_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("integrations.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    namespace: Mapped[str] = mapped_column(String(255), default="default")
    cluster: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    phase: Mapped[str | None] = mapped_column(String(50))
    node: Mapped[str | None] = mapped_column(String(255))
    cpu_request: Mapped[float | None] = mapped_column(Float)
    cpu_limit: Mapped[float | None] = mapped_column(Float)
    cpu_usage: Mapped[float | None] = mapped_column(Float)
    memory_request: Mapped[int | None] = mapped_column(BigInteger)
    memory_limit: Mapped[int | None] = mapped_column(BigInteger)
    memory_usage: Mapped[int | None] = mapped_column(BigInteger)
    restart_count: Mapped[int] = mapped_column(Integer, default=0)
    containers: Mapped[list] = mapped_column(JSON, default=list)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
