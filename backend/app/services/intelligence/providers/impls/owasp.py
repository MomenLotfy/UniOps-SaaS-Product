from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class OwaspProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="owasp",
            name="OWASP Top 10 / Guides",
            version="1.0.0",
            provider_type="community",
            supported_types=['CWE', 'CAPEC'],
            supported_lookups={'CWE', 'CAPEC'}
        )
