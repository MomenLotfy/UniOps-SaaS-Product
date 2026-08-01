from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# SBOM Format Types
class SBOMFormat(str):
    CycloneDX = "cyclonedx"
    SPDX = "spdx"


# Package Types
class PackageType(str):
    Library = "library"
    Application = "application"
    Framework = "framework"
    Tool = "tool"
    OperatingSystem = "operating-system"
    Container = "container"
    Device = "device"


# SBOM Metadata Schema
class SBOMMetadata(BaseModel):
    sbom_id: str
    sbom_name: str
    timestamp: str
    version: int
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    creators: List[str] = Field(default_factory=list)
    component: Dict[str, Any]


# Package Schema
class SBOMPackage(BaseModel):
    name: str
    version: str
    purl: Optional[str] = None
    cpe: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    supplier: Optional[str] = None
    maintainer: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    download_location: Optional[str] = None
    files_analyzed: bool = False
    external_references: List[Dict[str, Any]] = Field(default_factory=list)
    properties: List[Dict[str, str]] = Field(default_factory=list)


# CycloneDX SBOM Schema
class CycloneDXSBOM(BaseModel):
    bomFormat: str = "CycloneDX"
    specVersion: str = "1.4"
    version: int
    serialNumber: str
    metadata: SBOMMetadata
    components: List[SBOMPackage]
    dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    vulnerabilities: List[Dict[str, Any]] = Field(default_factory=list)
    services: List[Dict[str, Any]] = Field(default_factory=list)


# SPDX SBOM Schema
class SPDXSBOM(BaseModel):
    spdxVersion: str = "SPDX-2.3"
    SPDXID: str
    name: str
    documentNamespace: str
    creationInfo: Dict[str, Any]
    dataLicense: str = "CC0-1.0"
    documentName: str
    documentDescribes: List[str] = Field(default_factory=list)
    packages: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    files: List[Dict[str, Any]] = Field(default_factory=list)
    annotations: List[Dict[str, Any]] = Field(default_factory=list)


# SBOM Response Schema
class SBOMResponse(BaseModel):
    id: str
    tenant_id: str
    repo_id: str
    repo_name: str
    scan_id: Optional[str] = None
    format: str
    component_count: int
    generated_at: str
    generator: str
    created_at: str


# SBOM Detail Response Schema (with full content)
class SBOMDetailResponse(BaseModel):
    id: str
    tenant_id: str
    repo_id: str
    repo_name: str
    scan_id: Optional[str] = None
    format: str
    component_count: int
    content: str  # Full JSON content
    meta: Dict[str, Any]
    generated_at: str
    generator: str
    created_at: str


# SBOM List Query Parameters
class SBOMListFilter(BaseModel):
    repo_id: Optional[str] = None
    format: Optional[str] = None
    min_components: Optional[int] = None
    generator: Optional[str] = None


# SBOM Download Response
class SBOMDownloadResponse(BaseModel):
    filename: str
    content_type: str = "application/json"
    content: str


# Component Analysis Schema
class SBOMComponentAnalysis(BaseModel):
    component_id: str
    name: str
    version: str
    purl: Optional[str] = None
    license: Optional[str] = None
    risk_score: float = 0.0
    vulnerabilities_count: int = 0
    vulnerabilities: List[Dict[str, Any]] = Field(default_factory=list)
    cvss_scores: List[float] = Field(default_factory=list)
    epss_score: Optional[float] = None
    kev: bool = False
    cves: List[str] = Field(default_factory=list)
    dependency_depth: int = 0
    dependency_type: str = "direct"


# Dependency Tree Node
class DependencyTreeNode(BaseModel):
    id: str
    name: str
    version: str
    purl: Optional[str] = None
    parent_id: Optional[str] = None
    depth: int = 0
    children: List[str] = Field(default_factory=list)
    transitive_count: int = 0


# Dependency Tree Response
class DependencyTreeResponse(BaseModel):
    roots: List[DependencyTreeNode]
    nodes: Dict[str, DependencyTreeNode]
    total_packages: int
    depth_max: int


# Enterprise Package Table Row
class EnterprisePackage(BaseModel):
    id: str
    name: str
    version: str
    latest_version: Optional[str] = None
    purl: Optional[str] = None
    cpe: Optional[str] = None
    sha256: Optional[str] = None
    license: Optional[str] = None
    supplier: Optional[str] = None
    maintainer: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    description: Optional[str] = None
    risk_score: float
    vulnerability_count: int
    cvss_max: Optional[float] = None
    epss_score: Optional[float] = None
    kev: bool
    cves: List[str]
    dependency_depth: int
    dependency_type: str
    last_updated: str


# Export Filter
class SBOMExportFilter(BaseModel):
    format: str = Field(default="json", description="Export format: json, cyclonedx, spdx")
    include_vulnerabilities: bool = Field(default=True)
    include_dependencies: bool = Field(default=True)
    date_range: str = Field(default="all")


# Summary Stats
class SBOMSummaryStats(BaseModel):
    total_sboms: int
    total_components: int
    unique_packages: int
    by_format: Dict[str, int] = Field(default_factory=dict)
    by_generator: Dict[str, int] = Field(default_factory=dict)
    by_repo: Dict[str, int] = Field(default_factory=dict)
    average_components: float = 0.0
