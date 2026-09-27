"""Étape 7 : rendu HTML (Jinja2) puis capture PNG (Playwright, optionnel)."""

from __future__ import annotations

import base64
import mimetypes
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agent.schemas import AdFormat, Brief, Variant

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

RATIO_SIZES = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1920, 1080)}
DEFAULT_PALETTE = ["#F4F1EC", "#222222", "#B08D6E"]

_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))


def available_templates() -> set[str]:
    """Les formats qui ont un gabarit de rendu (fichiers `<format_id>.html`, hors `_base.html`)."""
    return {p.stem for p in TEMPLATES_DIR.glob("*.html") if not p.name.startswith("_")}


def contrast_color(hex_color: str) -> str:
    """Noir ou blanc, selon la luminosité du fond, pour garder un texte lisible."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    chan = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        chan.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2]


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(color: str, bg: str, min_ratio: float = 3.0) -> str:
    """La couleur telle quelle si elle reste lisible sur ce fond (WCAG, texte large), sinon noir/blanc."""
    return color if contrast_ratio(color, bg) >= min_ratio else contrast_color(bg)


def _data_uri(path: Path) -> str | None:
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _context(fmt: AdFormat, zones: dict[str, str], brief: Brief, ratio: str, product_image: Path | None,
            scene_image: Path | None) -> dict:
    w, h = RATIO_SIZES[ratio]
    palette = list(brief.da.palette) + DEFAULT_PALETTE[len(brief.da.palette):]
    bg, fg, accent = palette[0], palette[1], palette[2]
    fonts = brief.da.fonts
    return {
        "w": w, "h": h, "u": w / 100, "ratio": ratio, "fmt_id": fmt.id,
        "bg": bg, "fg": fg, "accent": accent,
        "on_bg": contrast_color(bg), "on_accent": contrast_color(accent),
        "accent_text": readable_on(accent, bg),
        "font_display": fonts[0] if fonts else "Georgia", "font_body": fonts[1] if len(fonts) > 1 else "Helvetica",
        "brand": brief.brand or brief.product.name, "product_name": brief.product.name,
        # produit détouré (fond uni/dégradé) vs. photo d'origine (scène plein cadre, fond conservé)
        "product_img": _data_uri(product_image) if product_image else None,
        "scene_img": _data_uri(scene_image) if scene_image else None,
        "z": zones,
    }


def render_html(variant: Variant, fmt: AdFormat, zones: dict[str, str], brief: Brief, ratio: str, out_dir: Path,
                product_image: Path | None = None, scene_image: Path | None = None) -> Path:
    html = _env.get_template(f"{fmt.id}.html").render(
        **_context(fmt, zones, brief, ratio, product_image, scene_image)
    )
    path = out_dir / f"{variant.id}_{fmt.id}_{ratio.replace(':', 'x')}.html"
    path.write_text(html, encoding="utf-8")
    return path


BROWSERS = ("chromium", "firefox", "webkit")


def screenshot_all(jobs: list[tuple[str, str, Path]], browser_name: str = "chromium") -> dict[tuple[str, str], Path]:
    """Capture chaque HTML (variante, ratio, chemin) en PNG à la taille de son ratio.
    Sans Playwright ou sans navigateur, prévient et renvoie ce qui a pu être capturé."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright n'est pas installé : HTML généré sans PNG "
              "(pip install -e \".[render]\" puis playwright install <navigateur>).", file=sys.stderr)
        return {}
    out: dict[tuple[str, str], Path] = {}
    try:
        with sync_playwright() as p:
            browser = getattr(p, browser_name).launch()
            for variant_id, ratio, html_path in jobs:
                w, h = RATIO_SIZES[ratio]
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(html_path.resolve().as_uri())
                png = html_path.with_suffix(".png")
                page.screenshot(path=str(png))
                page.close()
                out[(variant_id, ratio)] = png
            browser.close()
    except Exception as e:  # navigateur non installé, etc.
        print(f"Capture PNG impossible ({e.__class__.__name__}) : HTML généré sans PNG. "
              f"Le navigateur est-il installé ? (playwright install {browser_name})", file=sys.stderr)
    return out
