"""Chargement et validation des fichiers YAML (briefs et formats)."""

from __future__ import annotations

from pathlib import Path

import yaml

from agent.schemas import AdFormat, Brief

ROOT = Path(__file__).resolve().parent.parent
FORMATS_DIR = ROOT / "formats"
BRIEFS_DIR = ROOT / "briefs"


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: le fichier YAML doit contenir un objet à la racine")
    return data


def load_brief(path: Path) -> Brief:
    return Brief.model_validate(_read_yaml(path))


def load_format(path: Path) -> AdFormat:
    return AdFormat.model_validate(_read_yaml(path))


def load_all_formats(directory: Path = FORMATS_DIR) -> list[AdFormat]:
    """Charge tous les formats. Les fichiers commençant par `_` (templates) sont ignorés."""
    formats = [load_format(p) for p in sorted(directory.glob("*.yaml")) if not p.name.startswith("_")]
    ids = [f.id for f in formats]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"ids de formats dupliqués: {sorted(dupes)}")
    return formats
