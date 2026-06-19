from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ClusterCreate(BaseModel):
    name:           str = Field(..., min_length=1, max_length=255)
    provider:       str = Field(..., pattern="^(eks|aks|gke|oke|on-prem)$")
    region:         str = Field(default="")
    environment:    str = Field(default="production", pattern="^(production|staging|dev|sandbox)$")
    api_server_url: Optional[str] = None
    kubeconfig:     Optional[str] = None   # raw kubeconfig YAML (stored encoded)


class ClusterUpdate(BaseModel):
    name:           Optional[str] = None
    region:         Optional[str] = None
    environment:    Optional[str] = None
    api_server_url: Optional[str] = None
    kubeconfig:     Optional[str] = None


class ClusterResponse(BaseModel):
    id:               str
    name:             str
    provider:         str
    region:           str
    environment:      str
    api_server_url:   Optional[str]
    status:           str
    k8s_version:      Optional[str]
    node_count:       int
    pod_count:        int
    cpu_usage_pct:    float
    memory_usage_pct: float
    last_health_check:Optional[datetime]
    error_message:    Optional[str]
    created_at:       datetime

    model_config = {"from_attributes": True}


# ── Cluster detail resources ────────────────────────────────────────────────

class NodeCondition(BaseModel):
    type:   str
    status: str


class ClusterNode(BaseModel):
    name:             str
    status:           str           # Ready | NotReady | Unknown
    roles:            List[str]
    cpu_capacity:     Optional[str]
    memory_capacity:  Optional[str]
    cpu_allocatable:  Optional[str]
    memory_allocatable: Optional[str]
    os_image:         Optional[str]
    kubelet_version:  Optional[str]
    conditions:       List[NodeCondition] = []
    age:              Optional[str]


class ClusterNamespace(BaseModel):
    name:   str
    status: str
    age:    Optional[str]
    labels: dict = {}


class ClusterService(BaseModel):
    name:        str
    namespace:   str
    type:        str
    cluster_ip:  Optional[str]
    external_ip: Optional[str]
    ports:       List[str]
    age:         Optional[str]


class ClusterIngress(BaseModel):
    name:      str
    namespace: str
    class_:    Optional[str]
    hosts:     List[str]
    paths:     List[str]
    tls:       bool
    age:       Optional[str]


class ClusterDeployment(BaseModel):
    name:              str
    namespace:         str
    replicas:          int
    ready_replicas:    int
    available_replicas:int
    image:             Optional[str]
    age:               Optional[str]
    status:            str   # Healthy | Degraded | Progressing
