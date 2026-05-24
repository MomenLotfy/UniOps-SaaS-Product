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
        try:
            sts = self.get_session().client("sts")
            identity = sts.get_caller_identity()
            return bool(identity.get("Account"))
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"AWS connection test failed: {e}")
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
