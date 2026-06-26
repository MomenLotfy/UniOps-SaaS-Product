from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.schemas.intelligence import (
    CanonicalCVE, CanonicalPackage, CanonicalExploit,
    ProvenanceMetadata, CanonicalIntelligenceMetadata
)
from .conflict_resolver import ConflictResolver

class MergeEngine:
    """
    Aggregates intelligence from multiple providers into a single canonical object.
    Handles deduplication, conflict resolution, and provenance tracking.
    """
    def __init__(self, conflict_resolver: ConflictResolver):
        self.conflict_resolver = conflict_resolver

    async def merge_vulnerabilities(self, cve_id: str, provider_fragments: List[Dict[str, Any]]) -> CanonicalCVE:
        """
        Merges multiple provider fragments into a single CanonicalCVE.
        """
        if not provider_fragments:
            raise ValueError(f"No fragments provided to merge for {cve_id}")

        # 1. Collect candidate values for each field
        candidates = {}
        all_providers = []

        for frag in provider_fragments:
            pid = frag.get("provider_id")
            all_providers.append(pid)
            for field, value in frag.items():
                if field == "provider_id": continue
                if field not in candidates:
                    candidates[field] = []
                candidates[field].append({"value": value, "provider_id": pid})

        # 2. Resolve conflicts for primary fields
        resolved_data = {}
        for field, values in candidates.items():
            if field == "provenance":
                # Provenance is a special map we build
                continue
            resolved_data[field] = self.conflict_resolver.resolve(field, values)

        # 3. Build final provenance map
        # For each resolved field, track which provider won
        final_provenance = {}
        for field, values in candidates.items():
            if field == "provenance": continue
            winner = self.conflict_resolver.resolve(field, values)
            # Find which provider provided this winning value
            winning_prov = next(
                (v["provider_id"] for v in values if v["value"] == winner),
                "unknown"
            )
            final_provenance[field] = ProvenanceMetadata(
                provider_id=winning_prov,
                provider_version="1.0.0", # In real impl, fetched from registry
                trust_score=1.0
            )

        # 4. Handle lists (References, Advisories, etc.) by deduplicating
        # These are merged rather than resolved via conflict
        resolved_data["references"] = self._merge_lists(candidates.get("references", []))

        # Create the final CanonicalCVE
        return CanonicalCVE(
            cve_id=cve_id,
            cvss_score=resolved_data.get("cvss_score"),
            cvss_vector=resolved_data.get("cvss_vector"),
            severity=resolved_data.get("severity", "MEDIUM"),
            description=resolved_data.get("description", ""),
            published_at=resolved_data.get("published_at"),
            last_modified=resolved_data.get("last_modified"),
            references=resolved_data["references"],
            provenance=final_provenance
        )

    def _merge_lists(self, candidates: List[Dict[str, Any]]) -> List[Any]:
        """Deduplicates and merges lists of items from all providers."""
        merged = set()
        for entry in candidates:
            val = entry["value"]
            if isinstance(val, list):
                merged.update(val)
            elif val:
                merged.add(val)
        return list(merged)
