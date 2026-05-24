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

    async def test_connection(self) -> bool:
        from app.utils.logger import logger

        # 1. Try STS (fastest, always works for valid credentials with any permissions)
        try:
            sts = self.get_session().client("sts")
            identity = sts.get_caller_identity()
            if identity.get("Account"):
                logger.info(f"AWS test_connection OK via STS (account={identity['Account']})")
                return True
        except Exception as e:
            logger.warning(f"AWS STS test failed (will try fallbacks): {e}")

        # 2. Try Cost Explorer — works for billing-focused IAM users
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
            logger.info("AWS test_connection OK via Cost Explorer")
            return True
        except Exception as e:
            logger.warning(f"AWS Cost Explorer test failed (will try EC2): {e}")

        # 3. Try EC2 DescribeRegions — available to virtually any AWS credential
        try:
            ec2 = self.get_session().client("ec2", region_name="us-east-1")
            ec2.describe_regions(Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}])
            logger.info("AWS test_connection OK via EC2 DescribeRegions")
            return True
        except Exception as e:
            logger.warning(f"AWS EC2 test failed: {e}")

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
