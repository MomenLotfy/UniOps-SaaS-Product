from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
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

class ProvenanceMetadata(BaseModel):
    """Tracks the origin and trust of a specific piece of intelligence."""
    provider_id: str
    provider_version: str
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    trust_score: float = Field(1.0, ge=0.0, le=1.0)
    merge_version: Optional[str] = None

class CanonicalEcosystem(BaseModel):
    """Standardized software ecosystem."""
    id: str # npm, pypi, maven, etc.
    name: str
    canonical_url: Optional[str] = None

class CanonicalVendor(BaseModel):
    """Standardized vendor identity."""
    id: str
    name: str
    website: Optional[str] = None

class CanonicalProduct(BaseModel):
    """Standardized product identity."""
    id: str
    name: str
    vendor_id: Optional[str] = None

class CanonicalVersion(BaseModel):
    """Normalized version string."""
    original: str
    normalized: str
    ecosystem: str
    semantic_version: Optional[str] = None # x.y.z

class CanonicalVersionRange(BaseModel):
    """Normalized version range."""
    original: str
    normalized: str
    ecosystem: str
    min_version: Optional[str] = None
    max_version: Optional[str] = None

class CanonicalPatch(BaseModel):
    """Specific patch information."""
    patch_id: str
    commit_hash: Optional[str] = None
    url: str
    description: Optional[str] = None
    provenance: ProvenanceMetadata

class CanonicalFixRecommendation(BaseModel):
    """Guidance for fixing the vulnerability."""
    recommendation: str
    fixed_versions: List[str] = []
    patch: Optional[CanonicalPatch] = None
    provenance: ProvenanceMetadata

class CanonicalExploitStatus(BaseModel):
    """Current state of exploit availability."""
    status: str # PoC, Functional, Weaponized, Wild
    last_seen: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    provenance: ProvenanceMetadata

class CanonicalTimelineEvent(BaseModel):
    """Event markers in the vulnerability lifecycle."""
    event_type: str # discovered, published, fixed, exploited
    timestamp: datetime
    description: Optional[str] = None
    provenance: ProvenanceMetadata

class CanonicalSource(BaseModel):
    """Origin of the intelligence."""
    id: str
    name: str
    type: str # official, community, vendor
    url: Optional[str] = None

class CanonicalAdvisory(BaseModel):
    """Standardized security advisory."""
    advisory_id: str
    title: str
    description: str
    published_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    references: List[str] = []
    provenance: ProvenanceMetadata

class CanonicalThreatIntelligence(BaseModel):
    """Broader threat context."""
    threat_actor: Optional[str] = None
    campaign: Optional[str] = None
    targets: List[str] = []
    severity_score: Optional[float] = None
    provenance: ProvenanceMetadata

class CanonicalIntelligenceMetadata(BaseModel):
    """Metadata about the normalization and merge process."""
    normalization_version: str
    merge_timestamp: datetime = Field(default_factory=datetime.utcnow)
    quality_score: float = Field(1.0, ge=0.0, le=1.0)
    providers_merged: List[str] = []
    conflicts_resolved: int = 0

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

    # Expanded Canonical Models
    advisories: List[CanonicalAdvisory] = []
    timeline: List[CanonicalTimelineEvent] = []
    threat_intel: Optional[CanonicalThreatIntelligence] = None

    # Provenance for the primary fields
    provenance: Dict[str, ProvenanceMetadata] = {}

class CanonicalPackage(BaseModel):
    """Unified software package identity (PURL based)."""
    purl: str = Field(..., description="Package URL (e.g., pkg:npm/express@4.18.2)")
    name: str
    version: CanonicalVersion
    ecosystem: CanonicalEcosystem
    vendor: Optional[CanonicalVendor] = None
    product: Optional[CanonicalProduct] = None

    provenance: Dict[str, ProvenanceMetadata] = {}

class CanonicalExploit(BaseModel):
    """Intelligence on exploit availability."""
    exploit_id: Optional[str] = None
    status: CanonicalExploitStatus
    source: CanonicalSource
    url: Optional[str] = None

    provenance: Dict[str, ProvenanceMetadata] = {}

class CanonicalWeakness(BaseModel):
    """Mapping to Common Weakness Enumeration (CWE)."""
    cwe_id: str # CWE-79
    name: str
    description: str
    severity: Optional[RiskLevel] = None
    provenance: ProvenanceMetadata

class CanonicalAttackPattern(BaseModel):
    """Mapping to Common Attack Pattern Enumeration and Classification (CAPEC)."""
    capec_id: str # CAPEC-123
    name: str
    description: str
    technique: Optional[str] = None
    provenance: ProvenanceMetadata

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
    provenance: ProvenanceMetadata

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

class ProviderCapabilitySchema(BaseModel):
    """API Response for provider capabilities."""
    provider_id: str
    capability_type: str
    is_supported: bool
    confidence_level: float

class ProviderDetailsSchema(BaseModel):
    """API Response for provider detailed metadata."""
    provider_id: str
    name: str
    description: Optional[str]
    version: str
    provider_type: str
    is_active: bool
    capabilities: List[ProviderCapabilitySchema]
    config: Dict[str, Any]
    health: Optional[ProviderHealthSchema] = None
