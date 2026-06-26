from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class OsvProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="osv",
            name="Open Source Vulnerabilities",
            version="1.0.0",
            provider_type="community",
            supported_types=['CVE', 'PURL'],
            supported_lookups={'CVE', 'PURL'}
        )
