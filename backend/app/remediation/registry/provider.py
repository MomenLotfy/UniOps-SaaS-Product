from app.remediation.registry.registry import CapabilityRegistry

# Singleton instance of the CapabilityRegistry
# This ensures that all parts of the application (API, DecisionEngine, etc.)
# share the same set of registered remediation plugins.
registry = CapabilityRegistry()

def get_remediation_registry() -> CapabilityRegistry:
    """Returns the global remediation registry instance."""
    return registry
