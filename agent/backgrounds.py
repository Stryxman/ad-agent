"""Traitements de fond (aplat, dégradé linéaire, « mesh ») calculés depuis la palette du brief.

Les couleurs sont calculées ici plutôt qu'en CSS (`color-mix`) : on connaît ainsi chaque couleur
réellement visible (`stops`) et on peut vérifier le contraste du texte sur la pire d'entre elles."""

from __future__ import annotations

from dataclasses import dataclass

from agent.colors import contrast_ratio, mix

KINDS = ("lineaire", "mesh", "uni")
MIN_CONTRAST = 3.0   # WCAG, texte large : même seuil que render.readable_on
DARK, LIGHT = "#111111", "#FFFFFF"


@dataclass(frozen=True)
class Background:
    css: str
    stops: tuple[str, ...]


def build(kind: str, base: str, tint: str, extra: str) -> Background:
    """`base` : couleur de la surface ; `tint` : couleur vers laquelle on teinte ; `extra` : 3e tache du mesh."""
    if kind == "uni":
        return Background(base, (base,))
    if kind == "lineaire":
        end = mix(base, tint, 0.32)
        return Background(f"linear-gradient(160deg, {base} 0%, {end} 100%)", (base, end))
    if kind == "mesh":
        t55, t35, e10 = mix(base, tint, 0.55), mix(base, tint, 0.35), mix(base, extra, 0.10)
        css = (f"radial-gradient(at 12% 8%, {t55} 0, transparent 52%), "
               f"radial-gradient(at 92% 88%, {t35} 0, transparent 50%), "
               f"radial-gradient(at 85% 12%, {e10} 0, transparent 45%), {base}")
        return Background(css, (base, t55, t35, e10))
    raise ValueError(f"traitement de fond inconnu : {kind!r} (attendu : {', '.join(KINDS)})")


def worst_contrast(color: str, bg: Background) -> float:
    return min(contrast_ratio(color, s) for s in bg.stops)


def text_on(bg: Background) -> str:
    """Noir ou blanc : celui dont le contraste sur la pire couleur de la surface est le meilleur."""
    return max((DARK, LIGHT), key=lambda c: worst_contrast(c, bg))


def resolve_kind(cli: str | None, da: str, fmt: str) -> str:
    """Priorité : option CLI, puis DA du brief, puis défaut du format ("auto" = laisser la main)."""
    for choice in (cli, da):
        if choice and choice != "auto":
            return choice
    return fmt


@dataclass(frozen=True)
class Look:
    kind: str
    bg: Background              # surface « fond » (base = bg)
    accent: Background          # surface « accent » (base = accent), pour les canevas couleur d'accent
    on_bg: str                  # texte lisible sur toute la surface fond
    on_accent_surface: str      # texte lisible sur toute la surface accent
    accent_text: str            # l'accent s'il reste lisible sur la surface fond, sinon on_bg
    warnings: tuple[str, ...]


def make_look(kind: str, bg: str, fg: str, accent: str) -> Look:
    warnings: list[str] = []

    def surface(base: str, tint: str, extra: str, name: str) -> tuple[Background, str]:
        b = build(kind, base, tint, extra)
        color = text_on(b)
        worst = worst_contrast(color, b)
        if worst < MIN_CONTRAST and kind != "uni":
            warnings.append(f"fond « {kind} » trop peu contrasté sur la surface {name} "
                            f"({worst:.1f}:1) : repli en aplat")
            b = build("uni", base, tint, extra)
            color = text_on(b)
        return b, color

    bg_s, on_bg = surface(bg, accent, fg, "fond")
    acc_s, on_acc = surface(accent, fg, bg, "accent")
    accent_text = accent if worst_contrast(accent, bg_s) >= MIN_CONTRAST else on_bg
    return Look(kind, bg_s, acc_s, on_bg, on_acc, accent_text, tuple(warnings))
