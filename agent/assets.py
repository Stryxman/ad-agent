"""Étape 2 : analyse des assets produit.

Détermine si une image est déjà isolée (fond uni ou transparent) et, sinon, la détoure automatiquement
avec `rembg` (traitement local, gratuit, sans clé ni abonnement — l'API publique de Canva ne l'expose pas
aux développeurs, seulement dans son éditeur). Le détourage n'est appelé QUE si l'image ne semble pas
déjà isolée, et son résultat est mis en cache par empreinte du fichier source : il n'est calculé qu'une fois.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from agent.schemas import AssetAnalysis

CACHE_DIR = Path(__file__).resolve().parent.parent / "assets" / ".cache"
BORDER_FRACTION = 0.06        # épaisseur du bandeau de bord analysé
UNIFORMITY_THRESHOLD = 0.90   # part du bord qui doit être proche de la couleur dominante
COLOR_TOLERANCE = 18          # écart de couleur toléré (par canal, sur 255)


def _border_pixels(img: Image.Image) -> list[tuple[int, int, int]]:
    rgb = img.convert("RGB")
    w, h = rgb.size
    bw, bh = max(1, int(w * BORDER_FRACTION)), max(1, int(h * BORDER_FRACTION))
    px = rgb.load()
    pixels = []
    for x in range(w):
        for y in list(range(0, bh)) + list(range(h - bh, h)):
            pixels.append(px[x, y])
    for y in range(h):
        for x in list(range(0, bw)) + list(range(w - bw, w)):
            pixels.append(px[x, y])
    return pixels


def looks_isolated(img: Image.Image) -> bool:
    """Vrai si l'image a déjà un fond transparent, ou un bord de couleur quasi uniforme (packshot studio)."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        alpha = img.convert("RGBA").split()[-1]
        if alpha.getextrema()[0] < 250:  # une partie du bord est déjà transparente
            return True
    border = _border_pixels(img)
    if not border:
        return False
    n = len(border)
    r = sorted(p[0] for p in border)[n // 2]
    g = sorted(p[1] for p in border)[n // 2]
    b = sorted(p[2] for p in border)[n // 2]
    close = sum(
        1 for (pr, pg, pb) in border
        if abs(pr - r) <= COLOR_TOLERANCE and abs(pg - g) <= COLOR_TOLERANCE and abs(pb - b) <= COLOR_TOLERANCE
    )
    return (close / n) >= UNIFORMITY_THRESHOLD


# Modèle figé explicitement : le défaut de rembg (2.0.x) est "bria-rmbg", sous licence NON commerciale
# (accord payant requis auprès de BRIA AI) et ~1 Go. "u2net" est Apache 2.0 (réutilisable commercialement),
# ~176 Mo, téléchargé une seule fois. Ne jamais appeler remove()/new_session() sans préciser ce nom.
MODEL_NAME = "u2net"
_session = None


def _remove_background(path: Path) -> bytes:
    """Détourage local via rembg/u2net (modèle exécuté sur la machine, aucun envoi réseau après le premier
    téléchargement du modèle)."""
    global _session
    try:
        from rembg import new_session, remove
    except ImportError as e:
        raise RuntimeError(
            'Détourage indisponible : pip install -e ".[assets]" (installe rembg, local et gratuit).'
        ) from e
    if _session is None:
        _session = new_session(MODEL_NAME)
    return remove(path.read_bytes(), session=_session)


def ensure_isolated(path: Path, cache_dir: Path = CACHE_DIR) -> AssetAnalysis:
    """Renvoie le chemin à utiliser pour le rendu (l'original si déjà isolé, sinon une version détourée
    mise en cache) et un compte-rendu de l'analyse."""
    if not path.is_file():
        return AssetAnalysis(path=str(path), isolated=False, action="introuvable",
                             used_path=str(path), note="fichier absent")

    with Image.open(path) as img:
        if looks_isolated(img):
            return AssetAnalysis(path=str(path), isolated=True, action="aucune",
                                 used_path=str(path), note="fond déjà uniforme ou transparent")

    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    cached = cache_dir / f"{digest}.png"
    if not cached.is_file():
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            cached.write_bytes(_remove_background(path))
        except RuntimeError as e:
            return AssetAnalysis(path=str(path), isolated=False, action="echec",
                                 used_path=str(path), note=str(e))
    return AssetAnalysis(path=str(path), isolated=False, action="detoure",
                         used_path=str(cached), note=f"détouré et mis en cache ({cached.name})")
