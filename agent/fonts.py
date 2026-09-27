"""Polices de la DA : fichier local (assets/fonts/) d'abord, puis Google Fonts ; sinon police de secours signalée.

Un fichier local est embarqué en data URI : Firefox refuse une police chargée par file:// depuis un autre
dossier. Côté Google, un lien par famille (et un lien sans graisse, toujours valide) : une famille ou une
graisse introuvable ne casse pas les autres."""

from __future__ import annotations

import base64
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from agent.loader import ROOT

FONTS_DIR = ROOT / "assets" / "fonts"
MIME = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf"}
CSS_FORMAT = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}
GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")

# Les FontFace réellement chargées. Ne pas utiliser document.fonts.check() : il répond vrai pour une
# famille jamais déclarée.
LOADED_FAMILIES_JS = (
    "document.fonts.ready.then(() => [...document.fonts]"
    ".filter(f => f.status === 'loaded').map(f => f.family.replace(/[\"']/g, '')))"
)


def safe_family(name: str) -> str | None:
    """Le nom tel quel s'il ne contient que lettres, chiffres, espaces, tirets ; None sinon (jamais injecté)."""
    name = name.strip()
    return name if _SAFE_NAME.match(name) and name.lower() not in GENERIC else None


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_local(family: str, fonts_dir: Path = FONTS_DIR) -> Path | None:
    if not fonts_dir.is_dir():
        return None
    key = _key(family)
    files = sorted(p for p in fonts_dir.iterdir() if p.suffix.lower() in MIME)
    exact = [p for p in files if _key(p.stem) == key]
    prefixed = [p for p in files if _key(p.stem).startswith(key)]
    return (exact or prefixed or [None])[0]


@dataclass
class FontPlan:
    head: str = ""
    sources: dict[str, str] = field(default_factory=dict)   # famille -> "local" | "google"
    warnings: list[str] = field(default_factory=list)


def resolve(families: Iterable[str], fonts_dir: Path = FONTS_DIR) -> FontPlan:
    plan = FontPlan()
    faces: list[str] = []
    links: list[str] = []
    for raw in families:
        name = safe_family(raw)
        if name is None:
            plan.warnings.append(f"nom de police refusé (caractères non autorisés) : {raw!r}")
            continue
        if name in plan.sources:
            continue
        local = find_local(name, fonts_dir)
        if local:
            ext = local.suffix.lower()
            data = base64.b64encode(local.read_bytes()).decode()
            faces.append(f'@font-face {{ font-family: "{name}"; src: url(data:{MIME[ext]};base64,{data}) '
                         f'format("{CSS_FORMAT[ext]}"); font-weight: 100 900; font-display: block; }}')
            plan.sources[name] = "local"
        else:
            family = quote(name).replace("%20", "+")
            links.append(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={family}&display=swap">')
            links.append(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={family}:wght@700&display=swap">')
            plan.sources[name] = "google"
    parts = (['<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'] + links) if links else []
    if faces:
        parts.append("<style>\n" + "\n".join(faces) + "\n</style>")
    plan.head = "\n".join(parts)
    return plan


def missing(requested: Iterable[str], loaded: Iterable[str]) -> list[str]:
    loaded_keys = {_key(f) for f in loaded}
    return [f for f in requested if _key(f) not in loaded_keys]
