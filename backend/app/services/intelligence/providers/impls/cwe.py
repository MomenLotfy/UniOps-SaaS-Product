from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class CweProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="cwe",
            name="Common Weakness Enumeration",
            version="1.0.0",
            provider_type="official",
            supported_types=['CWE'],
            supported_lookups={'CWE'}
        )
