from __future__ import annotations
from typing import Dict, List, Optional, Type
from app.remediation.interfaces.base import IRemediationPlugin, ICapability
from app.utils.logger import logger

class CapabilityRegistry:
    """
    Central hub for discovering and managing remediation capabilities.
    Prevents the Decision Engine from having hardcoded logic for plugin types.
    """
    def __init__(self):
        self._plugins: Dict[str, IRemediationPlugin] = {}
        self._capabilities: Dict[str, ICapability] = {}

    def register_plugin(self, plugin: IRemediationPlugin) -> None:
        """Registers a plugin and its associated capabilities."""
        self._plugins[plugin.plugin_id] = plugin
        for cap_id in plugin.supported_capabilities:
            # In a real impl, plugins would provide the Capability instance
            # For now, we map the capability ID to the plugin that provides it
            self._capabilities[cap_id] = plugin

        logger.info(f"[Remediation] Registered plugin: {plugin.name} ({plugin.plugin_id})")

    def get_plugin(self, plugin_id: str) -> Optional[IRemediationPlugin]:
        return self._plugins.get(plugin_id)

    def get_capability(self, capability_id: str) -> Optional[Any]:
        """Returns the plugin or capability handler for a specific capability."""
        return self._capabilities.get(capability_id)

    def list_all_capabilities(self) -> List[str]:
        """Returns all registered remediation capabilities across the platform."""
        return list(self._capabilities.keys())

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Returns metadata about all registered plugins."""
        return [
            {"id": p.plugin_id, "name": p.name, "capabilities": p.supported_capabilities}
            for p in self._plugins.values()
        ]
