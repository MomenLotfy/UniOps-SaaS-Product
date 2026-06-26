from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class FindingCategory(str, Enum):
    """Deterministic categories for security findings."""
    DEPENDENCY_VULNERABILITY = "dependency_vulnerability"
    CONTAINER_VULNERABILITY = "container_vulnerability"
    DOCKERFILE_MISCONFIG = "dockerfile_misconfiguration"
    K8S_MISCONFIG = "kubernetes_misconfiguration"
    TF_MISCONFIG = "terraform_misconfiguration"
    CICD_MISCONFIG = "cicd_misconfiguration"
    SECRETS_EXPOSURE = "secrets_exposure"
    SOURCE_CODE_ISSUE = "source_code_issue"
    COMPLIANCE_ISSUE = "compliance_issue"
    CLOUD_MISCONFIG = "cloud_misconfiguration"
    IDENTITY_MISCONFIG = "identity_misconfiguration"
    NETWORK_MISCONFIG = "network_misconfiguration"
    UNKNOWN = "unknown"

class ClassificationResult(BaseModel):
    category: FindingCategory
    confidence: float
    suggested_capabilities: List[str] = []
