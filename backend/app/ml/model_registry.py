"""Model Registry — manages versioning, storage, and lifecycle of ML models."""
import os
import json
from datetime import datetime, timezone
from typing import Optional

from app.utils.logger import logger

MODELS_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


class ModelRegistry:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or MODELS_BASE_DIR
        os.makedirs(self.base_dir, exist_ok=True)
        self._registry_file = os.path.join(self.base_dir, "registry.json")
        self._registry: dict = self._load_registry()

    def _load_registry(self) -> dict:
        if os.path.exists(self._registry_file):
            try:
                with open(self._registry_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_registry(self) -> None:
        try:
            with open(self._registry_file, "w") as f:
                json.dump(self._registry, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save model registry: {e}")

    def get_model_path(self, model_name: str, version: str = "latest") -> str:
        if version == "latest":
            versions = self._registry.get(model_name, {}).get("versions", [])
            version = versions[-1] if versions else "1.0.0"
        return os.path.join(self.base_dir, f"{model_name}_{version.replace('.', '_')}.pkl")

    def register(self, model_name: str, version: str, metadata: Optional[dict] = None) -> dict:
        if model_name not in self._registry:
            self._registry[model_name] = {"versions": [], "current": None}

        entry = {
            "version": version,
            "path": self.get_model_path(model_name, version),
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        versions = self._registry[model_name]["versions"]
        existing = next((i for i, v in enumerate(versions) if v["version"] == version), None)
        if existing is not None:
            versions[existing] = entry
        else:
            versions.append(entry)

        self._registry[model_name]["current"] = version
        self._save_registry()
        logger.info(f"Model registered: {model_name} v{version}")
        return entry

    def get_info(self, model_name: str) -> Optional[dict]:
        return self._registry.get(model_name)

    def list_models(self) -> list[dict]:
        result = []
        for name, info in self._registry.items():
            current_version = info.get("current")
            path = self.get_model_path(name, current_version) if current_version else None
            result.append({
                "name": name,
                "current_version": current_version,
                "versions": [v["version"] for v in info.get("versions", [])],
                "file_exists": os.path.exists(path) if path else False,
                "file_size_kb": round(os.path.getsize(path) / 1024, 1) if path and os.path.exists(path) else None,
            })
        return result

    def is_available(self, model_name: str) -> bool:
        info = self.get_info(model_name)
        if not info:
            path = os.path.join(self.base_dir, f"{model_name}.pkl")
            return os.path.exists(path)
        current = info.get("current")
        if not current:
            return False
        path = self.get_model_path(model_name, current)
        return os.path.exists(path)

    def delete_version(self, model_name: str, version: str) -> bool:
        path = self.get_model_path(model_name, version)
        if os.path.exists(path):
            os.remove(path)
        if model_name in self._registry:
            self._registry[model_name]["versions"] = [
                v for v in self._registry[model_name]["versions"] if v["version"] != version
            ]
            self._save_registry()
        return True


model_registry = ModelRegistry()
