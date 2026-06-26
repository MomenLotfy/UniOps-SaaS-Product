from __future__ import annotations
from typing import Any, Dict, Optional
from ..base import ProviderMapper

class CisaKevMapper(ProviderMapper):
    def map_vulnerability(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None # Architecture stub

    def map_package(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None # Architecture stub

    def map_exploit(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None # Architecture stub
