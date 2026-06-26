from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class Technology(str, Enum):
    """Deterministic set of supported technologies."""
    NODEJS = "nodejs"
    PYTHON = "python"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    DOTNET = "dotnet"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    TERRAFORM = "terraform"
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    AZURE_PIPELINES = "azure_pipelines"
    HELM = "helm"
    ANSIBLE = "ansible"
    CLOUDFORMATION = "cloudformation"
    UNKNOWN = "unknown"

class DetectionResult(BaseModel):
    technology: Technology
    confidence: float
    detected_version: Optional[str] = None
    evidence: List[str] = []
