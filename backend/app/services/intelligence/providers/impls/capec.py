from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class CapecProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="capec",
            name="Common Attack Pattern Enumeration",
            version="1.0.0",
            provider_type="official",
            supported_types=['CAPEC'],
            supported_lookups={'CAPEC'}
        )
