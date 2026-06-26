from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# --- Session & State ---

class PaginationState(BaseModel):
    page: int = 1
    page_size: int = 50
    offset: int = 0
    total_count: Optional[int] = None

class SortingState(BaseModel):
    sort_by: str = "created_at"
    direction: str = "desc" # 'asc' or 'desc'

class InvestigationSessionSchema(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    name: Optional[str] = None
    current_context: Dict[str, Any]
    pagination_state: Optional[PaginationState] = None
    sorting_state: Optional[SortingState] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

class InvestigationSessionCreate(BaseModel):
    name: Optional[str] = None
    current_context: Dict[str, Any] = Field(default_factory=dict)

class InvestigationSessionUpdate(BaseModel):
    name: Optional[str] = None
    current_context: Optional[Dict[str, Any]] = None
    pagination_state: Optional[PaginationState] = None
    sorting_state: Optional[SortingState] = None
    is_active: Optional[bool] = None

# --- Bookmarks & Saved Queries ---

class InvestigationBookmarkSchema(BaseModel):
    id: str
    session_id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    label: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime

class InvestigationBookmarkCreate(BaseModel):
    entity_type: str
    entity_id: str
    label: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None

class SavedQuerySchema(BaseModel):
    id: str
    session_id: Optional[str] = None
    tenant_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    query_params: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class SavedQueryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    query_params: Dict[str, Any]

# --- Search & Query ---

class InvestigationQuery(BaseModel):
    """
    The deterministic query definition.
    Used by QueryPlanner and QueryExecutor.
    """
    target_entity: str # 'findings', 'assets', 'repositories', 'packages', etc.
    filters: Dict[str, Any] = Field(default_factory=dict)
    search_term: Optional[str] = None
    limit: int = 50
    offset: int = 0
    sort_by: str = "risk_score"
    sort_direction: str = "desc"

class InvestigationResult(BaseModel):
    results: List[Any]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    execution_time_ms: float
    context_id: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    entity_types: List[str] = ["all"] # 'CVE', 'Asset', 'Repository', etc.
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 50
    offset: int = 0

class SearchResponse(BaseModel):
    hits: List[Dict[str, Any]]
    total_hits: int
    suggestions: List[str] = []
    execution_time_ms: float

# --- Timeline & Correlation ---

class TimelineRequest(BaseModel):
    entity_id: str
    entity_type: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event_types: List[str] = ["all"]

class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    entity_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TimelineResponse(BaseModel):
    entity_id: str
    events: List[TimelineEvent]
    summary: Dict[str, Any]

class CorrelationRequest(BaseModel):
    source_entity_id: str
    source_entity_type: str
    target_entity_id: Optional[str] = None
    target_entity_type: Optional[str] = None
    depth: int = 3

class CorrelationLink(BaseModel):
    target_id: str
    target_type: str
    relationship: str
    depth: int
    evidence: List[str]

class CorrelationResponse(BaseModel):
    source_id: str
    correlations: List[CorrelationLink]
    summary: Dict[str, Any]

# --- Metadata & History ---

class SearchHistorySchema(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    query_text: str
    query_type: str
    result_count: Optional[int] = None
    execution_time_ms: Optional[float] = None
    created_at: datetime

class TimelineMetadataSchema(BaseModel):
    id: str
    tenant_id: str
    entity_id: str
    entity_type: str
    marker_label: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    comment: Optional[str] = None
    created_at: datetime

class TimelineMetadataCreate(BaseModel):
    marker_label: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    comment: Optional[str] = None

class CorrelationMetadataSchema(BaseModel):
    id: str
    tenant_id: str
    source_entity_id: str
    source_entity_type: str
    target_entity_id: str
    target_entity_type: str
    correlation_type: str
    confidence_score: float
    evidence: Optional[List[str]] = None
    created_at: datetime
