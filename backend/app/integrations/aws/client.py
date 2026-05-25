from __future__ import annotations
"""AWS base client — handles session creation and connection testing."""
import boto3
from app.integrations.base import BaseIntegration


class AWSClient(BaseIntegration):
    def __init__(self, config: dict):
        super().__init__(config)
        self._session = None

    def get_session(self) -> boto3.Session:
        if not self._session:
            self._session = boto3.Session(
                aws_access_key_id=self.config.get("access_key_id")
                    or self.config.get("access_key"),
                aws_secret_access_key=self.config.get("secret_access_key")
                    or self.config.get("secret_key"),
                region_name=self.config.get("region", "us-east-1"),
            )
        return self._session

    async def verify_credentials_via_sts(self) -> bool:
        """
        Primary credential verification using STS GetCallerIdentity.
        This API call:
          - Requires ZERO IAM permissions (it always works for valid credentials)
          - Fails immediately on wrong Access Key ID or Secret Access Key
          - Should be used as the sole "are credentials valid?" check
        Returns True only when credentials are cryptographically valid.
        """
        from app.utils.logger import logger
        try:
            sts = self.get_session().client("sts")
            identity = sts.get_caller_identity()
            if identity.get("Account"):
                logger.info(
                    f"[aws_sts_ok] account={identity['Account']} "
                    f"arn={identity.get('Arn','?')[:60]}"
                )
                return True
            return False
        except Exception as e:
            err = str(e)
            logger.warning(f"[aws_sts_failed] {err[:120]}")
            return False

    async def test_connection(self) -> bool:
        """
        Backward-compat: tries STS → CE → EC2 in order.
        Prefer verify_credentials_via_sts() for explicit credential checks.
        """
        from app.utils.logger import logger

        # 1. STS — fastest, zero permissions needed
        if await self.verify_credentials_via_sts():
            return True

        # 2. Cost Explorer — for billing-focused IAM roles that may lack sts:GetCallerIdentity
        try:
            from datetime import date, timedelta
            ce = self.get_session().client("ce", region_name="us-east-1")
            today = date.today()
            start = (today.replace(day=1)).isoformat()
            end = today.isoformat()
            if start == end:
                start = (today - timedelta(days=1)).isoformat()
            ce.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            logger.info("[aws_ce_ok] test_connection OK via Cost Explorer")
            return True
        except Exception as e:
            logger.warning(f"[aws_ce_failed] {str(e)[:80]}")

        # 3. EC2 DescribeRegions — available to almost any valid credential
        try:
            ec2 = self.get_session().client("ec2", region_name="us-east-1")
            ec2.describe_regions(Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}])
            logger.info("[aws_ec2_ok] test_connection OK via EC2 DescribeRegions")
            return True
        except Exception as e:
            logger.warning(f"[aws_ec2_failed] {str(e)[:80]}")

        return False

    async def get_account_id(self) -> str | None:
        try:
            sts = self.get_session().client("sts")
            return sts.get_caller_identity().get("Account")
        except Exception:
            return None

    async def sync(self) -> dict:
        """Full sync: costs + security findings."""
        from app.integrations.aws.cost_explorer import CostExplorer
        from app.integrations.aws.security_hub import SecurityHub

        cost_data = await CostExplorer(self.config).get_costs_by_service(months=3)
        threats = await SecurityHub(self.config).get_threats()
        vulns = await SecurityHub(self.config).get_vulnerabilities()

        return {
            "cost_records": len(cost_data),
            "threats_found": len(threats),
            "vulnerabilities_found": len(vulns),
        }
