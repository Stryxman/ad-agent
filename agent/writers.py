"""Rédacteurs : produisent les angles (étape 3) et les textes des zones (étape 5).

`Writer` est l'interface ; `OfflineWriter` est une implémentation déterministe, sans modèle de langage,
qui reformule uniquement ce que contient le brief. Elle sert de base testable et de solution de repli.
Une implémentation adossée à Claude viendra s'y brancher sans changer le pipeline.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from agent.schemas import Angle, AdFormat, Brief, HookType, Zone

CTA = {
    "fr": {"default": "Découvrir", "offer": "J'en profite"},
    "en": {"default": "Shop now", "offer": "Get the offer"},
}

# Rôles de zones qui ne reçoivent jamais de texte généré
NON_TEXT_ROLES = {"image", "logo"}


class WriterError(RuntimeError):
    """Erreur du rédacteur (clé absente, réseau, réponse inexploitable), avec un message lisible."""


def normalize(text: str) -> str:
    """Minuscules sans accents, pour comparer des textes (promesses interdites, etc.)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def fit_text(text: str, max_chars: int | None) -> str:
    """Tronque proprement à la limite de la zone, à la frontière d'un mot, avec une ellipse."""
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars is None or len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (cut or text[: max_chars - 1]) + "…"


class Writer(Protocol):
    name: str

    def propose_angles(self, brief: Brief) -> list[Angle]: ...

    def write_copy(self, brief: Brief, hook: str, fmt: AdFormat) -> tuple[dict[str, str], list[str]]:
        """Renvoie les textes par zone et la liste des avertissements."""
        ...


class OfflineWriter:
    name = "offline"

    def propose_angles(self, brief: Brief) -> list[Angle]:
        angles: list[Angle] = []
        if brief.hook_idea:
            angles.append(
                Angle(id="a_brief", hook_type=HookType.benefit, hooks=[brief.hook_idea],
                      rationale="Hook imposé par le brief.")
            )
        angles.append(
            Angle(id="a_benefit", hook_type=HookType.benefit, hooks=list(brief.product.benefits),
                  rationale="Bénéfices concrets listés dans le brief.")
        )
        if brief.offer:
            angles.append(
                Angle(id="a_offer", hook_type=HookType.offer, hooks=[brief.offer],
                      rationale="Offre commerciale indiquée dans le brief.")
            )
        if brief.testimonials:
            angles.append(
                Angle(id="a_proof", hook_type=HookType.social_proof,
                      hooks=[t.text for t in brief.testimonials],
                      rationale="Avis clients réels fournis dans le brief.")
            )
        return angles

    def write_copy(self, brief: Brief, hook: str, fmt: AdFormat) -> tuple[dict[str, str], list[str]]:
        lang = CTA.get(brief.language, CTA["fr"])
        testimonial = next((t for t in brief.testimonials if t.text == hook), None)
        zones: dict[str, str] = {}
        for z in fmt.zones:
            text = self._zone_text(brief, hook, testimonial, z, lang)
            if text:
                zones[z.id] = fit_text(text, z.max_chars)
        return zones, []

    @staticmethod
    def _zone_text(brief: Brief, hook: str, testimonial, zone: Zone, lang: dict[str, str]) -> str | None:
        if zone.role in NON_TEXT_ROLES:
            return None
        if zone.id == "price_old":
            return brief.product.compare_at_price
        if zone.id == "price_new":
            return brief.product.price
        if zone.id == "quote":
            return hook
        if zone.id == "author":
            return f"— {testimonial.author}" if testimonial and testimonial.author else None
        if zone.id == "stars":
            return "★" * testimonial.rating if testimonial and testimonial.rating else None
        if zone.id == "title":
            return None  # titre d'accroche facultatif : demande un vrai rédacteur
        if zone.id == "product_name":
            return brief.product.name  # identifiant factuel : jamais reformulé
        if zone.id == "price_line":
            return f"à partir de {brief.product.price}" if brief.product.price else None
        if zone.id == "offer_line":
            return brief.offer
        if zone.role == "headline":
            return hook
        if zone.role == "subhead":
            return brief.product.name
        if zone.role == "cta":
            return lang["offer"] if brief.offer else lang["default"]
        return None  # badge, list, etc. : pas de contenu sans modèle de langage
