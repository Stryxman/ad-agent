"""Schémas des deux objets d'entrée du pipeline : le brief et la fiche de format."""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RATIOS = {"1:1", "4:5", "9:16", "16:9"}
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class Objective(str, Enum):
    conversion = "conversion"
    awareness = "awareness"
    traffic = "traffic"
    lead = "lead"


class Niche(str, Enum):
    tech = "tech"
    beaute = "beaute"
    mode = "mode"
    sante_bien_etre = "sante_bien_etre"
    animaux = "animaux"
    autre = "autre"


class HookType(str, Enum):
    problem_solution = "problem_solution"
    social_proof = "social_proof"
    offer = "offer"
    comparison = "comparison"
    benefit = "benefit"
    curiosity = "curiosity"
    before_after = "before_after"


def _check_ratios(values: list[str]) -> list[str]:
    unknown = set(values) - RATIOS
    if unknown:
        raise ValueError(f"ratios inconnus: {sorted(unknown)} (attendus: {sorted(RATIOS)})")
    return values


# --------------------------------------------------------------------------- brief


class Product(BaseModel):
    name: str
    description: str
    benefits: list[str] = Field(min_length=1)
    price: str | None = None
    compare_at_price: str | None = Field(default=None, description="Ancien prix (prix barré), si réel")


class DA(BaseModel):
    """Direction artistique."""

    palette: list[str] = Field(min_length=1, description="Couleurs hex, principale en premier")
    fonts: list[str] = Field(default_factory=list)
    tone: str
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    fond: Literal["auto", "lineaire", "mesh", "uni"] = Field(
        default="auto", description="Traitement de fond ; auto = celui de chaque format"
    )

    @field_validator("palette")
    @classmethod
    def _check_hex(cls, values: list[str]) -> list[str]:
        bad = [v for v in values if not _HEX.match(v)]
        if bad:
            raise ValueError(f"couleur non hexadécimale dans la palette : {bad} (attendu : #RRGGBB ou #RGB)")
        return values


class AssetRef(BaseModel):
    path: str
    description: str = ""
    role: str | None = Field(
        default=None,
        description="Étiquette optionnelle (ex. 'before', 'after') pour les formats qui référencent "
                    "des photos précises plutôt que la première image venue.",
    )
    label: str | None = Field(default=None, description="Libellé factuel affiché avec l'image (ex. 'Jour 1')")


class Testimonial(BaseModel):
    """Avis client réel fourni par l'utilisateur : l'agent n'en invente jamais."""

    text: str
    author: str = ""
    rating: int | None = Field(default=None, ge=1, le=5)


class Brief(BaseModel):
    name: str
    brand: str = Field(default="", description="Nom de marque affiché en logotype textuel")
    niche: Niche
    objective: Objective
    product: Product
    audience: str
    offer: str | None = None
    da: DA
    hook_idea: str | None = Field(default=None, description="Angle ou hook imposé, sinon l'agent propose")
    ratios: list[str] = Field(default_factory=lambda: ["4:5"])
    language: str = "fr"
    forbidden_claims: list[str] = Field(default_factory=list)
    assets: list[AssetRef] = Field(default_factory=list)
    testimonials: list[Testimonial] = Field(default_factory=list)
    variants_count: int = Field(default=6, ge=1, le=20)

    _v_ratios = field_validator("ratios")(_check_ratios)


# -------------------------------------------------------------------------- format


class Zone(BaseModel):
    """Un emplacement à remplir dans le format (titre, preuve, CTA, image...)."""

    id: str
    role: str = Field(description="headline | subhead | proof | cta | badge | image | ...")
    required: bool = True
    max_chars: int | None = Field(default=None, description="Limite de texte par ligne, None pour une zone image")
    position: str = Field(default="", description="Indication libre: haut, centre gauche...")
    list_min: int | None = Field(default=None, description="Nombre minimal de lignes, uniquement pour role='list'")
    list_max: int | None = Field(default=None, description="Nombre maximal de lignes, uniquement pour role='list'")


class AssetNeeds(BaseModel):
    packshot: bool = False
    lifestyle: bool = False
    person: bool = False
    generated_scene_ok: bool = True


class Source(BaseModel):
    """D'où vient le format. On ne stocke jamais le visuel du concurrent, seulement une référence."""

    ad_library_ids: list[str] = Field(default_factory=list)
    advertisers: list[str] = Field(default_factory=list)
    observed_on: date | None = Field(default=None, description="Date de l'observation dans la bibliothèque")
    observed_running_days: int | None = Field(
        default=None, description="Plus longue durée de diffusion observée parmi les pubs de référence"
    )
    notes: str = ""


class AdFormat(BaseModel):
    id: str
    name: str
    description: str
    status: str = Field(default="draft", description="draft | validated")
    ratios: list[str] = Field(min_length=1)
    objectives: list[Objective] = Field(min_length=1)
    hook_types: list[HookType] = Field(min_length=1)
    niches_fit: list[Niche] = Field(
        default_factory=list, description="Niches où le format excelle ; liste vide = universel"
    )
    requires: list[str] = Field(
        default_factory=list,
        description="Champs du brief à renseigner pour utiliser ce format (chemin pointé, ex. product.compare_at_price)",
    )
    zones: list[Zone] = Field(min_length=1)
    asset_needs: AssetNeeds = Field(default_factory=AssetNeeds)
    fond: Literal["lineaire", "mesh", "uni"] = Field(
        default="lineaire", description="Traitement de fond par défaut de ce format"
    )
    layout_notes: str = Field(default="", description="Structure visuelle en langage naturel")
    when_to_use: str = ""
    when_to_avoid: str = ""
    source: Source = Field(default_factory=Source)
    tags: list[str] = Field(default_factory=list)
    score: float | None = Field(default=None, description="Performance connue (v2), None au départ")

    _v_ratios = field_validator("ratios")(_check_ratios)

    def fits_niche(self, niche: Niche) -> bool:
        """Universel (niches_fit vide) ou explicitement adapté à cette niche."""
        return not self.niches_fit or niche in self.niches_fit

    @field_validator("zones")
    @classmethod
    def _unique_zone_ids(cls, zones: list[Zone]) -> list[Zone]:
        ids = [z.id for z in zones]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"ids de zones dupliqués: {sorted(dupes)}")
        return zones


# ------------------------------------------------------------- artefacts du pipeline


class AssetAnalysis(BaseModel):
    path: str
    isolated: bool
    action: str = Field(description="aucune | detoure | echec | introuvable")
    used_path: str
    note: str = ""


class Angle(BaseModel):
    id: str
    hook_type: HookType
    hooks: list[str] = Field(min_length=1)
    rationale: str = ""


class Variant(BaseModel):
    id: str
    angle_id: str
    format_id: str
    ratios: list[str]
    hook: str
    score: float
    rationale: str = ""


class SkippedFormat(BaseModel):
    format_id: str
    reason: str


class VariantPlan(BaseModel):
    variants: list[Variant]
    skipped: list[SkippedFormat] = Field(default_factory=list)


class VariantCopy(BaseModel):
    variant_id: str
    zones: dict[str, str | list[str]]  # str pour une zone normale, list[str] pour une zone role="list"
    warnings: list[str] = Field(default_factory=list)
