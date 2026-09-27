"""Textes de publication Meta (texte principal, titre) : règles communes et rédacteur hors ligne.

Règles (docs/regles-et-design.md) : titre <= 27 caractères, rejeté au-delà, jamais tronqué ; texte principal
<= 150 caractères, avertissement sous 50. Le rédacteur hors ligne n'assemble que des phrases entières du
brief ; un témoignage réel est cité tel quel, jamais réécrit."""

from __future__ import annotations

import re

from agent.checks import allowed_numbers, check_text, normalize, numbers
from agent.schemas import Brief, PublicationCopy

HEADLINE_MAX = 27
PRIMARY_MAX = 150
PRIMARY_MIN = 50
MAX_ITEMS = 3


def sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if not text or text[-1] in ".!?…»" else text + "."


def assemble(parts: list[str], limit: int = PRIMARY_MAX) -> str:
    """Ajoute des phrases entières tant qu'elles tiennent ; une phrase trop longue est sautée, jamais coupée,
    et une phrase déjà présente (accroche identique à un bénéfice) n'est pas répétée."""
    out = ""
    for part in parts:
        s = sentence(part)
        if s and s not in out and len((out + " " + s).strip()) <= limit:
            out = (out + " " + s).strip()
    return out


def filter_texts(texts: list[str], max_len: int, brief: Brief, allowed: set[str], label: str,
                 min_len: int | None = None) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for t in texts:
        t = re.sub(r"\s+", " ", t or "").strip()
        if not t or normalize(t) in seen:
            continue
        seen.add(normalize(t))
        reason = check_text(t, max_len, brief, allowed)
        if reason:
            warnings.append(f"{label} rejeté ({reason}) : {t}")
            continue
        if min_len and len(t) < min_len:
            warnings.append(f"{label} court ({len(t)} < {min_len} caractères recommandés) : {t}")
        kept.append(t)
        if len(kept) == MAX_ITEMS:
            break
    return kept, warnings


def testimonial_text(brief: Brief) -> str | None:
    """Le premier avis réel, cité mot pour mot avec son auteur, s'il tient dans un texte principal."""
    if not brief.testimonials:
        return None
    t = brief.testimonials[0]
    text = f"« {t.text} »" + (f" — {t.author}" if t.author else "")
    if len(text) > PRIMARY_MAX:
        return None
    # un avis réel peut citer ses propres chiffres ; les promesses interdites restent interdites
    return None if check_text(text, PRIMARY_MAX, brief, allowed_numbers(brief) | numbers(text)) else text


def offline_publication(brief: Brief, hook: str) -> tuple[PublicationCopy, list[str]]:
    allowed = allowed_numbers(brief) | numbers(hook)
    heads_raw = [h for h in (hook, brief.offer or "", brief.product.name) if h and len(h) <= HEADLINE_MAX]
    heads, warnings = filter_texts(heads_raw, HEADLINE_MAX, brief, allowed, "titre")
    if not heads:
        warnings.append(f"aucun titre de {HEADLINE_MAX} caractères maximum dans le brief")

    prim_raw = [assemble([hook, *brief.product.benefits]),
                assemble([brief.product.description, brief.offer or ""])]
    prims, w = filter_texts(prim_raw, PRIMARY_MAX, brief, allowed, "texte principal", min_len=PRIMARY_MIN)
    warnings += w
    testimonial = testimonial_text(brief)
    if testimonial and testimonial not in prims:
        prims = prims[:MAX_ITEMS - 1] + [testimonial]
    if not prims:
        warnings.append("aucun texte principal constructible à partir du brief")
    return PublicationCopy(primary_texts=prims, headlines=heads), warnings
