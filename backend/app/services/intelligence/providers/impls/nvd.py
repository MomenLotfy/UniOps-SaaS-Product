from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class NvdProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="nvd",
            name="National Vulnerability Database",
            version="1.0.0",
            provider_type="official",
            supported_types=['CVE', 'CWE'],
            supported_lookups={'CVE'}
        )
