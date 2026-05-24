from __future__ import annotations
"""AWS Security Hub — fetches findings and maps them to UniOps threats/vulnerabilities."""
from app.integrations.aws.client import AWSClient

# Map AWS severity to UniOps severity
SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFORMATIONAL": "low",
}

# Map finding type to UniOps category
CATEGORY_MAP = {
    "Software and Configuration Checks": "vulnerability",
    "TTPs": "intrusion",
    "Effects": "impact",
    "Unusual Behaviors": "anomaly",
    "Sensitive Data Identifications": "data_exposure",
}


class SecurityHub(AWSClient):

    async def get_findings(self, max_results: int = 100) -> list[dict]:
        """Raw findings from Security Hub."""
        try:
            hub = self.get_session().client("securityhub")
            response = hub.get_findings(
                Filters={
                    "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
                    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}],
                },
                MaxResults=min(max_results, 100),
            )
            return response.get("Findings", [])
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"SecurityHub.get_findings failed: {e}")
            return []

    async def get_threats(self) -> list[dict]:
        """Convert Security Hub findings → UniOps threat format."""
        findings = await self.get_findings(max_results=50)
        threats = []

        for f in findings:
            severity_label = f.get("Severity", {}).get("Label", "MEDIUM")
            finding_type = f.get("Types", [""])[0].split("/")[0]

            # Only intrusion-type findings become threats
            if finding_type not in ("TTPs", "Effects", "Unusual Behaviors"):
                continue

            resource = f.get("Resources", [{}])[0]
            threats.append({
                "title": f.get("Title", "Security Finding"),
                "description": f.get("Description", ""),
                "severity": SEVERITY_MAP.get(severity_label, "medium"),
                "category": CATEGORY_MAP.get(finding_type, "network"),
                "source": "aws_security_hub",
                "source_id": f.get("Id", ""),
                "resource": resource.get("Id", ""),
                "ip": self._extract_ip(f),
                "mitre_tactic": self._extract_mitre_tactic(f),
                "mitre_technique": self._extract_mitre_technique(f),
                "raw_data": {
                    "finding_id": f.get("Id"),
                    "product_arn": f.get("ProductArn"),
                    "generator_id": f.get("GeneratorId"),
                    "aws_account": f.get("AwsAccountId"),
                    "region": f.get("Region"),
                },
                "detected_at": f.get("FirstObservedAt") or f.get("CreatedAt"),
            })
        return threats

    async def get_vulnerabilities(self) -> list[dict]:
        """Convert Security Hub findings → UniOps vulnerability format."""
        findings = await self.get_findings(max_results=100)
        vulns = []

        for f in findings:
            severity_label = f.get("Severity", {}).get("Label", "MEDIUM")
            finding_type = f.get("Types", [""])[0].split("/")[0]

            if finding_type != "Software and Configuration Checks":
                continue

            # Extract CVE if present
            cve_id = None
            for vuln in f.get("Vulnerabilities", []):
                if vuln.get("Id", "").startswith("CVE-"):
                    cve_id = vuln["Id"]
                    break

            resource = f.get("Resources", [{}])[0]
            remediation = f.get("Remediation", {}).get("Recommendation", {})

            vulns.append({
                "cve_id": cve_id,
                "title": f.get("Title", "Vulnerability Finding"),
                "description": f.get("Description", ""),
                "severity": SEVERITY_MAP.get(severity_label, "medium"),
                "cvss_score": f.get("Severity", {}).get("Normalized", 0) / 10,
                "status": "open",
                "target": resource.get("Id", ""),
                "image": resource.get("Id") if resource.get("Type") == "AwsEcrContainerImage" else None,
                "package_name": self._extract_package(f),
                "package_version": self._extract_version(f),
                "fixed_version": self._extract_fix(f),
                "references": [remediation.get("Url")] if remediation.get("Url") else [],
                "raw_data": {"finding_id": f.get("Id"), "generator_id": f.get("GeneratorId")},
            })
        return vulns

    async def get_compliance_status(self) -> list[dict]:
        """Compliance standards scores from Security Hub."""
        try:
            hub = self.get_session().client("securityhub")
            standards = hub.get_enabled_standards().get("StandardsSubscriptions", [])
            results = []

            for std in standards:
                arn = std["StandardsSubscriptionArn"]
                controls = hub.describe_standards_controls(
                    StandardsSubscriptionArn=arn, MaxResults=100
                ).get("Controls", [])

                passed = sum(1 for c in controls if c.get("ControlStatus") == "ENABLED" and c.get("ComplianceStatus") == "PASSED")
                failed = sum(1 for c in controls if c.get("ComplianceStatus") == "FAILED")
                total = passed + failed

                score = round((passed / total * 100) if total > 0 else 0, 1)
                name = std.get("StandardsArn", "").split("/")[-2].replace("-", " ").title()

                results.append({
                    "framework": name,
                    "score": score,
                    "passed": passed,
                    "failed": failed,
                    "total": total,
                    "status": "compliant" if score >= 80 else ("in_progress" if score >= 50 else "non_compliant"),
                })
            return results
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"SecurityHub.get_compliance_status failed: {e}")
            return []

    async def resolve_finding(
        self,
        finding_id: str,
        note: str = "Resolved via UniOps Security Center",
    ) -> dict:
        """
        Mark a Security Hub finding as RESOLVED.

        AWS API: batch_update_findings — sets:
          WorkflowStatus = RESOLVED
          Note           = {Text: note, UpdatedBy: "UniOps"}

        The finding stays in Security Hub history (for audit trail) but moves
        out of the ACTIVE/NEW filter, so it won't appear in future syncs.

        Args:
            finding_id: The raw AWS finding ARN stored in raw_data["finding_id"]
            note:       Optional resolution note written back to Security Hub

        Returns:
            {"success": bool, "processed": int, "failed_count": int, "error": str|None}
        """
        try:
            hub = self.get_session().client("securityhub")

            # Parse product_arn from finding_id (ARN format)
            # finding_id looks like:
            # arn:aws:securityhub:us-east-1:123456789012:subscription/aws-foundational-security/...
            # We need ProductArn which is stored alongside the finding
            response = hub.batch_update_findings(
                FindingIdentifiers=[{"Id": finding_id, "ProductArn": self._extract_product_arn(finding_id)}],
                Workflow={"Status": "RESOLVED"},
                Note={"Text": note[:512], "UpdatedBy": "UniOps"},
            )
            processed    = len(response.get("ProcessedFindings", []))
            unprocessed  = response.get("UnprocessedFindings", [])
            failed_count = len(unprocessed)

            if failed_count > 0:
                reason = unprocessed[0].get("ErrorMessage", "Unknown error")
                logger.warning(f"SecurityHub resolve partially failed: {reason}")
                return {
                    "success":     processed > 0,
                    "processed":   processed,
                    "failed_count":failed_count,
                    "error":       reason if processed == 0 else None,
                }

            logger.info(f"SecurityHub finding resolved: {finding_id[:60]}...")
            return {"success": True, "processed": processed, "failed_count": 0, "error": None}

        except Exception as e:
            err = str(e)
            logger.error(f"SecurityHub.resolve_finding failed ({finding_id[:40]}...): {err}")
            return {"success": False, "processed": 0, "failed_count": 1, "error": err}

    async def suppress_finding(self, finding_id: str, reason: str = "TOLERATED") -> dict:
        """
        Suppress a finding (NOTIFIED → won't resurface in scans).
        Used for false positives or accepted risks.
        reason options: "INTENDED", "FALSE_POSITIVE", "TOLERATED"
        """
        valid_reasons = {"INTENDED", "FALSE_POSITIVE", "TOLERATED"}
        if reason not in valid_reasons:
            reason = "TOLERATED"
        try:
            hub = self.get_session().client("securityhub")
            response = hub.batch_update_findings(
                FindingIdentifiers=[{"Id": finding_id, "ProductArn": self._extract_product_arn(finding_id)}],
                Workflow={"Status": "SUPPRESSED"},
                Note={"Text": f"Suppressed via UniOps: {reason}", "UpdatedBy": "UniOps"},
            )
            processed = len(response.get("ProcessedFindings", []))
            logger.info(f"SecurityHub finding suppressed ({reason}): {finding_id[:60]}...")
            return {"success": processed > 0, "processed": processed, "error": None}
        except Exception as e:
            logger.error(f"SecurityHub.suppress_finding failed: {e}")
            return {"success": False, "processed": 0, "error": str(e)}

    def _extract_product_arn(self, finding_id: str) -> str:
        """
        Derive ProductArn from finding ID ARN.
        Finding ID: arn:aws:securityhub:{region}:{account}:subscription/{product-path}/{finding}
        ProductArn: arn:aws:securityhub:{region}:{account}:product/{account}/default
                    OR the subscription prefix

        For AWS-native findings the ProductArn is always the subscription prefix up to the product.
        We reconstruct it best-effort; the SecurityHub API will reject if wrong.
        """
        # Many AWS native findings use this pattern — we extract up to /subscription/{product}
        try:
            parts = finding_id.split("/")
            # Rebuild as subscription ARN (drop the finding UUID at the end)
            arn_prefix = "/".join(parts[:-1])  # everything except last segment
            return arn_prefix
        except Exception:
            return finding_id  # fall back to using the finding_id itself
        for detail in finding.get("NetworkPath", []):
            if detail.get("ComponentType") == "source":
                return detail.get("Egress", {}).get("Destination", {}).get("IpV4Addresses", [None])[0]
        network = finding.get("Network", {})
        return network.get("SourceIpV4") or network.get("DestinationIpV4")

    def _extract_mitre_tactic(self, finding: dict) -> str | None:
        for t in finding.get("ThreatIntelIndicators", []):
            if t.get("Category") == "BACKDOOR":
                return "Persistence"
        types = finding.get("Types", [])
        if types:
            parts = types[0].split("/")
            return parts[1] if len(parts) > 1 else None
        return None

    def _extract_mitre_technique(self, finding: dict) -> str | None:
        for ref in finding.get("RelatedRequirements", []):
            if ref.startswith("NIST.SP.800-53"):
                return ref
        return None

    def _extract_package(self, finding: dict) -> str | None:
        for v in finding.get("Vulnerabilities", []):
            pkgs = v.get("VulnerablePackages", [])
            if pkgs:
                return pkgs[0].get("Name")
        return None

    def _extract_version(self, finding: dict) -> str | None:
        for v in finding.get("Vulnerabilities", []):
            pkgs = v.get("VulnerablePackages", [])
            if pkgs:
                return pkgs[0].get("Version")
        return None

    def _extract_fix(self, finding: dict) -> str | None:
        for v in finding.get("Vulnerabilities", []):
            pkgs = v.get("VulnerablePackages", [])
            if pkgs:
                return pkgs[0].get("FixedInVersion")
        return None
