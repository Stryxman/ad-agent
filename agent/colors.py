"""Couleurs : conversion hex, contraste WCAG, mélange perceptuel en OKLab.

Utilisé par le rendu et les fonds : les couleurs visibles sont calculées ici, en Python, pour que le
contraste du texte reste vérifiable (voir backgrounds.py)."""

from __future__ import annotations

from collections.abc import Iterable


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def to_hex(rgb: Iterable[float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def contrast_color(hex_color: str) -> str:
    """Noir ou blanc, selon la luminosité du fond, pour garder un texte lisible."""
    r, g, b = _rgb(hex_color)
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"


def _to_linear(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


def _luminance(hex_color: str) -> float:
    r, g, b = (_to_linear(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(color: str, bg: str, min_ratio: float = 3.0) -> str:
    """La couleur telle quelle si elle reste lisible sur ce fond (WCAG, texte large), sinon noir/blanc."""
    return color if contrast_ratio(color, bg) >= min_ratio else contrast_color(bg)


def _oklab(hex_color: str) -> tuple[float, float, float]:
    r, g, b = (_to_linear(c) for c in _rgb(hex_color))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _from_oklab(L: float, a: float, b: float) -> str:
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return to_hex(_from_linear(c) for c in (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    ))


def mix(a: str, b: str, t: float) -> str:
    """Mélange perceptuel (OKLab) : t=0 donne a, t=1 donne b ; évite les teintes grises du mélange RGB."""
    A, B = _oklab(a), _oklab(b)
    return _from_oklab(*(x + (y - x) * t for x, y in zip(A, B)))
