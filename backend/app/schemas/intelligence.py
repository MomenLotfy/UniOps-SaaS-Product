from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"

class CanonicalCVE(BaseModel):
    """Standardized Vulnerability data (CVE)."""
    cve_id: str = Field(..., description="The CVE ID (e.g., CVE-2024-1234)")
    cvss_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    cvss_vector: Optional[str] = None
    severity: RiskLevel
    description: str
    published_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    references: List[str] = []

class CanonicalPackage(BaseModel):
    """Unified software package identity (PURL based)."""
    purl: str = Field(..., description="Package URL (e.g., pkg:npm/express@4.18.2)")
    name: str
    version: str
    ecosystem: str # npm, pypi, maven, etc.
    vendor: Optional[str] = None

class CanonicalExploit(BaseModel):
    """Intelligence on exploit availability."""
    exploit_id: Optional[str] = None
    maturity: str # PoC, Functional, Weaponized, Wild
    source: str # Metasploit, CISA KEV, etc.
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    url: Optional[str] = None

class CanonicalWeakness(BaseModel):
    """Mapping to Common Weakness Enumeration (CWE)."""
    cwe_id: str # CWE-79
    name: str
    description: str
    severity: Optional[RiskLevel] = None

class CanonicalAttackPattern(BaseModel):
    """Mapping to Common Attack Pattern Enumeration and Classification (CAPEC)."""
    capec_id: str # CAPEC-123
    name: str
    description: str
    technique: Optional[str] = None

class CanonicalRisk(BaseModel):
    """Calculated business risk for a specific finding."""
    score: float = Field(..., ge=0.0, le=100.0)
    level: RiskLevel
    factors: Dict[str, Any] # e.g., {"exploitability": 0.8, "impact": 0.9}
    confidence: ConfidenceLevel

class CanonicalRemediationReference(BaseModel):
    """Standardized link to fixes and advisories."""
    ref_id: str
    type: str # advisory, patch, guide, blog
    url: str
    title: str
    is_official: bool = False

class EnrichedFinding(BaseModel):
    """
    The ultimate output of the Intelligence Enrichment Engine.
    Combines raw scanner data with canonical intelligence.
    """
    finding_id: str
    tenant_id: str

    # Intelligence Data
    vulnerability: Optional[CanonicalCVE] = None
    package: Optional[CanonicalPackage] = None
    exploit: Optional[CanonicalExploit] = None
    weakness: Optional[CanonicalWeakness] = None
    attack_pattern: Optional[CanonicalAttackPattern] = None

    # Calculated Risk
    risk: CanonicalRisk

    # Remediation Guidance
    remediation_refs: List[CanonicalRemediationReference] = []
    fix_available: bool = False
    patched_versions: List[str] = []

    # Metadata
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    providers_used: List[str] = []
    last_enriched_at: datetime = Field(default_factory=datetime.utcnow)

class ProviderHealthSchema(BaseModel):
    """API Response for provider health."""
    provider_id: str
    name: str
    status: str
    latency_ms: Optional[float] = None
    last_check_at: datetime
