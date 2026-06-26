from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class CisaKevProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="cisa",
            name="CISA Known Exploited Vulnerabilities",
            version="1.0.0",
            provider_type="official",
            supported_types=['CVE'],
            supported_lookups={'CVE'}
        )
