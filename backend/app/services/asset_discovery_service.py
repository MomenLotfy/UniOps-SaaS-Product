from __future__ import annotations
"""
Asset Discovery Service
=======================
Discovers and synchronises assets from all connected real integrations:
  • GitHub  → github_repo
  • GitLab  → gitlab_repo
  • AWS     → aws_ec2, aws_s3, aws_iam_user, aws_iam_role, aws_rds
  • K8s     → k8s_cluster, k8s_namespace, k8s_pod
  • Docker  → docker_image (derived from existing scan raw_results)

Design:
  - Each provider method is independent and fail-safe.
  - Upsert key: (tenant_id, source, external_id) — fully idempotent.
  - Risk level is derived from open finding counts.
  - Relationships are inferred after all assets are upserted.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetRelationship
from app.models.integration import Integration
from app.models.scan import Repository, Scan
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.services.base import BaseService
from app.utils.encryption import decrypt
from app.utils.logger import logger


def _decrypt_creds(raw: dict) -> dict:
    """Best-effort decrypt of stored integration credentials."""
    out = {}
    for k, v in (raw or {}).items():
        try:
            out[k] = decrypt(v)
        except Exception:
            out[k] = v
    return out


_RISK_ORDER = ["critical", "high", "medium", "low", "none"]


def _risk_from_findings(critical: int, high: int, medium: int, low: int) -> str:
    if critical > 0:
        return "critical"
    if high > 0:
        return "high"
    if medium > 0:
        return "medium"
    if low > 0:
        return "low"
    return "none"


class AssetDiscoveryService(BaseService):

    NOW = staticmethod(lambda: datetime.now(timezone.utc))

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry points
    # ─────────────────────────────────────────────────────────────────────────

    async def sync_all(self, tenant_id: str) -> dict:
        """
        Sync assets from every connected integration for this tenant.
        Each source is wrapped in its own try/except so one failure
        doesn't abort the entire sync.
        """
        integrations = await self._load_integrations(tenant_id)
        totals: dict[str, int] = {}
        errors: list[str] = []

        for intg in integrations:
            creds = _decrypt_creds(intg.credentials or {})
            config = {**creds, **(intg.config or {})}
            source = intg.type

            try:
                if source == "github":
                    count = await self._sync_github(tenant_id, intg, config)
                    totals["github_repo"] = totals.get("github_repo", 0) + count

                elif source == "gitlab":
                    count = await self._sync_gitlab(tenant_id, intg, config)
                    totals["gitlab_repo"] = totals.get("gitlab_repo", 0) + count

                elif source == "aws":
                    aws_counts = await self._sync_aws(tenant_id, intg, config)
                    for k, v in aws_counts.items():
                        totals[k] = totals.get(k, 0) + v

                elif source == "kubernetes":
                    k8s_counts = await self._sync_kubernetes(tenant_id, intg, config)
                    for k, v in k8s_counts.items():
                        totals[k] = totals.get(k, 0) + v

            except Exception as exc:
                msg = f"{source}: {str(exc)[:200]}"
                errors.append(msg)
                logger.warning(f"[asset_sync] source={source} tenant={tenant_id[:8]} error={msg}")

        # Docker images from existing scan results (no integration needed)
        try:
            docker_count = await self._sync_docker_images(tenant_id)
            totals["docker_image"] = docker_count
        except Exception as exc:
            errors.append(f"docker: {str(exc)[:200]}")

        # Recompute risk levels from actual finding counts
        await self._recompute_risk_levels(tenant_id)

        # Infer relationships
        await self._build_relationships(tenant_id)

        return {"synced": totals, "errors": errors}

    async def sync_source(self, tenant_id: str, source: str) -> dict:
        """Sync assets from a single named source type."""
        integrations = await self._load_integrations(tenant_id, source_type=source)
        totals: dict[str, int] = {}
        errors: list[str] = []

        for intg in integrations:
            creds = _decrypt_creds(intg.credentials or {})
            config = {**creds, **(intg.config or {})}
            try:
                if source == "github":
                    n = await self._sync_github(tenant_id, intg, config)
                    totals["github_repo"] = totals.get("github_repo", 0) + n
                elif source == "gitlab":
                    n = await self._sync_gitlab(tenant_id, intg, config)
                    totals["gitlab_repo"] = totals.get("gitlab_repo", 0) + n
                elif source == "aws":
                    aws_counts = await self._sync_aws(tenant_id, intg, config)
                    for k, v in aws_counts.items():
                        totals[k] = totals.get(k, 0) + v
                elif source == "kubernetes":
                    k8s_counts = await self._sync_kubernetes(tenant_id, intg, config)
                    for k, v in k8s_counts.items():
                        totals[k] = totals.get(k, 0) + v
            except Exception as exc:
                errors.append(str(exc)[:200])

        if source == "docker":
            try:
                n = await self._sync_docker_images(tenant_id)
                totals["docker_image"] = n
            except Exception as exc:
                errors.append(str(exc)[:200])

        await self._recompute_risk_levels(tenant_id)
        await self._build_relationships(tenant_id)
        return {"synced": totals, "errors": errors}

    # ─────────────────────────────────────────────────────────────────────────
    # Per-source sync methods
    # ─────────────────────────────────────────────────────────────────────────

    async def _sync_github(self, tenant_id: str, intg: Integration, config: dict) -> int:
        from app.integrations.github.client import GitHubClient
        client = GitHubClient(config)
        repos = await client.list_repos(per_page=100)

        count = 0
        for repo in repos:
            external_id = str(repo.get("id", repo.get("full_name", "")))
            env = _infer_github_env(repo)
            await self._upsert_asset(
                tenant_id=tenant_id,
                integration_id=intg.id,
                asset_type="github_repo",
                source="github",
                external_id=external_id,
                name=repo.get("full_name") or repo.get("name", ""),
                environment=env,
                owner=repo.get("owner", {}).get("login"),
                description=repo.get("description"),
                url=repo.get("html_url"),
                tags={
                    "language": repo.get("language"),
                    "private": repo.get("private"),
                    "default_branch": repo.get("default_branch", "main"),
                    "archived": repo.get("archived", False),
                    "fork": repo.get("fork", False),
                    "stars": repo.get("stargazers_count", 0),
                },
                meta={"topics": repo.get("topics", [])},
                last_scanned_at=None,
            )
            count += 1
        logger.info(f"[asset_sync:github] tenant={tenant_id[:8]} synced={count} repos")
        return count

    async def _sync_gitlab(self, tenant_id: str, intg: Integration, config: dict) -> int:
        from app.integrations.gitlab.client import GitLabClient
        client = GitLabClient(config)
        projects = await client.list_projects(per_page=100)

        count = 0
        for proj in projects:
            external_id = str(proj.get("id", proj.get("path_with_namespace", "")))
            await self._upsert_asset(
                tenant_id=tenant_id,
                integration_id=intg.id,
                asset_type="gitlab_repo",
                source="gitlab",
                external_id=external_id,
                name=proj.get("path_with_namespace") or proj.get("name", ""),
                environment="unknown",
                owner=proj.get("namespace", {}).get("name"),
                description=proj.get("description"),
                url=proj.get("web_url"),
                tags={
                    "visibility": proj.get("visibility", "private"),
                    "default_branch": proj.get("default_branch", "main"),
                    "archived": proj.get("archived", False),
                },
                meta={},
                last_scanned_at=None,
            )
            count += 1
        logger.info(f"[asset_sync:gitlab] tenant={tenant_id[:8]} synced={count} projects")
        return count

    async def _sync_aws(self, tenant_id: str, intg: Integration, config: dict) -> dict[str, int]:
        """Discover EC2, S3, IAM users/roles, RDS via boto3 in a thread pool."""
        from app.integrations.aws.client import AWSClient
        aws_client = AWSClient(config)
        session = aws_client.get_session()
        region = config.get("region", "us-east-1")
        account_id = config.get("account_id")
        counts: dict[str, int] = {}

        # All boto3 calls are sync — run in thread pool
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, lambda: self._aws_ec2(tenant_id, intg.id, session, region, account_id)),
            loop.run_in_executor(None, lambda: self._aws_s3(tenant_id, intg.id, session, account_id)),
            loop.run_in_executor(None, lambda: self._aws_iam(tenant_id, intg.id, session, account_id)),
            loop.run_in_executor(None, lambda: self._aws_rds(tenant_id, intg.id, session, region, account_id)),
        ]

        ec2_data, s3_data, iam_data, rds_data = await asyncio.gather(*tasks, return_exceptions=True)

        for label, data in [("aws_ec2", ec2_data), ("aws_s3", s3_data), ("aws_rds", rds_data)]:
            if isinstance(data, Exception):
                logger.warning(f"[asset_sync:aws] {label} failed: {data}")
                continue
            for asset in data:
                await self._upsert_asset(**asset)
            counts[label] = len(data) if not isinstance(data, Exception) else 0

        if not isinstance(iam_data, Exception):
            for asset in iam_data:
                await self._upsert_asset(**asset)
            counts["aws_iam_user"] = sum(1 for a in iam_data if a["asset_type"] == "aws_iam_user")
            counts["aws_iam_role"] = sum(1 for a in iam_data if a["asset_type"] == "aws_iam_role")

        return counts

    def _aws_ec2(self, tenant_id: str, intg_id: str, session, region: str, account_id: str | None) -> list[dict]:
        assets = []
        try:
            ec2 = session.client("ec2", region_name=region)
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for inst in reservation.get("Instances", []):
                        instance_id = inst.get("InstanceId", "")
                        name = next(
                            (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                            instance_id,
                        )
                        env = next(
                            (t["Value"] for t in inst.get("Tags", []) if t["Key"].lower() in ("env", "environment")),
                            "unknown",
                        ).lower()
                        tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                        assets.append(dict(
                            tenant_id=tenant_id, integration_id=intg_id,
                            asset_type="aws_ec2", source="aws",
                            external_id=instance_id, name=name,
                            environment=env, region=region,
                            account_id=account_id,
                            owner=tags.get("Owner"),
                            team=tags.get("Team"),
                            description=f"{inst.get('InstanceType','?')} · {inst.get('State',{}).get('Name','unknown')}",
                            url=None, tags=tags,
                            meta={
                                "instance_type": inst.get("InstanceType"),
                                "state": inst.get("State", {}).get("Name"),
                                "platform": inst.get("Platform", "linux"),
                                "private_ip": inst.get("PrivateIpAddress"),
                                "public_ip": inst.get("PublicIpAddress"),
                                "vpc_id": inst.get("VpcId"),
                                "subnet_id": inst.get("SubnetId"),
                                "image_id": inst.get("ImageId"),
                                "key_name": inst.get("KeyName"),
                                "launch_time": str(inst.get("LaunchTime", "")),
                            },
                            last_scanned_at=None,
                        ))
        except Exception as exc:
            logger.warning(f"[aws_ec2_sync] region={region}: {exc}")
        return assets

    def _aws_s3(self, tenant_id: str, intg_id: str, session, account_id: str | None) -> list[dict]:
        assets = []
        try:
            s3 = session.client("s3")
            response = s3.list_buckets()
            for bucket in response.get("Buckets", []):
                bname = bucket.get("Name", "")
                created = bucket.get("CreationDate")

                # Try to get bucket location
                try:
                    loc = s3.get_bucket_location(Bucket=bname)
                    region = loc.get("LocationConstraint") or "us-east-1"
                except Exception:
                    region = "unknown"

                # Try tagging
                try:
                    tag_resp = s3.get_bucket_tagging(Bucket=bname)
                    tags = {t["Key"]: t["Value"] for t in tag_resp.get("TagSet", [])}
                except Exception:
                    tags = {}

                env = next(
                    (v for k, v in tags.items() if k.lower() in ("env", "environment")),
                    "unknown",
                ).lower()

                assets.append(dict(
                    tenant_id=tenant_id, integration_id=intg_id,
                    asset_type="aws_s3", source="aws",
                    external_id=bname, name=bname,
                    environment=env, region=region,
                    account_id=account_id,
                    owner=tags.get("Owner"),
                    team=tags.get("Team"),
                    description=f"S3 Bucket · created {created.date() if created else 'unknown'}",
                    url=f"https://s3.console.aws.amazon.com/s3/buckets/{bname}",
                    tags=tags, meta={"creation_date": str(created or "")},
                    last_scanned_at=None,
                ))
        except Exception as exc:
            logger.warning(f"[aws_s3_sync]: {exc}")
        return assets

    def _aws_iam(self, tenant_id: str, intg_id: str, session, account_id: str | None) -> list[dict]:
        assets = []
        try:
            iam = session.client("iam")

            # Users
            paginator = iam.get_paginator("list_users")
            for page in paginator.paginate():
                for user in page.get("Users", []):
                    username = user.get("UserName", "")
                    assets.append(dict(
                        tenant_id=tenant_id, integration_id=intg_id,
                        asset_type="aws_iam_user", source="aws",
                        external_id=user.get("UserId", username),
                        name=username, environment="production",
                        account_id=account_id,
                        owner=None, team=None,
                        description=f"IAM User · {user.get('Path', '/')}",
                        url=f"https://console.aws.amazon.com/iam/home#/users/{username}",
                        tags={}, meta={
                            "arn": user.get("Arn"),
                            "path": user.get("Path"),
                            "create_date": str(user.get("CreateDate", "")),
                            "password_last_used": str(user.get("PasswordLastUsed", "")),
                        },
                        last_scanned_at=None,
                    ))

            # Roles
            paginator = iam.get_paginator("list_roles")
            for page in paginator.paginate():
                for role in page.get("Roles", []):
                    rname = role.get("RoleName", "")
                    assets.append(dict(
                        tenant_id=tenant_id, integration_id=intg_id,
                        asset_type="aws_iam_role", source="aws",
                        external_id=role.get("RoleId", rname),
                        name=rname, environment="production",
                        account_id=account_id,
                        owner=None, team=None,
                        description=f"IAM Role · {role.get('Description', '')}",
                        url=f"https://console.aws.amazon.com/iam/home#/roles/{rname}",
                        tags={}, meta={
                            "arn": role.get("Arn"),
                            "path": role.get("Path"),
                            "create_date": str(role.get("CreateDate", "")),
                        },
                        last_scanned_at=None,
                    ))
        except Exception as exc:
            logger.warning(f"[aws_iam_sync]: {exc}")
        return assets

    def _aws_rds(self, tenant_id: str, intg_id: str, session, region: str, account_id: str | None) -> list[dict]:
        assets = []
        try:
            rds = session.client("rds", region_name=region)
            paginator = rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db in page.get("DBInstances", []):
                    db_id = db.get("DBInstanceIdentifier", "")
                    tags_list = db.get("TagList", [])
                    tags = {t["Key"]: t["Value"] for t in tags_list}
                    env = next(
                        (v for k, v in tags.items() if k.lower() in ("env", "environment")),
                        "unknown",
                    ).lower()
                    assets.append(dict(
                        tenant_id=tenant_id, integration_id=intg_id,
                        asset_type="aws_rds", source="aws",
                        external_id=db.get("DbiResourceId", db_id),
                        name=db_id, environment=env,
                        region=region, account_id=account_id,
                        owner=tags.get("Owner"), team=tags.get("Team"),
                        description=(
                            f"{db.get('Engine','?')} {db.get('EngineVersion','?')} · "
                            f"{db.get('DBInstanceClass','?')} · {db.get('DBInstanceStatus','?')}"
                        ),
                        url=None, tags=tags,
                        meta={
                            "engine": db.get("Engine"),
                            "engine_version": db.get("EngineVersion"),
                            "instance_class": db.get("DBInstanceClass"),
                            "status": db.get("DBInstanceStatus"),
                            "multi_az": db.get("MultiAZ", False),
                            "storage_encrypted": db.get("StorageEncrypted", False),
                            "endpoint": db.get("Endpoint", {}).get("Address"),
                        },
                        is_critical=True,
                        last_scanned_at=None,
                    ))
        except Exception as exc:
            logger.warning(f"[aws_rds_sync] region={region}: {exc}")
        return assets

    async def _sync_kubernetes(self, tenant_id: str, intg: Integration, config: dict) -> dict[str, int]:
        from app.integrations.kubernetes.client import KubernetesClient
        client = KubernetesClient(config)
        counts: dict[str, int] = {}

        cluster_name = config.get("cluster_name") or intg.name or "kubernetes"
        cluster_external_id = f"k8s-cluster-{intg.id}"

        # Upsert the cluster itself
        cluster_asset = await self._upsert_asset(
            tenant_id=tenant_id, integration_id=intg.id,
            asset_type="k8s_cluster", source="kubernetes",
            external_id=cluster_external_id,
            name=cluster_name, environment="production",
            description=f"Kubernetes cluster: {cluster_name}",
            url=config.get("server"),
            tags={}, meta={"server": config.get("server", "")},
            last_scanned_at=None,
        )
        counts["k8s_cluster"] = 1

        # Namespaces
        try:
            namespaces = await client.get_namespaces()
            for ns in namespaces:
                await self._upsert_asset(
                    tenant_id=tenant_id, integration_id=intg.id,
                    asset_type="k8s_namespace", source="kubernetes",
                    external_id=f"{cluster_external_id}/{ns}",
                    name=ns, environment=_infer_k8s_env(ns),
                    cluster=cluster_name,
                    description=f"Namespace {ns} in {cluster_name}",
                    url=None, tags={}, meta={"cluster": cluster_name},
                    last_scanned_at=None,
                )
            counts["k8s_namespace"] = len(namespaces)
        except Exception as exc:
            logger.warning(f"[asset_sync:k8s_ns] cluster={cluster_name}: {exc}")

        # Pods
        try:
            pods = await client.list_all_pods()
            for pod in pods:
                pod_name = pod.get("name", "")
                ns = pod.get("namespace", "default")
                await self._upsert_asset(
                    tenant_id=tenant_id, integration_id=intg.id,
                    asset_type="k8s_pod", source="kubernetes",
                    external_id=f"{cluster_external_id}/{ns}/{pod_name}",
                    name=pod_name, environment=_infer_k8s_env(ns),
                    cluster=cluster_name, namespace=ns,
                    description=f"Pod in {ns}",
                    url=None,
                    tags={"phase": pod.get("phase", "unknown")},
                    meta={
                        "namespace": ns,
                        "cluster": cluster_name,
                        "phase": pod.get("phase"),
                        "node": pod.get("node"),
                        "ready": pod.get("ready"),
                        "restarts": pod.get("restart_count", 0),
                        "images": pod.get("images", []),
                    },
                    last_scanned_at=None,
                )
            counts["k8s_pod"] = len(pods)
        except Exception as exc:
            logger.warning(f"[asset_sync:k8s_pods] cluster={cluster_name}: {exc}")

        return counts

    async def _sync_docker_images(self, tenant_id: str) -> int:
        """Extract docker images referenced in existing scan results."""
        result = await self.db.execute(
            select(Scan).where(
                Scan.tenant_id == tenant_id,
                Scan.status == "completed",
            ).order_by(Scan.completed_at.desc()).limit(200)
        )
        scans = result.scalars().all()

        seen: set[str] = set()
        count = 0
        for scan in scans:
            raw = scan.raw_results or {}
            images: list[str] = []

            # Extract from container scanner results
            container_results = raw.get("container", {})
            if isinstance(container_results, dict):
                for target_key in ("results", "targets", "vulnerabilities"):
                    for item in container_results.get(target_key, []):
                        if isinstance(item, dict):
                            img = item.get("Target") or item.get("image") or item.get("artifact", {}).get("name")
                            if img:
                                images.append(img)

            for image in images:
                image = image.strip()
                if not image or image in seen:
                    continue
                seen.add(image)

                tag = "latest"
                if ":" in image:
                    image_name, tag = image.rsplit(":", 1)
                else:
                    image_name = image

                await self._upsert_asset(
                    tenant_id=tenant_id, integration_id=None,
                    asset_type="docker_image", source="docker",
                    external_id=image,
                    name=image, environment="unknown",
                    description=f"Docker image found in scan",
                    url=None,
                    tags={"tag": tag, "image_name": image_name},
                    meta={"scan_id": scan.id, "repo_id": scan.repo_id},
                    last_scanned_at=scan.completed_at,
                )
                count += 1

        return count

    # ─────────────────────────────────────────────────────────────────────────
    # Upsert helper
    # ─────────────────────────────────────────────────────────────────────────

    async def _upsert_asset(
        self, *, tenant_id: str, integration_id: str | None,
        asset_type: str, source: str, external_id: str,
        name: str, environment: str = "unknown",
        owner: str | None = None, team: str | None = None,
        description: str | None = None, url: str | None = None,
        region: str | None = None, account_id: str | None = None,
        namespace: str | None = None, cluster: str | None = None,
        tags: dict | None = None, meta: dict | None = None,
        last_scanned_at: datetime | None = None,
        is_critical: bool = False,
    ) -> Asset:
        """
        SELECT-or-INSERT asset using (tenant_id, source, external_id) as key.
        Updates mutable fields on every sync.
        """
        now = self.NOW()
        result = await self.db.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.source == source,
                Asset.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = name
            existing.type = asset_type
            existing.environment = environment or existing.environment
            existing.owner = owner or existing.owner
            existing.team = team or existing.team
            existing.description = description or existing.description
            existing.url = url or existing.url
            existing.region = region or existing.region
            existing.account_id = account_id or existing.account_id
            existing.namespace = namespace or existing.namespace
            existing.cluster = cluster or existing.cluster
            existing.tags = tags or existing.tags
            existing.meta = meta or existing.meta
            existing.last_synced_at = now
            if last_scanned_at:
                existing.last_scanned_at = last_scanned_at
            if is_critical:
                existing.is_critical = True
            return existing
        else:
            asset = Asset(
                tenant_id=tenant_id,
                integration_id=integration_id,
                name=name,
                type=asset_type,
                source=source,
                external_id=external_id,
                environment=environment,
                status="active",
                risk_level="none",
                owner=owner,
                team=team,
                description=description,
                url=url,
                region=region,
                account_id=account_id,
                namespace=namespace,
                cluster=cluster,
                tags=tags or {},
                meta=meta or {},
                is_critical=is_critical,
                open_findings=0,
                last_scanned_at=last_scanned_at,
                last_synced_at=now,
            )
            self.db.add(asset)
            await self.db.flush()
            return asset

    # ─────────────────────────────────────────────────────────────────────────
    # Risk computation
    # ─────────────────────────────────────────────────────────────────────────

    async def _recompute_risk_levels(self, tenant_id: str) -> None:
        """
        For GitHub/GitLab repos that have been scanned:
        derive risk level from existing Threat + Vulnerability counts.
        """
        repos_result = await self.db.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.type.in_(["github_repo", "gitlab_repo"]),
            )
        )
        repos = repos_result.scalars().all()

        # Build repo name → asset mapping
        name_map = {a.name: a for a in repos}
        url_map: dict[str, Asset] = {}
        for a in repos:
            if a.url:
                url_map[a.url.rstrip("/")] = a

        # Check scan results (threats + vulns)
        repo_db_result = await self.db.execute(
            select(Repository).where(Repository.tenant_id == tenant_id)
        )
        repo_db_rows = repo_db_result.scalars().all()

        for repo_row in repo_db_rows:
            asset = name_map.get(repo_row.full_name) or url_map.get(repo_row.clone_url or "")
            if not asset:
                continue

            t_result = await self.db.execute(
                select(
                    func.sum(Threat.severity == "critical").label("c"),
                    func.sum(Threat.severity == "high").label("h"),
                    func.sum(Threat.severity == "medium").label("m"),
                    func.sum(Threat.severity == "low").label("l"),
                    func.count().label("total"),
                ).where(
                    Threat.tenant_id == tenant_id,
                    Threat.repo_id == repo_row.id,
                    Threat.status.notin_(["resolved", "suppressed"]),
                )
            )
            t = t_result.first()

            v_result = await self.db.execute(
                select(
                    func.sum(Vulnerability.severity == "critical").label("c"),
                    func.sum(Vulnerability.severity == "high").label("h"),
                    func.sum(Vulnerability.severity == "medium").label("m"),
                    func.sum(Vulnerability.severity == "low").label("l"),
                    func.count().label("total"),
                ).where(
                    Vulnerability.tenant_id == tenant_id,
                    Vulnerability.repo_id == repo_row.id,
                    Vulnerability.status.notin_(["resolved", "suppressed", "patched"]),
                )
            )
            v = v_result.first()

            tc = int(t.c or 0)
            th = int(t.h or 0)
            tm = int(t.m or 0)
            tl = int(t.l or 0)
            vc = int(v.c or 0)
            vh = int(v.h or 0)
            vm = int(v.m or 0)
            vl = int(v.l or 0)

            asset.open_findings = int((t.total or 0) + (v.total or 0))
            asset.risk_level = _risk_from_findings(tc + vc, th + vh, tm + vm, tl + vl)

            if repo_row.last_scan_at:
                asset.last_scanned_at = repo_row.last_scan_at

    # ─────────────────────────────────────────────────────────────────────────
    # Relationship inference
    # ─────────────────────────────────────────────────────────────────────────

    async def _build_relationships(self, tenant_id: str) -> None:
        """Infer and upsert asset relationships."""

        # k8s_pod → runs_in → k8s_namespace
        pods_result = await self.db.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.type == "k8s_pod",
                Asset.namespace.isnot(None),
                Asset.cluster.isnot(None),
            )
        )
        pods = pods_result.scalars().all()

        ns_result = await self.db.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.type == "k8s_namespace",
            )
        )
        ns_assets = {(a.cluster, a.name): a for a in ns_result.scalars().all()}

        cluster_result = await self.db.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.type == "k8s_cluster",
            )
        )
        clusters = {a.name: a for a in cluster_result.scalars().all()}

        for pod in pods:
            ns_asset = ns_assets.get((pod.cluster, pod.namespace))
            if ns_asset:
                await self._upsert_relationship(tenant_id, pod.id, ns_asset.id, "contains")
                # k8s_namespace → contains → k8s_cluster
                cluster_asset = clusters.get(pod.cluster)
                if cluster_asset:
                    await self._upsert_relationship(tenant_id, cluster_asset.id, ns_asset.id, "contains")

    async def _upsert_relationship(
        self, tenant_id: str, source_id: str, target_id: str, rel_type: str
    ) -> None:
        result = await self.db.execute(
            select(AssetRelationship).where(
                AssetRelationship.source_asset_id == source_id,
                AssetRelationship.target_asset_id == target_id,
                AssetRelationship.relationship_type == rel_type,
            )
        )
        if not result.scalar_one_or_none():
            rel = AssetRelationship(
                tenant_id=tenant_id,
                source_asset_id=source_id,
                target_asset_id=target_id,
                relationship_type=rel_type,
            )
            self.db.add(rel)
            await self.db.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _load_integrations(
        self, tenant_id: str, source_type: str | None = None
    ) -> list[Integration]:
        query = select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.is_active.is_(True),
            Integration.status == "connected",
        )
        if source_type:
            query = query.where(Integration.type == source_type)
        result = await self.db.execute(query)
        return result.scalars().all()


# ── Pure utility functions ────────────────────────────────────────────────────

def _infer_github_env(repo: dict) -> str:
    name = (repo.get("full_name") or repo.get("name") or "").lower()
    topics = [t.lower() for t in repo.get("topics", [])]
    all_hints = name + " " + " ".join(topics)
    if any(h in all_hints for h in ("prod", "production", "live")):
        return "production"
    if any(h in all_hints for h in ("stag", "staging", "stage")):
        return "staging"
    if any(h in all_hints for h in ("dev", "develop", "sandbox", "test")):
        return "development"
    return "unknown"


def _infer_k8s_env(namespace: str) -> str:
    ns = namespace.lower()
    if any(h in ns for h in ("prod", "production", "live")):
        return "production"
    if any(h in ns for h in ("stag", "staging")):
        return "staging"
    if any(h in ns for h in ("dev", "develop", "sandbox", "test", "qa")):
        return "development"
    return "unknown"
