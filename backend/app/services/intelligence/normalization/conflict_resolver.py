from __future__ import annotations
from typing import Any, Dict, Optional, List

class ConflictResolver:
    """
    Resolves discrepancies between multiple providers using deterministic precedence.
    """
    def __init__(self, precedence_list: Optional[List[str]] = None):
        # Default precedence: CISA > NVD > GHSA > OSV > Vendor
        self.precedence = precedence_list or ["cisa", "nvd", "ghsa", "osv", "vendor"]

    def resolve(self, field_name: str, values: List[Dict[str, Any]]) -> Any:
        """
        Resolves the winning value for a field given a list of candidate values
        and their associated provenance.

        values: List of {"value": Any, "provider_id": str}
        """
        if not values:
            return None
        if len(values) == 1:
            return values[0]["value"]

        # Sort based on precedence list
        def get_priority(provider_id: str) -> int:
            try:
                return self.precedence.index(provider_id.lower())
            except ValueError:
                return len(self.precedence)

        sorted_values = sorted(values, key=lambda x: get_priority(x["provider_id"]))

        # The first one in the sorted list is the winner based on precedence
        return sorted_values[0]["value"]
