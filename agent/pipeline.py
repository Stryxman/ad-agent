"""Le pipeline : brief -> angles -> plan de variantes -> textes -> rendu -> export.

Chaque étape lit l'objet de la précédente et écrit son fichier dans le dossier du run (traçable, rejouable).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from agent.loader import ROOT, load_all_formats, load_brief
from agent.render import available_templates, render_html, screenshot_all
from agent.schemas import (
    AdFormat, Angle, Brief, SkippedFormat, Variant, VariantCopy, VariantPlan,
)
from agent.writers import OfflineWriter, Writer, WriterError, fit_text, normalize

OUTPUTS_DIR = ROOT / "outputs"


# ------------------------------------------------------------------------ utilitaires


def _dump(path: Path, data: BaseModel | dict | list) -> None:
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _has_field(brief: Brief, dotted: str) -> bool:
    obj = brief
    for part in dotted.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return False
    return bool(obj)


# -------------------------------------------------------------- étape 4 : sélection


def eligibility(brief: Brief, fmt: AdFormat, templates: set[str]) -> str | None:
    """Renvoie la raison d'exclusion d'un format, ou None s'il est utilisable pour ce brief."""
    if not set(fmt.ratios) & set(brief.ratios):
        return f"aucun ratio commun (format: {fmt.ratios}, brief: {brief.ratios})"
    if brief.objective not in fmt.objectives:
        return f"objectif « {brief.objective.value} » non prévu par le format"
    if not fmt.fits_niche(brief.niche):
        return f"format réservé aux niches {[n.value for n in fmt.niches_fit]}"
    for path in fmt.requires:
        if not _has_field(brief, path):
            return f"champ du brief manquant : {path}"
    if any("before_after" == h.value for h in fmt.hook_types):
        if any("avant/apres" in normalize(c) or "avant apres" in normalize(c) for c in brief.forbidden_claims):
            return "avant/après interdit par les promesses exclues du brief"
    if fmt.id not in templates:
        return "aucun gabarit de rendu pour ce format pour l'instant"
    return None


def select_variants(brief: Brief, angles: list[Angle], formats: list[AdFormat]) -> VariantPlan:
    templates = available_templates()
    skipped: list[SkippedFormat] = []
    usable: list[AdFormat] = []
    for fmt in formats:
        reason = eligibility(brief, fmt, templates)
        if reason:
            skipped.append(SkippedFormat(format_id=fmt.id, reason=reason))
        else:
            usable.append(fmt)

    # candidats = angle × format × accroche : un concept par candidat, rendu dans tous ses ratios communs
    candidates: list[tuple[Angle, AdFormat, str]] = []
    for fmt in usable:
        for angle in angles:
            if angle.hook_type in fmt.hook_types:
                candidates.extend((angle, fmt, hook) for hook in angle.hooks)

    # sélection gloutonne : on pénalise la répétition d'un même format ou d'un même angle
    chosen: list[Variant] = []
    counts: dict[str, dict[str, int]] = {"format": {}, "angle": {}}

    def score(c: tuple[Angle, AdFormat, str]) -> float:
        angle, fmt, _ = c
        s = 1.0 + (0.5 if angle.hook_type == fmt.hook_types[0] else 0.0)
        s -= 0.25 * counts["format"].get(fmt.id, 0)
        s -= 0.15 * counts["angle"].get(angle.id, 0)
        return s

    remaining = list(candidates)
    while remaining and len(chosen) < brief.variants_count:
        remaining.sort(key=score, reverse=True)
        angle, fmt, hook = best = remaining.pop(0)
        ratios = [r for r in brief.ratios if r in fmt.ratios]
        chosen.append(
            Variant(
                id=f"v{len(chosen) + 1:02d}", angle_id=angle.id, format_id=fmt.id, ratios=ratios,
                hook=hook, score=round(score(best), 2),
                rationale=f"Hook « {angle.hook_type.value} » adapté au format « {fmt.name} ».",
            )
        )
        counts["format"][fmt.id] = counts["format"].get(fmt.id, 0) + 1
        counts["angle"][angle.id] = counts["angle"].get(angle.id, 0) + 1
    return VariantPlan(variants=chosen, skipped=skipped)


# ------------------------------------------------------------------ étape 5 : textes


def write_all_copy(brief: Brief, plan: VariantPlan, formats: dict[str, AdFormat], writer: Writer) -> list[VariantCopy]:
    result: list[VariantCopy] = []
    for v in plan.variants:
        fmt = formats[v.format_id]
        zones, warnings = writer.write_copy(brief, v.hook, fmt)
        warnings = list(warnings)
        for z in fmt.zones:
            text = zones.get(z.id)
            if text is not None and z.max_chars and len(text) > z.max_chars:
                zones[z.id] = fit_text(text, z.max_chars)
                warnings.append(f"zone « {z.id} » tronquée à {z.max_chars} caractères")
            if z.required and z.role not in ("image", "logo") and not zones.get(z.id):
                warnings.append(f"zone obligatoire « {z.id} » sans contenu")
        result.append(VariantCopy(variant_id=v.id, zones=zones, warnings=warnings))
    return result


# ------------------------------------------------------------------ étape 9 : export


def write_review(path: Path, brief: Brief, plan: VariantPlan, copies: list[VariantCopy],
                 formats: dict[str, AdFormat], rendered: dict[str, dict[str, dict[str, str]]]) -> None:
    lines = [f"# Revue du run — {brief.name}", "",
             f"Niche : {brief.niche.value} · Objectif : {brief.objective.value} · "
             f"{len(plan.variants)} variante(s)", ""]
    by_id = {c.variant_id: c for c in copies}
    for v in plan.variants:
        fmt = formats[v.format_id]
        files = rendered.get(v.id, {})
        lines += [f"## {v.id} — {fmt.name} ({', '.join(v.ratios)})", "",
                  f"- Angle : `{v.angle_id}` · score {v.score}", f"- Pourquoi : {v.rationale}"]
        for ratio, paths in files.items():
            lines.append(f"- {ratio} : {', '.join(f'`{p}`' for p in paths.values())}")
        for zid, text in by_id[v.id].zones.items():
            lines.append(f"- {zid} : {text}")
        for w in by_id[v.id].warnings:
            lines.append(f"- ⚠ {w}")
        lines.append("")
    if plan.skipped:
        lines += ["## Formats écartés", ""]
        lines += [f"- `{s.format_id}` : {s.reason}" for s in plan.skipped]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ------------------------------------------------------------------------- le run


def run(brief_path: Path, writer: Writer | None = None, out_root: Path = OUTPUTS_DIR,
        render_png: bool = True, browser: str = "chromium") -> Path:
    writer = writer or OfflineWriter()
    run_dir = out_root / f"run_{datetime.now():%Y%m%d_%H%M%S}"
    (run_dir / "renders").mkdir(parents=True)

    # 1. brief
    brief = load_brief(brief_path)
    _dump(run_dir / "brief.normalized.json", brief)

    # 3. angles
    try:
        angles = writer.propose_angles(brief)
    except WriterError:
        shutil.rmtree(run_dir, ignore_errors=True)  # rien d'exploitable à conserver
        raise
    _dump(run_dir / "angles.json", [a.model_dump(mode="json") for a in angles])

    # 4. formats et plan de variantes
    formats = {f.id: f for f in load_all_formats()}
    plan = select_variants(brief, angles, list(formats.values()))
    _dump(run_dir / "variant_plan.json", plan)

    # 5. textes
    try:
        copies = write_all_copy(brief, plan, formats, writer)
    except WriterError:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise
    _dump(run_dir / "copy.json", [c.model_dump(mode="json") for c in copies])

    # 7. rendu HTML puis PNG, un fichier par ratio
    copy_by_id = {c.variant_id: c for c in copies}
    rendered: dict[str, dict[str, dict[str, str]]] = {}
    jobs: list[tuple[str, str, Path]] = []
    for v in plan.variants:
        rendered[v.id] = {}
        for ratio in v.ratios:
            html_path = render_html(v, formats[v.format_id], copy_by_id[v.id].zones, brief, ratio,
                                    run_dir / "renders")
            rendered[v.id][ratio] = {"html": str(html_path.relative_to(run_dir))}
            jobs.append((v.id, ratio, html_path))
    if render_png and jobs:
        for (variant_id, ratio), png in screenshot_all(jobs, browser).items():
            rendered[variant_id][ratio]["png"] = str(png.relative_to(run_dir))

    # 9. manifest + revue
    manifest = {
        "brief": brief.name, "writer": writer.name, "usage": getattr(writer, "usage", None), "created_at": datetime.now().isoformat(timespec="seconds"),
        "variants": [
            {**v.model_dump(mode="json"), "copy": copy_by_id[v.id].zones,
             "warnings": copy_by_id[v.id].warnings, "files": rendered[v.id]}
            for v in plan.variants
        ],
        "skipped_formats": [s.model_dump(mode="json") for s in plan.skipped],
    }
    _dump(run_dir / "manifest.json", manifest)
    write_review(run_dir / "review.md", brief, plan, copies, formats, rendered)
    return run_dir
