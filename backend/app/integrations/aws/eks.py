from app.integrations.aws.client import AWSClient


class EKSClient(AWSClient):
    async def list_clusters(self) -> list[str]:
        try:
            eks = self.get_session().client("eks")
            return eks.list_clusters().get("clusters", [])
        except Exception:
            return []

    async def describe_cluster(self, cluster_name: str) -> dict:
        try:
            eks = self.get_session().client("eks")
            return eks.describe_cluster(name=cluster_name).get("cluster", {})
        except Exception:
            return {}
