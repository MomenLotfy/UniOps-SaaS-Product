from __future__ import annotations
"""Clusters API — Multi-Cluster Kubernetes Management."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.cluster import ClusterCreate, ClusterUpdate, ClusterResponse
from app.schemas.common import APIResponse
from app.services.cluster_service import ClusterService as ClusterSvc

router = APIRouter()


@router.get("", response_model=APIResponse[list[ClusterResponse]])
async def list_clusters(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = ClusterSvc(db)
    clusters = await svc.list_clusters(tenant_id)
    return APIResponse(data=clusters)


@router.post("", response_model=APIResponse[ClusterResponse], status_code=201)
async def add_cluster(
    body: ClusterCreate,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    svc = ClusterSvc(db)
    cluster = await svc.add_cluster(tenant_id, body)
    return APIResponse(data=cluster, message="Cluster added successfully")


@router.get("/{cluster_id}", response_model=APIResponse[ClusterResponse])
async def get_cluster(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    svc = ClusterSvc(db)
    cluster = await svc.get_cluster(tenant_id, cluster_id)
    return APIResponse(data=ClusterResponse.model_validate(cluster))


@router.patch("/{cluster_id}", response_model=APIResponse[ClusterResponse])
async def update_cluster(
    cluster_id: str, body: ClusterUpdate,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    svc = ClusterSvc(db)
    cluster = await svc.update_cluster(tenant_id, cluster_id, body)
    return APIResponse(data=cluster, message="Cluster updated")


@router.delete("/{cluster_id}", status_code=204)
async def delete_cluster(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    svc = ClusterSvc(db)
    await svc.delete_cluster(tenant_id, cluster_id)


@router.post("/{cluster_id}/test")
async def test_connection(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    svc = ClusterSvc(db)
    result = await svc.test_connection(tenant_id, cluster_id)
    return APIResponse(data=result)


@router.get("/{cluster_id}/nodes")
async def get_nodes(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    svc = ClusterSvc(db)
    nodes = await svc.get_nodes(tenant_id, cluster_id)
    return APIResponse(data=nodes)


@router.get("/{cluster_id}/namespaces")
async def get_namespaces(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    svc = ClusterSvc(db)
    nss = await svc.get_namespaces(tenant_id, cluster_id)
    return APIResponse(data=nss)


@router.get("/{cluster_id}/deployments")
async def get_deployments(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    svc = ClusterSvc(db)
    deps = await svc.get_deployments(tenant_id, cluster_id, namespace)
    return APIResponse(data=deps)


@router.get("/{cluster_id}/services")
async def get_services(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    svc = ClusterSvc(db)
    svcs = await svc.get_services(tenant_id, cluster_id, namespace)
    return APIResponse(data=svcs)


@router.get("/{cluster_id}/ingresses")
async def get_ingresses(
    cluster_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    svc = ClusterSvc(db)
    ings = await svc.get_ingresses(tenant_id, cluster_id, namespace)
    return APIResponse(data=ings)
