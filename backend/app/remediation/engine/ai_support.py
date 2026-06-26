from __future__ import annotations
from typing import Any, Dict, Optional, List
from pydantic import BaseModel
from app.services.copilot_service import CopilotService
from app.utils.logger import logger

class AIDecisionInsight(BaseModel):
    """AI-generated insight to support the decision process."""
    summary: str
    root_cause_analysis: Optional[str] = None
    alternative_strategies: List[str] = []
    risk_explanation: Optional[str] = None
    confidence_score: float = 0.0

class DecisionSupportAI:
    """
    AI-powered assistant specifically for the Decision Engine.
    Provides insights, explanations, and strategy suggestions without executing code.
    """
    def __init__(self, copilot_service: CopilotService):
        self.copilot_service = copilot_service

    async def get_planning_insights(self, context: Any) -> Optional[AIDecisionInsight]:
        """
        Queries the AI to provide context and reasoning for a proposed remediation.
        """
        logger.info(f"[DecisionSupportAI] Requesting insights for finding {context.finding_id}")

        # We use a specific system prompt for planning insights
        prompt = (
            f"Analyze this security finding: {context.finding_id}. "
            f"Technology: {context.metadata.get('technology', 'unknown')}. "
            f"Category: {context.metadata.get('category', 'unknown')}. "
            "Provide: 1. A human-readable summary of the fix. 2. Root cause analysis. "
            "3. Alternative remediation strategies. 4. Explanation of the business risk. "
            "Format as JSON."
        )

        try:
            # We simulate the AI call using the existing CopilotService but without a full conversation
            # In a real impl, this would be a specialized prompt to the LLM.
            response = await self.copilot_service.chat(
                tenant_id=context.tenant_id,
                user_id="system_decision_engine",
                conversation_id="planning_session",
                message=prompt
            )

            # Since our simulated Copilot returns a string, we'd normally parse JSON here.
            # For the framework implementation, we return a structured mock insight based on the prompt.
            return AIDecisionInsight(
                summary=f"Suggested fix for {context.finding_id} involving configuration hardening.",
                root_cause_analysis="Misconfigured security headers allowing potential XSS.",
                alternative_strategies=["Manual review", "WAF Rule implementation"],
                risk_explanation="High potential for data theft if exploited in production.",
                confidence_score=0.85
            )
        except Exception as e:
            logger.error(f"[DecisionSupportAI] Insight generation failed: {e}")
            return None
