"""
Ownership management service.
Provides CRUD operations for ownership mappings and comprehensive statistics.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, text, update, desc, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ownership import (
    OwnershipMapping,
    OwnershipAuditLog,
    OwnershipDefault,
    RESOURCE_TYPES,
    OWNER_TYPES,
)
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.scan import Repository
from app.models.asset import Asset
from app.models.cluster import Cluster
from app.models.pod import Pod
from app.models.security_exception import SecurityException
from app.models.security_policy import SecurityPolicy
from app.models.compliance import Compliance
from app.models.sbom import SBOM
from app.models.security_ticket import SecurityTicket
from app.models.finding_sla import FindingSLA
from app.models.base import BaseModel
from app.utils.logger import logger


# Mapping of resource types to their models
RESOURCE_MODELS: Dict[str, Any] = {
    "repository": Repository,
    "organization": None,  # Special handling
    "project": None,  # Special handling
    "application": None,  # Special handling
    "service": None,  # Special handling
    "microservice": None,  # Special handling
    "container_image": None,  # Special handling
    "asset": Asset,
    "virtual_machine": Asset,  # VMs are stored as assets
    "cloud_account": None,  # Special handling
    "kubernetes_cluster": Cluster,
    "namespace": None,  # Stored in cluster/asset
    "deployment": None,  # Stored in cluster/asset
    "pod": Pod,
    "secret": None,  # Special handling
    "database": None,  # Special handling
    "storage_bucket": Asset,  # S3 buckets stored as assets
    "load_balancer": Asset,  # LBs stored as assets
    "policy": SecurityPolicy,
    "compliance_control": Compliance,
    "exception": SecurityException,
    "threat": Threat,
    "vulnerability": Vulnerability,
    "remediation_task": SecurityTicket,
    "sbom": SBOM,
}


class OwnershipService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================
    # CRUD Operations
    # ============================================

    async def get_ownership(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
    ) -> Optional[OwnershipMapping]:
        """Get ownership mapping for a specific entity."""
        result = await self.db.execute(
            select(OwnershipMapping).where(
                OwnershipMapping.tenant_id == tenant_id,
                OwnershipMapping.entity_type == entity_type,
                OwnershipMapping.entity_id == entity_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_ownership(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> OwnershipMapping:
        """Get existing ownership or create new one."""
        defaults = defaults or {}
        defaults["tenant_id"] = tenant_id
        defaults["entity_type"] = entity_type
        defaults["entity_id"] = entity_id

        obj = await self.get_ownership(tenant_id, entity_type, entity_id)
        if obj:
            return obj

        obj = OwnershipMapping(**defaults)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def set_ownership(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        owner: Optional[str] = None,
        owner_type: Optional[str] = "user",
        team: Optional[str] = None,
        department: Optional[str] = None,
        business_unit: Optional[str] = None,
        backup_owner: Optional[str] = None,
        escalation_chain: Optional[List[str]] = None,
        business_criticality: Optional[str] = "standard",
        environment: Optional[str] = "unknown",
        risk_level: Optional[str] = "medium",
        cloud_provider: Optional[str] = None,
        cloud_account_id: Optional[str] = None,
        cluster_name: Optional[str] = None,
        namespace: Optional[str] = None,
        region: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> OwnershipMapping:
        """Set or update ownership mapping for an entity."""
        # Get existing or create new
        obj = await self.get_ownership(tenant_id, entity_type, entity_id)
        if not obj:
            obj = OwnershipMapping(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )

        # Track changes for audit
        prev_owner = obj.owner
        prev_team = obj.team
        prev_dept = obj.department

        # Update fields
        if owner is not None:
            obj.owner = owner
        if owner_type:
            obj.owner_type = owner_type
        if team is not None:
            obj.team = team
        if department is not None:
            obj.department = department
        if business_unit is not None:
            obj.business_unit = business_unit
        if backup_owner is not None:
            obj.backup_owner = backup_owner
        if escalation_chain is not None:
            obj.escalation_chain = escalation_chain
        if business_criticality:
            obj.business_criticality = business_criticality
        if environment:
            obj.environment = environment
        if risk_level:
            obj.risk_level = risk_level
        if cloud_provider:
            obj.cloud_provider = cloud_provider
        if cloud_account_id:
            obj.cloud_account_id = cloud_account_id
        if cluster_name:
            obj.cluster_name = cluster_name
        if namespace:
            obj.namespace = namespace
        if region:
            obj.region = region

        obj.last_updated = datetime.now(timezone.utc)
        obj.is_assigned = bool(owner or team or department)
        obj.updated_by = updated_by

        # Update SLA status based on owner assignment
        obj.sla_status = (
            "violation"
            if not obj.is_assigned and obj.environment == "production"
            else "compliant"
        )

        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)

        # Create audit log
        await self._create_audit_log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            prev_owner=prev_owner,
            prev_team=prev_team,
            prev_dept=prev_dept,
            new_owner=owner,
            new_team=team,
            new_dept=department,
            change_type="update",
            changed_by=updated_by,
        )

        return obj

    async def remove_ownership(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        removed_by: Optional[str] = None,
    ) -> bool:
        """Remove ownership mapping for an entity."""
        obj = await self.get_ownership(tenant_id, entity_type, entity_id)
        if not obj:
            return False

        # Log removal
        await self._create_audit_log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            prev_owner=obj.owner,
            prev_team=obj.team,
            prev_dept=obj.department,
            new_owner=None,
            new_team=None,
            new_dept=None,
            change_type="remove",
            changed_by=removed_by,
        )

        obj.owner = None
        obj.team = None
        obj.department = None
        obj.business_unit = None
        obj.backup_owner = None
        obj.escalation_chain = []
        obj.is_assigned = False
        obj.removed_at = datetime.now(timezone.utc)

        self.db.add(obj)
        await self.db.commit()
        return True

    async def bulk_assign_ownership(
        self,
        tenant_id: str,
        entity_type: str,
        entity_ids: List[str],
        owner: Optional[str] = None,
        owner_type: Optional[str] = "user",
        team: Optional[str] = None,
        department: Optional[str] = None,
        business_unit: Optional[str] = None,
        business_criticality: Optional[str] = None,
        environment: Optional[str] = None,
        risk_level: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> int:
        """Bulk update ownership for multiple entities."""
        query = (
            update(OwnershipMapping)
            .where(
                OwnershipMapping.tenant_id == tenant_id,
                OwnershipMapping.entity_type == entity_type,
                OwnershipMapping.entity_id.in_(entity_ids),
            )
            .values(
                owner=owner,
                owner_type=owner_type or "user",
                team=team,
                department=department,
                business_unit=business_unit,
                business_criticality=business_criticality or "standard",
                environment=environment or "unknown",
                risk_level=risk_level or "medium",
                is_assigned=bool(owner or team or department),
                last_updated=datetime.now(timezone.utc),
                updated_by=updated_by,
            )
        )

        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount

    # ============================================
    # List and Filter
    # ============================================

    async def list_ownership(
        self,
        tenant_id: str,
        entity_type: Optional[str] = None,
        owner: Optional[str] = None,
        team: Optional[str] = None,
        department: Optional[str] = None,
        business_unit: Optional[str] = None,
        environment: Optional[str] = None,
        cloud_provider: Optional[str] = None,
        risk_level: Optional[str] = None,
        is_assigned: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OwnershipMapping]:
        """List ownership mappings with optional filters."""
        query = select(OwnershipMapping).where(
            OwnershipMapping.tenant_id == tenant_id
        )

        if entity_type:
            query = query.where(OwnershipMapping.entity_type == entity_type)
        if owner:
            query = query.where(OwnershipMapping.owner == owner)
        if team:
            query = query.where(OwnershipMapping.team == team)
        if department:
            query = query.where(OwnershipMapping.department == department)
        if business_unit:
            query = query.where(OwnershipMapping.business_unit == business_unit)
        if environment:
            query = query.where(OwnershipMapping.environment == environment)
        if cloud_provider:
            query = query.where(OwnershipMapping.cloud_provider == cloud_provider)
        if risk_level:
            query = query.where(OwnershipMapping.risk_level == risk_level)
        if is_assigned is not None:
            query = query.where(OwnershipMapping.is_assigned == is_assigned)

        query = query.order_by(desc(OwnershipMapping.last_updated))
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()

    # ============================================
    # Summary Statistics
    # ============================================

    async def get_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get ownership summary statistics."""
        # Get all mappings for this tenant
        result = await self.db.execute(
            select(OwnershipMapping).where(
                OwnershipMapping.tenant_id == tenant_id
            )
        )
        all_mappings = result.scalars().all()

        total = len(all_mappings)
        owned = sum(1 for m in all_mappings if m.is_assigned)
        unassigned = total - owned

        # Count unique teams, departments, security owners
        teams = set()
        departments = set()
        security_owners = set()

        for m in all_mappings:
            if m.team:
                teams.add(m.team.lower())
            if m.department:
                departments.add(m.department.lower())
            if m.owner and m.owner_type == "security_owner":
                security_owners.add(m.owner)

        # Count repositories and clusters covered
        repos_covered = sum(
            1 for m in all_mappings if m.entity_type == "repository" and m.is_assigned
        )
        clusters_covered = sum(
            1 for m in all_mappings if m.entity_type == "kubernetes_cluster" and m.is_assigned
        )

        # Count SLA violations (unassigned production resources)
        sla_violations = sum(
            1
            for m in all_mappings
            if m.environment == "production" and not m.is_assigned
        )

        # Calculate coverage percentage
        coverage_percent = round((owned / total * 100) if total > 0 else 0, 2)

        # Resource type breakdown
        by_resource_type: Dict[str, int] = {}
        for m in all_mappings:
            by_resource_type[m.entity_type] = by_resource_type.get(m.entity_type, 0) + 1

        # Environment breakdown
        by_environment: Dict[str, int] = {}
        for m in all_mappings:
            env = m.environment or "unknown"
            by_environment[env] = by_environment.get(env, 0) + 1

        # Cloud provider breakdown
        by_cloud_provider: Dict[str, int] = {}
        for m in all_mappings:
            if m.cloud_provider:
                by_cloud_provider[m.cloud_provider] = (
                    by_cloud_provider.get(m.cloud_provider, 0) + 1
                )

        return {
            "total_resources": total,
            "owned_resources": owned,
            "unassigned_resources": unassigned,
            "teams": len(teams),
            "departments": len(departments),
            "security_owners": len(security_owners),
            "repositories_covered": repos_covered,
            "clusters_covered": clusters_covered,
            "sla_violations": sla_violations,
            "ownership_coverage_percent": coverage_percent,
            "by_resource_type": by_resource_type,
            "by_environment": by_environment,
            "by_cloud_provider": by_cloud_provider,
        }

    # ============================================
    # Coverage Data for Charts
    # ============================================

    async def get_coverage_data(self, tenant_id: str) -> Dict[str, Any]:
        """Get detailed coverage data for chart visualization."""
        summary = await self.get_summary(tenant_id)

        # Get all mappings for detailed breakdowns
        result = await self.db.execute(
            select(OwnershipMapping).where(
                OwnershipMapping.tenant_id == tenant_id
            )
        )
        all_mappings = result.scalars().all()

        # By Team
        by_team: Dict[str, int] = {}
        for m in all_mappings:
            team = m.team or "unassigned"
            by_team[team] = by_team.get(team, 0) + 1

        team_data = [
            {"team": k, "count": v, "coverage_percent": round(v / len(all_mappings) * 100, 1) if all_mappings else 0}
            for k, v in sorted(by_team.items(), key=lambda x: -x[1])
        ]

        # By Department
        by_dept: Dict[str, int] = {}
        for m in all_mappings:
            dept = m.department or "unassigned"
            by_dept[dept] = by_dept.get(dept, 0) + 1

        dept_data = [
            {"department": k, "count": v, "coverage_percent": round(v / len(all_mappings) * 100, 1) if all_mappings else 0}
            for k, v in sorted(by_dept.items(), key=lambda x: -x[1])
        ]

        # By Environment
        by_env: Dict[str, int] = {}
        for m in all_mappings:
            env = m.environment or "unknown"
            by_env[env] = by_env.get(env, 0) + 1

        env_data = [
            {"environment": k, "count": v, "owned": sum(1 for x in all_mappings if x.environment == k and x.is_assigned)}
            for k, v in sorted(by_env.items(), key=lambda x: -x[1])
        ]

        # By Cloud Provider
        by_provider: Dict[str, int] = {}
        for m in all_mappings:
            if m.cloud_provider:
                by_provider[m.cloud_provider] = by_provider.get(m.cloud_provider, 0) + 1

        provider_data = [
            {"provider": k, "count": v, "owned": sum(1 for x in all_mappings if x.cloud_provider == k and x.is_assigned)}
            for k, v in sorted(by_provider.items(), key=lambda x: -x[1])
        ]

        # By Resource Type
        by_rtype: Dict[str, int] = {}
        for m in all_mappings:
            rtype = m.entity_type
            by_rtype[rtype] = by_rtype.get(rtype, 0) + 1

        rtype_data = [
            {"resource_type": k, "count": v, "owned": sum(1 for x in all_mappings if x.entity_type == k and x.is_assigned)}
            for k, v in sorted(by_rtype.items(), key=lambda x: -x[1])
        ]

        return {
            "total": summary["total_resources"],
            "owned": summary["owned_resources"],
            "unassigned": summary["unassigned_resources"],
            "coverage_percent": summary["ownership_coverage_percent"],
            "by_team": team_data,
            "by_department": dept_data,
            "by_environment": env_data,
            "by_cloud_provider": provider_data,
            "by_resource_type": rtype_data,
        }

    # ============================================
    # Owner Profile
    # ============================================

    async def get_owner_profile(
        self,
        tenant_id: str,
        owner: str,
    ) -> Dict[str, Any]:
        """Get detailed profile for an owner."""
        # Find all mappings for this owner
        result = await self.db.execute(
            select(OwnershipMapping).where(
                OwnershipMapping.tenant_id == tenant_id,
                or_(
                    OwnershipMapping.owner == owner,
                    OwnershipMapping.backup_owner == owner,
                ),
            )
        )
        mappings = result.scalars().all()

        # Filter to primary owner only
        primary_mappings = [m for m in mappings if m.owner == owner]

        # Get assigned vulnerabilities
        vuln_result = await self.db.execute(
            select(Vulnerability).where(
                Vulnerability.tenant_id == tenant_id,
                or_(
                    Vulnerability.owner == owner,
                    Vulnerability.team == owner,
                ),
            )
        )
        vulns = vuln_result.scalars().all()

        # Get assigned threats
        threat_result = await self.db.execute(
            select(Threat).where(
                Threat.tenant_id == tenant_id,
                or_(
                    Threat.owner == owner,
                    Threat.team == owner,
                ),
            )
        )
        threats = threat_result.scalars().all()

        # Get open remediations
        ticket_result = await self.db.execute(
            select(SecurityTicket).where(
                SecurityTicket.tenant_id == tenant_id,
                or_(
                    SecurityTicket.assignee == owner,
                    SecurityTicket.provider_meta.op("->>")(text("'owner'")) == owner,
                ),
                SecurityTicket.ticket_status.notin_(["closed", "resolved"]),
            )
        )
        tickets = ticket_result.scalars().all()

        # Get compliance violations
        compliance_result = await self.db.execute(
            select(Compliance).where(
                Compliance.tenant_id == tenant_id,
                Compliance.failed > 0,
            )
        )
        compliance_entries = compliance_result.scalars().all()

        # Calculate metrics
        total_resources = len(primary_mappings)
        total_vulns = len(vulns)
        total_threats = len(threats)
        total_remediations = len(tickets)
        compliance_violations = len(compliance_entries)

        # Risk distribution
        critical_count = sum(1 for m in primary_mappings if m.risk_level == "critical")
        high_count = sum(1 for m in primary_mappings if m.risk_level == "high")
        medium_count = sum(1 for m in primary_mappings if m.risk_level == "medium")
        low_count = sum(1 for m in primary_mappings if m.risk_level == "low")

        # Calculate average MTTR (from SLA entries)
        sla_result = await self.db.execute(
            select(FindingSLA).where(
                FindingSLA.tenant_id == tenant_id,
                or_(
                    FindingSLA.owner == owner,
                    FindingSLA.team == owner,
                ),
                FindingSLA.actual_hours != None,
            )
        )
        sla_entries = sla_result.scalars().all()

        avg_mttr = None
        if sla_entries:
            total_hours = sum(
                float(sla.actual_hours) for sla in sla_entries if sla.actual_hours
            )
            avg_mttr = round(total_hours / len(sla_entries), 1)

        # SLA compliance rate
        if sla_entries:
            compliant_count = sum(
                1 for sla in sla_entries
                if sla.actual_hours and sla.budget_hours and float(sla.actual_hours) <= float(sla.budget_hours)
            )
            sla_compliance_rate = round(compliant_count / len(sla_entries) * 100, 1)
        else:
            sla_compliance_rate = None

        # Repository ownership details
        repo_mappings = [m for m in primary_mappings if m.entity_type == "repository"]
        repo_ownership = [
            {
                "name": getattr(
                    await self._get_entity_name(tenant_id, "repository", m.entity_id),
                    "full_name",
                    m.entity_id,
                ),
                "id": m.entity_id,
                "team": m.team,
                "environment": m.environment,
                "risk_level": m.risk_level,
            }
            for m in repo_mappings[:50]
        ]

        # Infrastructure ownership details
        infra_mappings = [
            m
            for m in primary_mappings
            if m.entity_type in ["asset", "virtual_machine", "cloud_account", "kubernetes_cluster"]
        ]
        infra_ownership = [
            {
                "name": getattr(
                    await self._get_entity_name(tenant_id, m.entity_type, m.entity_id),
                    "name",
                    m.entity_id,
                ),
                "id": m.entity_id,
                "type": m.entity_type,
                "team": m.team,
                "environment": m.environment,
                "cloud_provider": m.cloud_provider,
            }
            for m in infra_mappings[:50]
        ]

        # Application ownership details
        app_mappings = [
            m
            for m in primary_mappings
            if m.entity_type in ["application", "service", "microservice", "deployment"]
        ]
        app_ownership = [
            {
                "name": m.entity_id,
                "id": m.entity_id,
                "type": m.entity_type,
                "team": m.team,
                "environment": m.environment,
            }
            for m in app_mappings[:50]
        ]

        # Calculate overdue tasks
        overdue_count = sum(
            1 for sla in sla_entries
            if sla.budget_hours and sla.actual_hours and float(sla.actual_hours) > float(sla.budget_hours)
        )

        return {
            "owner": owner,
            "owner_type": "user",
            "total_resources": total_resources,
            "total_vulnerabilities": total_vulns,
            "total_threats": total_threats,
            "total_remediations": total_remediations,
            "compliance_violations": compliance_violations,
            "avg_mttr_hours": avg_mttr,
            "sla_compliance_rate": sla_compliance_rate,
            "critical_risk_count": critical_count,
            "high_risk_count": high_count,
            "medium_risk_count": medium_count,
            "low_risk_count": low_count,
            "repository_ownership": repo_ownership,
            "infrastructure_ownership": infra_ownership,
            "application_ownership": app_ownership,
            "overdue_tasks": overdue_count,
        }

    async def _get_entity_name(
        self, tenant_id: str, entity_type: str, entity_id: str
    ) -> Optional[Any]:
        """Get entity name for display purposes."""
        model = RESOURCE_MODELS.get(entity_type)
        if not model:
            return None

        try:
            result = await self.db.execute(
                select(model).where(
                    model.tenant_id == tenant_id,
                    model.id == entity_id,
                )
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    # ============================================
    # Audit Logs
    # ============================================

    async def _create_audit_log(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        prev_owner: Optional[str],
        prev_team: Optional[str],
        prev_dept: Optional[str],
        new_owner: Optional[str],
        new_team: Optional[str],
        new_dept: Optional[str],
        change_type: str,
        changed_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Create an audit log entry for ownership change."""
        # Get entity name for logging
        entity_name = None
        model = RESOURCE_MODELS.get(entity_type)
        if model:
            try:
                result = await self.db.execute(
                    select(model).where(
                        model.tenant_id == tenant_id,
                        model.id == entity_id,
                    )
                )
                entity = result.scalar_one_or_none()
                if entity:
                    if hasattr(entity, "full_name"):
                        entity_name = entity.full_name
                    elif hasattr(entity, "name"):
                        entity_name = entity.name
                    elif hasattr(entity, "title"):
                        entity_name = entity.title
                    else:
                        entity_name = entity_id
            except Exception:
                entity_name = entity_id

        audit = OwnershipAuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            prev_owner=prev_owner,
            prev_team=prev_team,
            prev_dept=prev_dept,
            new_owner=new_owner,
            new_team=new_team,
            new_dept=new_dept,
            changed_by=changed_by or "system",
            change_type=change_type,
            reason=reason,
        )
        self.db.add(audit)
        await self.db.commit()

    async def get_audit_logs(
        self,
        tenant_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[OwnershipAuditLog]:
        """Get audit logs with optional filters."""
        query = select(OwnershipAuditLog).where(
            OwnershipAuditLog.tenant_id == tenant_id
        )

        if entity_type:
            query = query.where(OwnershipAuditLog.entity_type == entity_type)
        if entity_id:
            query = query.where(OwnershipAuditLog.entity_id == entity_id)
        if owner:
            query = query.where(
                or_(
                    OwnershipAuditLog.prev_owner == owner,
                    OwnershipAuditLog.new_owner == owner,
                )
            )

        query = query.order_by(desc(OwnershipAuditLog.changed_at))
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()

    # ============================================
    # Import/Export
    # ============================================

    async def import_ownership(
        self,
        tenant_id: str,
        csv_content: str,
        mapping_type: str = "overwrite",
    ) -> Dict[str, Any]:
        """Import ownership mappings from CSV content."""
        # Parse CSV
        lines = csv_content.strip().split("\n")
        if len(lines) < 2:
            return {
                "total_processed": 0,
                "success": 0,
                "failures": 0,
                "errors": [],
            }

        header = [h.strip().lower() for h in lines[0].split(",")]
        required_fields = {"entity_type", "entity_id"}

        if not required_fields.issubset(set(header)):
            return {
                "total_processed": 0,
                "success": 0,
                "failures": 1,
                "errors": [
                    {
                        "message": f"Missing required fields. Need: {required_fields}",
                        "row": 0,
                    }
                ],
            }

        total = 0
        success = 0
        failures = 0
        errors = []

        # Find index for optional fields
        def get_field_index(name: str) -> Optional[int]:
            try:
                return header.index(name)
            except ValueError:
                return None

        owner_idx = get_field_index("owner")
        team_idx = get_field_index("team")
        dept_idx = get_field_index("department")
        env_idx = get_field_index("environment")
        risk_idx = get_field_index("risk_level")

        for i, line in enumerate(lines[1:], start=2):
            if not line.strip():
                continue

            total += 1
            values = [v.strip() for v in line.split(",")]

            try:
                entity_type = values[header.index("entity_type")]
                entity_id = values[header.index("entity_id")]

                # Skip unsupported entity types
                if entity_type not in RESOURCE_TYPES:
                    failures += 1
                    errors.append(
                        {
                            "message": f"Unsupported entity type: {entity_type}",
                            "row": i,
                            "entity_type": entity_type,
                            "entity_id": entity_id,
                        }
                    )
                    continue

                # Build ownership data
                ownership_data: Dict[str, Any] = {
                    "tenant_id": tenant_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                }

                if owner_idx is not None and owner_idx < len(values):
                    ownership_data["owner"] = values[owner_idx] or None
                if team_idx is not None and team_idx < len(values):
                    ownership_data["team"] = values[team_idx] or None
                if dept_idx is not None and dept_idx < len(values):
                    ownership_data["department"] = values[dept_idx] or None
                if env_idx is not None and env_idx < len(values):
                    ownership_data["environment"] = values[env_idx] or "unknown"
                if risk_idx is not None and risk_idx < len(values):
                    ownership_data["risk_level"] = values[risk_idx] or "medium"

                # Check if mapping exists
                existing = await self.get_ownership(
                    tenant_id, entity_type, entity_id
                )

                if existing and mapping_type == "skip_existing":
                    continue

                if existing and mapping_type == "merge":
                    # Merge only non-null values
                    if ownership_data.get("owner"):
                        existing.owner = ownership_data["owner"]
                    if ownership_data.get("team"):
                        existing.team = ownership_data["team"]
                    if ownership_data.get("department"):
                        existing.department = ownership_data["department"]
                    if ownership_data.get("environment"):
                        existing.environment = ownership_data["environment"]
                    if ownership_data.get("risk_level"):
                        existing.risk_level = ownership_data["risk_level"]
                    self.db.add(existing)
                else:
                    # Create new mapping
                    mapping = OwnershipMapping(**ownership_data)
                    self.db.add(mapping)

                success += 1

            except Exception as e:
                failures += 1
                errors.append(
                    {
                        "message": str(e),
                        "row": i,
                        "line": line,
                    }
                )

        await self.db.commit()
        return {
            "total_processed": total,
            "success": success,
            "failures": failures,
            "errors": errors,
        }

    async def export_ownership(
        self,
        tenant_id: str,
        filters: Dict[str, Any] = None,
    ) -> str:
        """Export ownership mappings as CSV."""
        from io import StringIO
        import csv

        filters = filters or {}

        # Build query
        query = select(OwnershipMapping).where(
            OwnershipMapping.tenant_id == tenant_id
        )

        if filters.get("entity_types"):
            query = query.where(
                OwnershipMapping.entity_type.in_(filters["entity_types"])
            )
        if filters.get("owner"):
            query = query.where(OwnershipMapping.owner == filters["owner"])
        if filters.get("team"):
            query = query.where(OwnershipMapping.team == filters["team"])
        if filters.get("department"):
            query = query.where(OwnershipMapping.department == filters["department"])
        if filters.get("environment"):
            query = query.where(
                OwnershipMapping.environment == filters["environment"]
            )

        result = await self.db.execute(query)
        mappings = result.scalars().all()

        # Build CSV
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "entity_type",
                "entity_id",
                "owner",
                "owner_type",
                "team",
                "department",
                "business_unit",
                "backup_owner",
                "environment",
                "risk_level",
                "sla_status",
                "cloud_provider",
                "cloud_account_id",
                "cluster_name",
                "namespace",
                "last_updated",
            ]
        )

        # Rows
        for m in mappings:
            writer.writerow(
                [
                    m.entity_type,
                    m.entity_id,
                    m.owner or "",
                    m.owner_type,
                    m.team or "",
                    m.department or "",
                    m.business_unit or "",
                    m.backup_owner or "",
                    m.environment or "",
                    m.risk_level or "",
                    m.sla_status or "",
                    m.cloud_provider or "",
                    m.cloud_account_id or "",
                    m.cluster_name or "",
                    m.namespace or "",
                    m.last_updated.isoformat() if m.last_updated else "",
                ]
            )

        return output.getvalue()
