"""
Decision Strategy Registry.

Plugin registry — the authoritative extension point for new strategies.
The engine itself never references StrategyType enum values directly;
it always asks the registry.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.platform.thread_safe_registry import ThreadSafeRegistry

from ..constants import StrategyType
from .strategy_interfaces import IStrategyDescriptor, IStrategyRegistry


class DecisionStrategyRegistry(ThreadSafeRegistry[StrategyType, IStrategyDescriptor], IStrategyRegistry):
    """
    In-memory registry of strategy descriptors.

    Thread-safe (Sprint 3 R36): inherited ``threading.RLock``-guarded
    store.  Registrations are still expected to happen at process
    start (in ``bootstrap_default_strategies``); reads are concurrent
    across both asyncio tasks and Celery worker threads.
    """

    # ── IStrategyRegistry ────────────────────────────────────────────────
    def register(self, strategy_type: StrategyType, descriptor: IStrategyDescriptor) -> None:
        descriptor.strategy_type = strategy_type
        super().register(strategy_type, descriptor)

    def get(self, strategy_type: StrategyType):
        return super().get(strategy_type)

    def all(self) -> Dict[StrategyType, IStrategyDescriptor]:
        return super().all()

    def discover(self, decision: Any, context: Any) -> List[IStrategyDescriptor]:
        out: List[IStrategyDescriptor] = []
        for d in self.values():
            try:
                if d.applicable(decision, context):
                    out.append(d)
            except Exception:  # pragma: no cover — defensive
                # A buggy descriptor must not kill the pipeline.
                continue
        return out


# ─── Built-in Descriptors ────────────────────────────────────────────────────
# 17 strategies as required by the spec.  Each descriptor is pure data +
# predicates; it never opens DB connections or performs I/O.

class _BaseStrategy(IStrategyDescriptor):
    """Base class providing common predicate helpers."""

    strategy_type: StrategyType  # set by registry.register()

    def _ctx(self, context: Any) -> dict:
        """Return the raw context dict in a uniform way."""
        if context is None:
            return {}
        if hasattr(context, "raw_data"):
            return context.raw_data or {}
        if isinstance(context, dict):
            return context
        return {}

    def _has_patch(self, ctx: dict) -> bool:
        return bool(ctx.get("fixed_version") or ctx.get("patch_url"))

    def _has_repo(self, ctx: dict) -> bool:
        return bool(ctx.get("asset_id") or ctx.get("repo_id"))

    def _has_asset(self, ctx: dict) -> bool:
        return bool(ctx.get("asset_id"))

    def _platform_supported(self, ctx: dict) -> bool:
        from ..constants import SUPPORTED_PLATFORMS
        p = (ctx.get("platform") or ctx.get("environment") or "").lower()
        return not p or p in SUPPORTED_PLATFORMS

    def _pkg_manager_supported(self, ctx: dict) -> bool:
        from ..constants import SUPPORTED_PACKAGE_MANAGERS
        pm = (ctx.get("package_manager") or "").lower()
        return not pm or pm in SUPPORTED_PACKAGE_MANAGERS


class PatchExistingVersionDescriptor(_BaseStrategy):
    strategy_type = StrategyType.PATCH_EXISTING_VERSION

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        # Only when a fixed_version is advertised for the vulnerable pkg
        return bool(ctx.get("fixed_version"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [
            {"type": "PATCH_AVAILABLE",
             "is_met": self._has_patch(ctx),
             "details": f"fixed_version={ctx.get('fixed_version')!r}"},
            {"type": "REPOSITORY_PRESENT",
             "is_met": self._has_repo(ctx),
             "details": f"asset_id={ctx.get('asset_id')!r}"},
        ]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "MAINTENANCE_WINDOW", "value": "preferred"}]


class UpgradePackageDescriptor(_BaseStrategy):
    strategy_type = StrategyType.UPGRADE_PACKAGE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("package_name")) and bool(ctx.get("fixed_version"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [
            {"type": "PACKAGE_KNOWN",     "is_met": bool(ctx.get("package_name"))},
            {"type": "TARGET_VERSION_KNOWN", "is_met": bool(ctx.get("fixed_version"))},
            {"type": "PKG_MANAGER_SUPPORTED", "is_met": self._pkg_manager_supported(ctx)},
        ]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "TEST_SUITE_PASS", "value": "required"}]


class DowngradePackageDescriptor(_BaseStrategy):
    strategy_type = StrategyType.DOWNGRADE_PACKAGE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        # Downgrade is a last resort — only if a safe version is known
        return bool(ctx.get("safe_version"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [
            {"type": "SAFE_VERSION_KNOWN", "is_met": bool(ctx.get("safe_version"))},
            {"type": "PKG_MANAGER_SUPPORTED", "is_met": self._pkg_manager_supported(ctx)},
        ]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "REGRESSION_TEST", "value": "required"}]


class ReplaceDependencyDescriptor(_BaseStrategy):
    strategy_type = StrategyType.REPLACE_DEPENDENCY

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("replacement_package"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "REPLACEMENT_KNOWN", "is_met": bool(ctx.get("replacement_package"))}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "API_COMPATIBILITY", "value": "verified"}]


class DisableFeatureDescriptor(_BaseStrategy):
    strategy_type = StrategyType.DISABLE_FEATURE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("feature_flag"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "FEATURE_FLAG_PRESENT", "is_met": bool(ctx.get("feature_flag"))}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "FEATURE_OWNER_APPROVAL", "value": "required"}]


class ConfigurationChangeDescriptor(_BaseStrategy):
    strategy_type = StrategyType.CONFIGURATION_CHANGE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("config_key"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "CONFIG_KEY_PRESENT", "is_met": bool(ctx.get("config_key"))}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "CONFIG_BACKUP", "value": "required"}]


class InfrastructureChangeDescriptor(_BaseStrategy):
    strategy_type = StrategyType.INFRASTRUCTURE_CHANGE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("infra_target"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [
            {"type": "INFRA_TARGET_KNOWN", "is_met": bool(ctx.get("infra_target"))},
            {"type": "PLATFORM_SUPPORTED", "is_met": self._platform_supported(ctx)},
        ]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "CHANGE_WINDOW", "value": "required"}]


class ContainerUpdateDescriptor(_BaseStrategy):
    strategy_type = StrategyType.CONTAINER_UPDATE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("image")) and bool(ctx.get("fixed_version"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [
            {"type": "IMAGE_KNOWN",         "is_met": bool(ctx.get("image"))},
            {"type": "TARGET_TAG_KNOWN",    "is_met": bool(ctx.get("fixed_version"))},
            {"type": "PLATFORM_SUPPORTED",  "is_met": self._platform_supported(ctx)},
        ]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "IMAGE_REBUILD", "value": "required"}]


class OsPackageUpdateDescriptor(_BaseStrategy):
    strategy_type = StrategyType.OS_PACKAGE_UPDATE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("package_name")) and bool(ctx.get("fixed_version")) and \
               (ctx.get("package_manager") in {"apt", "yum", "dnf", "apk", "brew", "choco"})

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [
            {"type": "OS_PKG_KNOWN",     "is_met": bool(ctx.get("package_name"))},
            {"type": "OS_PKG_FIXED",     "is_met": bool(ctx.get("fixed_version"))},
            {"type": "OS_PKG_MGR_SUPP",  "is_met": self._pkg_manager_supported(ctx)},
        ]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "OS_REBOOT_OK", "value": "preferred"}]


class ImageReplacementDescriptor(_BaseStrategy):
    strategy_type = StrategyType.IMAGE_REPLACEMENT

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("image")) and bool(ctx.get("replacement_image"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [
            {"type": "IMAGE_KNOWN",        "is_met": bool(ctx.get("image"))},
            {"type": "REPLACEMENT_KNOWN", "is_met": bool(ctx.get("replacement_image"))},
        ]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "CONTAINER_REBUILD", "value": "required"}]


class SecretRotationDescriptor(_BaseStrategy):
    strategy_type = StrategyType.SECRET_ROTATION

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("secret_id"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "SECRET_ID_KNOWN", "is_met": bool(ctx.get("secret_id"))}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "ROTATION_RUNBOOK", "value": "required"}]


class CertificateRotationDescriptor(_BaseStrategy):
    strategy_type = StrategyType.CERTIFICATE_ROTATION

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("certificate_id"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "CERT_ID_KNOWN", "is_met": bool(ctx.get("certificate_id"))}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "CA_COORDINATION", "value": "required"}]


class PolicyChangeDescriptor(_BaseStrategy):
    strategy_type = StrategyType.POLICY_CHANGE

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return bool(ctx.get("policy_id"))

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "POLICY_ID_KNOWN", "is_met": bool(ctx.get("policy_id"))}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "POLICY_OWNER_APPROVAL", "value": "required"}]


class TemporaryMitigationDescriptor(_BaseStrategy):
    strategy_type = StrategyType.TEMPORARY_MITIGATION

    def applicable(self, decision: Any, context: Any) -> bool:
        # Always applicable as a fallback mitigation.
        return True

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "ASSET_PRESENT", "is_met": self._has_asset(ctx)}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "MITIGATION_EXPIRY", "value": "required"}]


class ManualReviewRequiredDescriptor(_BaseStrategy):
    strategy_type = StrategyType.MANUAL_REVIEW_REQUIRED

    def applicable(self, decision: Any, context: Any) -> bool:
        # Always a valid fallback when no automated path exists.
        return True

    def hard_constraints(self, decision: Any, context: Any):
        return [{"type": "ASSET_PRESENT", "is_met": True}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "REVIEWER_ASSIGNED", "value": "required"}]


class VendorPatchRequiredDescriptor(_BaseStrategy):
    strategy_type = StrategyType.VENDOR_PATCH_REQUIRED

    def applicable(self, decision: Any, context: Any) -> bool:
        ctx = self._ctx(context)
        return ctx.get("vendor_patch_required") is True

    def hard_constraints(self, decision: Any, context: Any):
        ctx = self._ctx(context)
        return [{"type": "VENDOR_FLAG_SET", "is_met": ctx.get("vendor_patch_required") is True}]

    def base_requirements(self, decision: Any, context: Any):
        return [{"type": "VENDOR_CONTACT", "value": "required"}]


class NoActionDescriptor(_BaseStrategy):
    strategy_type = StrategyType.NO_ACTION

    def applicable(self, decision: Any, context: Any) -> bool:
        # NO_ACTION is the universal safety net — always applicable.
        return True

    def hard_constraints(self, decision: Any, context: Any):
        # NO_ACTION always satisfies its constraints.
        return [{"type": "TRIVIAL", "is_met": True}]

    def base_requirements(self, decision: Any, context: Any):
        return []


# ─── Bootstrap ───────────────────────────────────────────────────────────────

def bootstrap_default_strategies(registry: DecisionStrategyRegistry) -> None:
    """
    Register the 17 canonical strategies required by the spec.

    New strategies added later MUST NOT touch this function — they call
    `registry.register(strategy_type, descriptor)` from their own module.
    """
    pairs = [
        (StrategyType.PATCH_EXISTING_VERSION, PatchExistingVersionDescriptor),
        (StrategyType.UPGRADE_PACKAGE, UpgradePackageDescriptor),
        (StrategyType.DOWNGRADE_PACKAGE, DowngradePackageDescriptor),
        (StrategyType.REPLACE_DEPENDENCY, ReplaceDependencyDescriptor),
        (StrategyType.DISABLE_FEATURE, DisableFeatureDescriptor),
        (StrategyType.CONFIGURATION_CHANGE, ConfigurationChangeDescriptor),
        (StrategyType.INFRASTRUCTURE_CHANGE, InfrastructureChangeDescriptor),
        (StrategyType.CONTAINER_UPDATE, ContainerUpdateDescriptor),
        (StrategyType.OS_PACKAGE_UPDATE, OsPackageUpdateDescriptor),
        (StrategyType.IMAGE_REPLACEMENT, ImageReplacementDescriptor),
        (StrategyType.SECRET_ROTATION, SecretRotationDescriptor),
        (StrategyType.CERTIFICATE_ROTATION, CertificateRotationDescriptor),
        (StrategyType.POLICY_CHANGE, PolicyChangeDescriptor),
        (StrategyType.TEMPORARY_MITIGATION, TemporaryMitigationDescriptor),
        (StrategyType.MANUAL_REVIEW_REQUIRED, ManualReviewRequiredDescriptor),
        (StrategyType.VENDOR_PATCH_REQUIRED, VendorPatchRequiredDescriptor),
        (StrategyType.NO_ACTION, NoActionDescriptor),
    ]
    for st, cls in pairs:
        registry.register(st, cls())
