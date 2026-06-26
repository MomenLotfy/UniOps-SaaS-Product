from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.utils.logger import logger

class EntityResolver:
    """
    Implements deterministic entity resolution to merge duplicates across providers.
    """
    def resolve_id(self, entity_type: str, identifiers: Dict[str, Any]) -> str:
        """
        Generates a canonical ID based on the entity type and key identifiers.
        """
        if entity_type == "CVE":
            # Use the CVE-ID as canonical
            return f"canonical:cve:{identifiers.get('cve_id', 'unknown').lower()}"

        if entity_type == "Package":
            # Use PURL as canonical
            return f"canonical:pkg:{identifiers.get('purl', 'unknown').lower()}"

        if entity_type == "Repository":
            # Use tenant:repo_name
            return f"canonical:repo:{identifiers.get('tenant_id')}:{identifiers.get('repo_id', 'unknown')}"

        # Fallback to a simple hash of the identifiers
        import hashlib
        id_str = str(sorted(identifiers.items()))
        return f"canonical:{entity_type}:{hashlib.sha256(id_str.encode()).hexdigest()[:16]}"
