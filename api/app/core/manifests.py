"""Honeypot manifest loading.

Manifests live under ``MANIFESTS_DIR`` as ``<name>/manifest.yaml`` plus any
config template referenced by ``config.template`` (e.g. cowrie's cowrie.cfg).
The controller resolves a manifest (and inlines the config template content)
into a deploy command for the agent, so the agent needs nothing on disk.
"""
import logging
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings

logger = logging.getLogger(__name__)


def manifest_path(name: str) -> Path:
    # Guard against path traversal in the manifest name.
    safe = Path(name).name
    return Path(settings.manifests_dir) / safe / "manifest.yaml"


def load_manifest(name: str) -> dict[str, Any]:
    path = manifest_path(name)
    if not path.exists():
        raise FileNotFoundError(f"manifest '{name}' not found at {path}")
    with path.open() as fh:
        manifest = yaml.safe_load(fh)

    # Inline the config template content so the agent can render + mount it.
    config = manifest.get("config")
    if config and config.get("template"):
        template_path = path.parent / Path(config["template"]).name
        if template_path.exists():
            config["template_content"] = template_path.read_text()
        else:
            logger.warning("Config template %s missing for manifest %s", template_path, name)
    return manifest


def list_manifests() -> list[str]:
    base = Path(settings.manifests_dir)
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "manifest.yaml").exists())
