from typing import Dict, Any, Optional
from pydantic import BaseModel

class ExecutionEstimate(BaseModel):
    difficulty: str # low | medium | high
    expected_files_changed: int
    rollback_complexity: str # low | medium | high
    validation_complexity: str # low | medium | high
    business_risk: str # low | medium | high
    estimated_cost: float = 0.0 # e.g. in terms of AI tokens or compute

class RemediationEstimator:
    """
    Estimates the effort and risk associated with a specific strategy.
    Does NOT use AI; uses deterministic mapping based on strategy IDs.
    """
    def __init__(self):
        # Strategy ID -> Estimate mapping
        self.strategy_estimates = {
            "DependencyUpgrade": {
                "difficulty": "low",
                "files": 1,
                "rollback": "low",
                "validation": "medium",
                "risk": "low"
            },
            "DockerImageHardening": {
                "difficulty": "medium",
                "files": 1,
                "rollback": "low",
                "validation": "medium",
                "risk": "medium"
            },
            "TfInfrastructureFix": {
                "difficulty": "high",
                "files": 2,
                "rollback": "medium",
                "validation": "high",
                "risk": "high"
            },
            "SecretRotation": {
                "difficulty": "high",
                "files": 3,
                "rollback": "high",
                "validation": "high",
                "risk": "high"
            }
        }

    async def estimate(self, strategy_id: str) -> ExecutionEstimate:
        """
        Provides an estimate for the given strategy.
        """
        est = self.strategy_estimates.get(strategy_id, {
            "difficulty": "medium",
            "files": 1,
            "rollback": "medium",
            "validation": "medium",
            "risk": "medium"
        })

        return ExecutionEstimate(
            difficulty=est["difficulty"],
            expected_files_changed=est["files"],
            rollback_complexity=est["rollback"],
            validation_complexity=est["validation"],
            business_risk=est["risk"]
        )
