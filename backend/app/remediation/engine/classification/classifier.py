from typing import Any, Dict, Optional
from app.remediation.engine.classification.categories import FindingCategory, ClassificationResult
from app.utils.logger import logger

class FindingClassifier:
    """
    Classifies raw security findings into deterministic categories.
    Uses rule-based matching on finding IDs, titles, and descriptions.
    """
    def __init__(self):
        # In a production environment, these rules could be loaded from a DB or config file.
        self.rules = {
            "CVE": FindingCategory.DEPENDENCY_VULNERABILITY,
            "S3": FindingCategory.CLOUD_MISCONFIG,
            "Dockerfile": FindingCategory.DOCKERFILE_MISCONFIG,
            "k8s": FindingCategory.K8S_MISCONFIG,
            "terraform": FindingCategory.TF_MISCONFIG,
            "Secret": FindingCategory.SECRETS_EXPOSURE,
            "Privilege": FindingCategory.IDENTITY_MISCONFIG,
            "Network": FindingCategory.NETWORK_MISCONFIG,
        }

    async def classify(self, finding_metadata: Dict[str, Any]) -> ClassificationResult:
        """
        Classifies a finding based on its metadata.
        """
        title = finding_metadata.get("title", "").lower()
        description = finding_metadata.get("description", "").lower()
        finding_id = finding_metadata.get("id", "")

        # 1. Check for CVEs
        if "cve" in finding_id.lower() or "cve" in title:
            return ClassificationResult(
                category=FindingCategory.DEPENDENCY_VULNERABILITY,
                confidence=0.9,
                suggested_capabilities=["DependencyUpgrade", "VersionPinning"]
            )

        # 2. Rule-based matching
        for keyword, category in self.rules.items():
            if keyword.lower() in title or keyword.lower() in description:
                return ClassificationResult(
                    category=category,
                    confidence=0.7,
                    suggested_capabilities=self._get_default_capabilities(category)
                )

        return ClassificationResult(category=FindingCategory.UNKNOWN, confidence=0.0)

    def _get_default_capabilities(self, category: FindingCategory) -> List[str]:
        mapping = {
            FindingCategory.DOCKERFILE_MISCONFIG: ["DockerImageHardening"],
            FindingCategory.TF_MISCONFIG: ["TfInfrastructureFix"],
            FindingCategory.SECRETS_EXPOSURE: ["SecretRotation", "SecretVaulting"],
            FindingCategory.K8S_MISCONFIG: ["K8sSecurityHardening"],
        }
        return mapping.get(category, [])
