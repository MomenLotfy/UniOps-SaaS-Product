from typing import Any, Dict, List
from app.remediation.engine.detection.tech_types import Technology, DetectionResult
from app.utils.logger import logger

class TechnologyDetector:
    """
    Detects the affected technology for a finding.
    Uses rule-based detection on file paths, content patterns, and metadata.
    """
    def __init__(self):
        # Mapping of file patterns/extensions to technologies
        self.file_rules = {
            "package.json": Technology.NODEJS,
            "requirements.txt": Technology.PYTHON,
            "pyproject.toml": Technology.PYTHON,
            "pom.xml": Technology.JAVA,
            "go.mod": Technology.GO,
            "Cargo.toml": Technology.RUST,
            "Dockerfile": Technology.DOCKER,
            "main.tf": Technology.TERRAFORM,
            ".tf": Technology.TERRAFORM,
            "values.yaml": Technology.HELM,
            "Chart.yaml": Technology.HELM,
            ".github/workflows": Technology.GITHUB_ACTIONS,
            ".gitlab-ci.yml": Technology.GITLAB_CI,
            "k8s": Technology.KUBERNETES,
        }

    async def detect(self, context_metadata: Dict[str, Any]) -> DetectionResult:
        """
        Detects technology based on provided metadata (file paths, repo structure, etc).
        """
        file_paths = context_metadata.get("affected_files", [])
        tech_hints = context_metadata.get("technology_hints", [])

        # 1. Direct hint check
        for hint in tech_hints:
            try:
                return DetectionResult(technology=Technology(hint.lower()), confidence=1.0, evidence=[f"Direct hint: {hint}"])
            except ValueError:
                continue

        # 2. File path analysis
        for path in file_paths:
            for pattern, tech in self.file_rules.items():
                if pattern in path:
                    return DetectionResult(technology=tech, confidence=0.8, evidence=[f"File pattern match: {path} -> {pattern}"])

        return DetectionResult(technology=Technology.UNKNOWN, confidence=0.0)
