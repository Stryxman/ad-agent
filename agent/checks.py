"""Contrôles communs aux textes produits (zones de l'image et textes de publication) : longueur, promesses
interdites, chiffres absents du brief."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from agent.schemas import Brief


def normalize(text: str) -> str:
    """Minuscules sans accents, pour comparer des textes (promesses interdites, etc.)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", text)}


def brief_facts(brief: Brief) -> dict[str, Any]:
    """Ce que le modèle a le droit de savoir : pas de chemins de fichiers ni de couleurs."""
    return {
        "campagne": brief.name, "marque": brief.brand, "niche": brief.niche.value,
        "objectif": brief.objective.value, "langue": brief.language,
        "produit": {
            "nom": brief.product.name, "description": brief.product.description,
            "benefices": brief.product.benefits, "prix": brief.product.price,
            "ancien_prix": brief.product.compare_at_price,
        },
        "audience": brief.audience, "offre": brief.offer,
        "ton": brief.da.tone, "a_faire": brief.da.dos, "a_eviter": brief.da.donts,
        "hook_impose": brief.hook_idea, "promesses_interdites": brief.forbidden_claims,
    }


def allowed_numbers(brief: Brief) -> set[str]:
    """Les nombres que le brief autorise dans un texte (prix, durées, pourcentages...)."""
    return numbers(json.dumps(brief_facts(brief), ensure_ascii=False))


def check_text(text: str, max_chars: int | None, brief: Brief, allowed_numbers: set[str]) -> str | None:
    """Renvoie le motif de rejet d'un texte produit, ou None s'il est acceptable."""
    if not text.strip():
        return "texte vide"
    if max_chars is not None and len(text) > max_chars:
        return f"trop long ({len(text)} > {max_chars} caractères)"
    norm = normalize(text)
    for claim in brief.forbidden_claims:
        if normalize(claim) in norm:
            return f"contient la promesse interdite « {claim} »"
    invented = numbers(text) - allowed_numbers
    if invented:
        return f"chiffre absent du brief : {sorted(invented)}"
    return None
