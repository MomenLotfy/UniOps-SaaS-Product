from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class EpssProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="epss",
            name="Exploit Prediction Scoring System",
            version="1.0.0",
            provider_type="official",
            supported_types=['EPSS'],
            supported_lookups={'CVE'}
        )
