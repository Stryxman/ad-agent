"""Rédacteur adossé à Claude : propose les angles (étape 3) et écrit les textes des zones (étape 5).

Principes de conception :
- Sorties structurées : on passe un schéma Pydantic à l'API et on récupère un objet validé, jamais du texte libre à analyser.
- Le modèle n'écrit que ce qui est créatif (accroches, sous-titres, appels à l'action). Les prix, les avis clients
  et leur signature restent déterministes : ils viennent du brief tels quels.
- Chaque texte du modèle est revérifié par du code (longueur, promesses interdites, chiffres inventés) ;
  s'il échoue, on retombe sur le texte du brief et un avertissement est consigné.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

from pydantic import BaseModel

from agent.schemas import AdFormat, Angle, Brief, HookType, PublicationCopy
from agent.checks import brief_facts, check_text, normalize  # réexportés (tests)
from agent.checks import allowed_numbers, numbers as _numbers
from agent.publication import (
    HEADLINE_MAX, MAX_ITEMS, PRIMARY_MAX, PRIMARY_MIN, filter_texts, is_testimonial, offline_publication,
    testimonial_text,
)
from agent.writers import NON_TEXT_ROLES, OfflineWriter, WriterError

DEFAULT_MODEL = "claude-opus-5"

# Zones dont le contenu ne doit jamais être écrit par le modèle
FIXED_ZONES = {
    "quote", "author", "stars", "price_old", "price_new", "product_name", "price_line", "offer_line",
    "disclaimer", "before_label", "after_label",  # texte légal et métadonnées d'asset : jamais réécrits
}
# Rôles que le modèle peut rédiger ("list" = plusieurs lignes courtes, ex. les symptômes d'une infographie)
CREATIVE_ROLES = {"headline", "subhead", "cta", "badge", "list"}

SYSTEM = """Tu es directeur de création, spécialisé dans les publicités statiques pour les réseaux sociaux.

Règles impératives :
- Tu n'utilises que les faits du brief. Tu n'inventes ni chiffre, ni statistique, ni prix, ni avis, ni promesse.
- Tu respectes la langue, le ton et les consignes de direction artistique du brief.
- Tu n'emploies jamais les promesses interdites du brief, ni leurs formulations proches.
- Tes textes sont courts, concrets, sans jargon ni superlatifs vides. Une idée par texte.
- Tu respectes strictement la longueur maximale de chaque zone (en caractères)."""


# ------------------------------------------------------------ schémas des réponses


class AngleDraft(BaseModel):
    hook_type: Literal["benefit", "offer", "problem_solution", "curiosity", "before_after"]
    hooks: list[str]
    rationale: str


class AnglesDraft(BaseModel):
    angles: list[AngleDraft]


class ZoneDraft(BaseModel):
    zone_id: str
    text: str


class CopyDraft(BaseModel):
    zones: list[ZoneDraft]


class PublicationDraft(BaseModel):
    primary_texts: list[str]
    headlines: list[str]


# --------------------------------------------------------------------- le rédacteur


class ClaudeWriter:
    name = "claude"

    def __init__(self, client: Any = None, model: str | None = None) -> None:
        if client is None:
            try:
                import anthropic
            except ImportError as e:
                raise WriterError('Le SDK Anthropic est absent : pip install -e ".[llm]"') from e
            client = anthropic.Anthropic()
        self.client = client
        self.model = model or os.environ.get("AD_AGENT_MODEL") or DEFAULT_MODEL
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
        self._offline = OfflineWriter()

    # -- appel de l'API ---------------------------------------------------------------

    def _ask(self, prompt: str, schema: type[BaseModel]) -> Any:
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=8000,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
                output_config={"effort": "low"},  # tâche courte : inutile de payer une longue réflexion
            )
        except TypeError as e:
            if "authentication" in str(e).lower():
                raise WriterError(
                    "Aucune clé API trouvée. Définissez ANTHROPIC_API_KEY (voir .env.example)."
                ) from e
            raise
        except Exception as e:
            name = type(e).__name__
            if name == "AuthenticationError":
                raise WriterError("Clé API refusée : vérifiez ANTHROPIC_API_KEY dans la console Anthropic.") from e
            if name == "PermissionDeniedError":
                raise WriterError("Cette clé n'a pas accès à ce modèle ou à cette fonctionnalité.") from e
            if name == "NotFoundError":
                raise WriterError(f"Modèle introuvable : « {self.model} ». Voir AD_AGENT_MODEL.") from e
            if name == "RateLimitError":
                raise WriterError("Limite de débit atteinte : réessayez dans un instant.") from e
            if name == "APIConnectionError":
                raise WriterError("Connexion à l'API impossible : vérifiez le réseau.") from e
            if name == "APIStatusError" or hasattr(e, "status_code"):
                raise WriterError(f"Erreur de l'API ({getattr(e, 'status_code', '?')}) : {e}") from e
            raise

        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
            self.usage["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
        self.usage["calls"] += 1
        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise WriterError(f"Réponse inexploitable du modèle (stop_reason={getattr(response, 'stop_reason', '?')}).")
        return parsed

    # -- étape 3 : angles -------------------------------------------------------------

    def propose_angles(self, brief: Brief) -> list[Angle]:
        facts = brief_facts(brief)
        has_before_after = any(a.role == "before" for a in brief.assets) and any(a.role == "after" for a in brief.assets)
        allowed_types = (
            ["benefit", "problem_solution", "curiosity"]
            + (["offer"] if brief.offer else [])
            + (["before_after"] if has_before_after else [])
        )
        prompt = (
            "Voici le brief d'une campagne publicitaire (JSON) :\n"
            f"{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            f"Propose UN angle pour CHACUN des types suivants, sans en omettre aucun : {', '.join(allowed_types)}. "
            "Pour chaque angle, écris 3 accroches de 60 caractères maximum, "
            "dans la langue du brief, fondées uniquement sur les faits du brief, "
            "et une phrase de justification (pourquoi cet angle convient à cette audience)."
        )
        draft: AnglesDraft = self._ask(prompt, AnglesDraft)

        allowed_numbers = _numbers(json.dumps(facts, ensure_ascii=False))
        by_type: dict[str, list[str]] = {}
        rationale: dict[str, str] = {}
        for a in draft.angles:
            if a.hook_type not in allowed_types:
                continue
            for hook in a.hooks:
                hook = hook.strip()
                if hook and hook not in by_type.get(a.hook_type, []) and not check_text(hook, 60, brief, allowed_numbers):
                    by_type.setdefault(a.hook_type, []).append(hook)
                    rationale.setdefault(a.hook_type, a.rationale)

        angles: list[Angle] = []
        if brief.hook_idea:
            angles.append(Angle(id="a_brief", hook_type=HookType.benefit, hooks=[brief.hook_idea],
                                rationale="Hook imposé par le brief."))
        for hook_type, hooks in by_type.items():
            if hook_type == "offer":
                hooks = [brief.offer, *[h for h in hooks if h != brief.offer]]  # l'offre exacte d'abord
            angles.append(Angle(id=f"a_{hook_type}", hook_type=HookType(hook_type), hooks=hooks,
                                rationale=rationale[hook_type]))
        if brief.offer and "offer" not in by_type:
            angles.append(Angle(id="a_offer", hook_type=HookType.offer, hooks=[brief.offer],
                                rationale="Offre commerciale indiquée dans le brief."))
        if brief.testimonials:  # la preuve sociale reste factuelle : les vrais avis, sans réécriture
            angles.append(Angle(id="a_proof", hook_type=HookType.social_proof,
                                hooks=[t.text for t in brief.testimonials],
                                rationale="Avis clients réels fournis dans le brief."))
        if not angles:
            raise WriterError("Le modèle n'a produit aucun angle utilisable pour ce brief.")
        return angles

    # -- étape 5 : textes -------------------------------------------------------------

    def write_copy(self, brief: Brief, hook: str, fmt: AdFormat) -> tuple[dict[str, str | list[str]], list[str]]:
        zones, warnings = self._offline.write_copy(brief, hook, fmt)  # base déterministe (prix, avis, repli)
        creative = [z for z in fmt.zones
                    if z.role in CREATIVE_ROLES and z.role not in NON_TEXT_ROLES and z.id not in FIXED_ZONES]
        if not creative:
            return zones, warnings

        facts = brief_facts(brief)
        spec = [{"zone_id": z.id, "role": z.role, "longueur_max_par_ligne": z.max_chars, "obligatoire": z.required,
                 "position": z.position,
                 **({"nombre_de_lignes": f"{z.list_min or 1}-{z.list_max or z.list_min or 1}"}
                    if z.role == "list" else {})}
                for z in creative]
        prompt = (
            f"Brief (JSON) :\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            f"Format d'annonce : « {fmt.name} » — {fmt.description.strip()}\n"
            f"Structure visuelle : {fmt.layout_notes.strip()}\n\n"
            f"Message à porter (accroche) : « {hook} »\n\n"
            f"Écris le texte de chacune de ces zones (JSON) :\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n"
            "Pour une zone facultative sans intérêt, renvoie un texte vide. "
            "Le texte du titre principal doit porter le message ci-dessus, reformulé si besoin. "
            "Pour une zone de rôle « list », renvoie une ligne par idée, séparées par de vrais retours à la "
            "ligne (\\n), en respectant le nombre de lignes indiqué : une idée courte et concrète par ligne, "
            "sans numérotation ni puce (déjà ajoutées par la mise en page)."
        )
        draft: CopyDraft = self._ask(prompt, CopyDraft)

        allowed_numbers = _numbers(json.dumps(facts, ensure_ascii=False)) | _numbers(hook)
        zone_by_id = {z.id: z for z in creative}
        for item in draft.zones:
            zone = zone_by_id.get(item.zone_id)
            if zone is None:
                continue
            if zone.role == "list":
                lines = [ln.strip() for ln in item.text.split("\n") if ln.strip()]
                valid = []
                for line in lines:
                    reason = check_text(line, zone.max_chars, brief, allowed_numbers)
                    if reason:
                        warnings.append(f"zone « {zone.id} » : une ligne rejetée ({reason})")
                    else:
                        valid.append(line)
                if zone.list_max and len(valid) > zone.list_max:
                    warnings.append(f"zone « {zone.id} » : {len(valid)} lignes valides, tronqué à {zone.list_max}")
                    valid = valid[:zone.list_max]
                if zone.list_min and len(valid) < zone.list_min:
                    warnings.append(
                        f"zone « {zone.id} » : seulement {len(valid)} ligne(s) valide(s) sur "
                        f"{zone.list_min} minimum"
                    )
                zones[zone.id] = valid  # les lignes valides sont gardées même sous le minimum : mieux
                                        # qu'une zone totalement vide (le warning signale le manque)
                continue
            text = re.sub(r"\s+", " ", item.text).strip()
            if not text:
                continue
            reason = check_text(text, zone.max_chars, brief, allowed_numbers)
            if reason:
                warnings.append(f"zone « {zone.id} » : texte du modèle rejeté ({reason}), texte du brief conservé")
            else:
                zones[zone.id] = text
        return zones, warnings

    # -- textes de publication ----------------------------------------------------------

    def write_publication(self, brief: Brief, hook: str) -> tuple[PublicationCopy, list[str]]:
        base, base_warnings = offline_publication(brief, hook)  # repli déterministe
        if is_testimonial(brief, hook):
            return base, base_warnings  # un avis réel n'est jamais envoyé au modèle pour réécriture
        facts = brief_facts(brief)                              # sans les avis : ils restent au code
        prompt = (
            f"Brief (JSON) :\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            f"Accroche de cette variante : « {hook} »\n\n"
            "Écris les textes de publication Meta qui accompagnent le visuel, dans la langue du brief :\n"
            f"- {MAX_ITEMS} textes principaux de {PRIMARY_MIN} à {PRIMARY_MAX} caractères, chacun sous un angle "
            "différent, qui portent l'accroche ;\n"
            f"- {MAX_ITEMS} titres de {HEADLINE_MAX} caractères maximum.\n"
            "N'utilise que les faits du brief : aucun avis client, aucun chiffre absent du brief."
        )
        draft: PublicationDraft = self._ask(prompt, PublicationDraft)
        allowed = allowed_numbers(brief) | _numbers(hook)
        heads, warnings = filter_texts(draft.headlines, HEADLINE_MAX, brief, allowed, "titre")
        prims, w = filter_texts(draft.primary_texts, PRIMARY_MAX, brief, allowed, "texte principal",
                                min_len=PRIMARY_MIN)
        warnings += w
        testimonial = testimonial_text(brief, hook)
        if testimonial:
            prims = [p for p in prims if p != testimonial][:MAX_ITEMS - 1] + [testimonial]
        if not heads:
            heads = base.headlines
            warnings.append("aucun titre du modèle retenu : titres hors ligne")
        if not [p for p in prims if p != testimonial]:
            prims = base.primary_texts
            warnings.append("aucun texte principal du modèle retenu : textes hors ligne")
        if heads is base.headlines or prims is base.primary_texts:
            warnings += base_warnings
        return PublicationCopy(primary_texts=prims, headlines=heads), warnings
