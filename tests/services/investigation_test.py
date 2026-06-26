import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.investigation.engine import InvestigationEngine
from app.schemas.investigation import InvestigationQuery, SearchRequest, CorrelationRequest
from app.services.graph.repository import GraphRepository

@pytest.mark.asyncio
async def test_investigation_query_flow():
    """
    Test the full deterministic flow: Query -> Plan -> Optimize -> Execute.
    """
    mock_db = AsyncMock(spec=AsyncSession)
    engine = InvestigationEngine(mock_db)

    # Define a query for critical findings
    query = InvestigationQuery(
        target_entity="findings",
        filters={"risk_score": {"op": "gt", "val": 9.0}},
        search_term="RCE"
    )

    result = await engine.run_query(query)

    assert result.results is not None
    assert result.execution_time_ms >= 0
    assert result.total_count >= 0

@pytest.mark.asyncio
async def test_deterministic_search():
    """
    Verify that the SearchEngine returns results for a given term.
    """
    mock_db = AsyncMock(spec=AsyncSession)
    engine = InvestigationEngine(mock_db)

    # Register a mock entity
    class MockModel:
        def __init__(self, id, name):
            self.id = id
            self.name = name

    engine.search_engine.register_entity_type("CVE", MockModel, ["id", "name"])

    request = SearchRequest(query="CVE-2024", entity_types=["CVE"])
    # We mock the db execution for search
    mock_db.execute.return_value = MagicMock(scalars=lambda: [MockModel("CVE-2024-1", "RCE Bug")])

    response = await engine.run_search(request)

    assert len(response.hits) == 1
    assert response.hits[0]["entity_id"] == "CVE-2024-1"

@pytest.mark.asyncio
async def test_correlation_discovery():
    """
    Verify that the CorrelationEngine finds linked entities.
    """
    mock_db = AsyncMock(spec=AsyncSession)
    engine = InvestigationEngine(mock_db)

    # Mock the graph repository to return a relationship
    class MockRel:
        def __init__(self, target_id, rel_type):
            self.target_id = target_id
            self.relationship_type = rel_type
            self.target_type = "Asset"

    engine.correlation_engine.repo.get_relationships = AsyncMock(
        return_value=[MockRel("asset-1", "AFFECTS")]
    )

    request = CorrelationRequest(
        source_entity_id="cve-1",
        source_entity_type="CVE"
    )

    response = await engine.run_correlation(request)

    assert len(response.correlations) == 1
    assert response.correlations[0].target_id == "asset-1"
    assert response.correlations[0].relationship == "AFFECTS"
