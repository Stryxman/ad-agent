"""Étape 7 : rendu HTML (Jinja2) puis capture PNG (Playwright, optionnel)."""

from __future__ import annotations

import base64
import mimetypes
import sys
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from agent.backgrounds import Look, make_look
from agent.colors import contrast_color, contrast_ratio, readable_on  # réexportés (tests, gabarits)
from agent.fonts import LOADED_FAMILIES_JS, missing, safe_family
from agent.schemas import AdFormat, Brief, Variant

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

RATIO_SIZES = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1920, 1080)}
DEFAULT_PALETTE = ["#F4F1EC", "#222222", "#B08D6E"]
SCALE = 4 / 3  # mise en page sur 1080 px de large, capturée en 1440 px (Meta : 1440 x 1800 en 4:5)
# haut/bas en fraction de la hauteur, côtés en fraction de la largeur ; voir docs/regles-et-design.md
SAFE_ZONES = {"9:16": (0.14, 0.06, 0.35, 0.06)}
DEFAULT_SAFE = 0.07  # fraction de la largeur, sur les 4 bords (valeur historique des gabarits)

_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))


def available_templates() -> set[str]:
    """Les formats qui ont un gabarit de rendu (fichiers `<format_id>.html`, hors `_base.html`)."""
    return {p.stem for p in TEMPLATES_DIR.glob("*.html") if not p.name.startswith("_")}


@lru_cache(maxsize=256)
def _data_uri(path: Path) -> str | None:
    """Encodée une seule fois par chemin : un run appelle `render_html` une fois par (variante, ratio),
    mais les 4 images (produit/scène/avant/après) sont les mêmes fichiers à chaque appel."""
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def capture_size(ratio: str) -> tuple[int, int]:
    w, h = RATIO_SIZES[ratio]
    return round(w * SCALE), round(h * SCALE)


def safe_zone_px(ratio: str) -> tuple[float, float, float, float]:
    """Marges (haut, droite, bas, gauche) en px de mise en page, où ne doivent aller ni texte ni logo."""
    w, h = RATIO_SIZES[ratio]
    if ratio in SAFE_ZONES:
        top, right, bottom, left = SAFE_ZONES[ratio]
        return round(top * h, 1), round(right * w, 1), round(bottom * h, 1), round(left * w, 1)
    m = round(DEFAULT_SAFE * w, 1)
    return m, m, m, m


def palette_of(brief: Brief) -> tuple[str, str, str]:
    """(fond, texte, accent) du brief, complétés par la palette par défaut si le brief en donne moins de 3."""
    palette = list(brief.da.palette) + DEFAULT_PALETTE[len(brief.da.palette):]
    return palette[0], palette[1], palette[2]


def _context(fmt: AdFormat, zones: dict, brief: Brief, ratio: str, product_image: Path | None,
             scene_image: Path | None, before_image: Path | None, after_image: Path | None,
             look: Look | None, font_head: str, safe_overlay: bool) -> dict:
    w, h = RATIO_SIZES[ratio]
    bg, fg, accent = palette_of(brief)
    look = look or make_look(fmt.fond, bg, fg, accent)
    fonts = brief.da.fonts
    return {
        "w": w, "h": h, "u": w / 100, "ratio": ratio, "fmt_id": fmt.id,
        "bg": bg, "fg": fg, "accent": accent, "fond": look.kind,
        # surfaces calculées (fond et accent) et textes lisibles sur chacune de leurs couleurs
        "bg_surface_css": look.bg.css, "accent_surface_css": look.accent.css,
        "on_bg": look.on_bg, "on_accent_surface": look.on_accent_surface, "accent_text": look.accent_text,
        # blocs posés sur une couleur pure de la palette
        "on_accent": contrast_color(accent), "on_fg": contrast_color(fg),
        # noms venus du brief : seuls les noms sûrs atteignent le CSS, sinon police de secours
        "font_display": (safe_family(fonts[0]) or "Georgia") if fonts else "Georgia",
        "font_body": (safe_family(fonts[1]) or "Helvetica") if len(fonts) > 1 else "Helvetica",
        "font_head": Markup(font_head), "safe_overlay": safe_overlay, "safe": safe_zone_px(ratio),
        "brand": brief.brand or brief.product.name, "product_name": brief.product.name,
        # produit détouré (fond uni/dégradé) vs. photo d'origine (scène plein cadre, fond conservé)
        "product_img": _data_uri(product_image) if product_image else None,
        "scene_img": _data_uri(scene_image) if scene_image else None,
        # avant/après : jamais détourés, jamais générés — la photo réelle telle quelle, ou rien
        "before_img": _data_uri(before_image) if before_image else None,
        "after_img": _data_uri(after_image) if after_image else None,
        "z": zones,
    }


def render_html(variant: Variant, fmt: AdFormat, zones: dict, brief: Brief, ratio: str, out_dir: Path,
                product_image: Path | None = None, scene_image: Path | None = None,
                before_image: Path | None = None, after_image: Path | None = None, *,
                look: Look | None = None, font_head: str = "", safe_overlay: bool = False) -> Path:
    html = _env.get_template(f"{fmt.id}.html").render(
        **_context(fmt, zones, brief, ratio, product_image, scene_image, before_image, after_image,
                   look, font_head, safe_overlay)
    )
    path = out_dir / f"{variant.id}_{fmt.id}_{ratio.replace(':', 'x')}.html"
    path.write_text(html, encoding="utf-8")
    return path


BROWSERS = ("chromium", "firefox", "webkit")


def screenshot_all(jobs: list[tuple[str, str, Path]], browser_name: str = "chromium",
                   fonts: tuple[str, ...] = ()) -> tuple[dict[tuple[str, str], Path], list[str] | None]:
    """Capture chaque HTML en PNG (échelle 4/3) et renvoie aussi les polices demandées non chargées
    (None si rien n'a pu être vérifié : Playwright ou navigateur absent)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright n'est pas installé : HTML généré sans PNG "
              "(pip install -e \".[render]\" puis playwright install <navigateur>).", file=sys.stderr)
        return {}, None
    out: dict[tuple[str, str], Path] = {}
    absent: set[str] = set()
    checked = False
    try:
        with sync_playwright() as p:
            browser = getattr(p, browser_name).launch()
            for variant_id, ratio, html_path in jobs:
                w, h = RATIO_SIZES[ratio]
                page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=SCALE)
                page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
                if fonts:
                    absent.update(missing(fonts, page.evaluate(LOADED_FAMILIES_JS)))
                    checked = True
                png = html_path.with_suffix(".png")
                page.screenshot(path=str(png))
                page.close()
                out[(variant_id, ratio)] = png
            browser.close()
    except Exception as e:  # navigateur non installé, etc.
        print(f"Capture PNG impossible ({e.__class__.__name__}) : HTML généré sans PNG. "
              f"Le navigateur est-il installé ? (playwright install {browser_name})", file=sys.stderr)
    return out, (sorted(absent) if checked or not fonts else None)
