from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class MLPredictionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    model_name: str
    model_version: str = "1.0.0"
    prediction_type: Optional[str] = None
    input_data: dict = {}
    output_data: dict = {}
    confidence: Optional[float] = None
    predicted_at: datetime
    target_date: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class MLRecommendationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: int = 5
    confidence: float
    impact: str = "medium"
    effort: str = "medium"
    status: str = "pending"
    action: Optional[str] = None
    created_at: datetime


class MLPatternResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    name: str
    pattern_type: Optional[str] = None
    description: Optional[str] = None
    confidence: float
    frequency: Optional[str] = None
    data: dict = {}
    created_at: datetime


class MLCorrelationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    metric_a: str
    metric_b: str
    correlation_score: float
    method: str = "pearson"
    insight: Optional[str] = None
    created_at: datetime


class MLInsightRequest(BaseModel):
    model_type: str
    input_data: dict
    options: dict = {}


class MLInsightResponse(BaseModel):
    model_type: str
    result: Any
    confidence: Optional[float] = None
    generated_at: datetime


class ModelStatus(BaseModel):
    name: str
    version: str
    trained: bool
    last_trained_at: Optional[datetime] = None
    accuracy: Optional[float] = None
    features_count: Optional[int] = None
