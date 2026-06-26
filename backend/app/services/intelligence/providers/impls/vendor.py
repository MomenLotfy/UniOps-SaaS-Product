from __future__ import annotations
from typing import Any, Dict, Optional
from .base_stub import BaseStubProvider

class VendorAdvisoryProvider(BaseStubProvider):
    def __init__(self):
        super().__init__(
            provider_id="vendor",
            name="Generic Vendor Advisory",
            version="1.0.0",
            provider_type="vendor",
            supported_types=['CVE', 'VULN'],
            supported_lookups={'CVE'}
        )
