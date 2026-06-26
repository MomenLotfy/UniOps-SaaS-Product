from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.schemas.intelligence import CanonicalRemediationReference, ProvenanceMetadata

class ReferenceResolver:
    """
    Standardizes security references, assigning types and trust levels.
    """
    def __init__(self):
        # Trust levels for different reference types
        self.trust_levels = {
            "official_advisory": 1.0,
            "security_blog": 0.6,
            "patch_commit": 0.9,
            "documentation": 0.7,
            "exploit_db": 0.8
        }

    def resolve_reference(self, url: str, provider_id: str, provider_version: str) -> CanonicalRemediationReference:
        """
        Analyzes a URL and resolves it into a CanonicalRemediationReference.
        """
        ref_type = self._infer_type(url)
        trust = self.trust_levels.get(ref_type, 0.5)

        return CanonicalRemediationReference(
            ref_id=f"ref_{hash(url)}",
            type=ref_type,
            url=url,
            title=self._infer_title(url),
            is_official=ref_type == "official_advisory",
            provenance=ProvenanceMetadata(
                provider_id=provider_id,
                provider_version=provider_version,
                trust_score=trust
            )
        )

    def _infer_type(self, url: str) -> str:
        """Heuristic to determine reference type from URL."""
        url = url.lower()
        if "cve.mitre.org" in url or "nvd.nist.gov" in url:
            return "official_advisory"
        if "github.com" in url and "commits" in url:
            return "patch_commit"
        if "exploit-db.com" in url:
            return "exploit_db"
        if "medium.com" in url or "blog" in url:
            return "security_blog"
        return "documentation"

    def _infer_title(self, url: str) -> str:
        """Heuristic to create a title from a URL."""
        return url.split('/')[-1] or url
