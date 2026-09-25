import json

from markupsafe import escape

from agent.loader import BRIEFS_DIR, load_all_formats, load_brief
from agent.pipeline import eligibility, run, select_variants
from agent.render import available_templates, contrast_ratio, readable_on
from agent.schemas import Niche
from agent.writers import OfflineWriter, fit_text

EXAMPLE = BRIEFS_DIR / "example_soin_peau.yaml"


def _plan(brief):
    return select_variants(brief, OfflineWriter().propose_angles(brief), load_all_formats())


def test_fit_text_cuts_on_word_boundary_within_limit():
    out = fit_text("Un texte beaucoup trop long pour la zone", 20)
    assert len(out) <= 20 and out.endswith("…")
    assert fit_text("court", 20) == "court"


def test_forbidden_before_after_excludes_the_format():
    brief = load_brief(EXAMPLE)
    fmt = next(f for f in load_all_formats() if f.id == "avant_apres_beaute")
    assert "avant/après" in eligibility(brief, fmt, available_templates())


def test_missing_required_brief_field_excludes_the_format():
    brief = load_brief(EXAMPLE)
    brief.product.compare_at_price = None
    skipped = {s.format_id: s.reason for s in _plan(brief).skipped}
    assert "product.compare_at_price" in skipped["offre_prix_barre"]


def test_testimonial_format_needs_real_testimonials():
    brief = load_brief(EXAMPLE).model_copy(update={"testimonials": []})
    assert "temoignage_citation" in {s.format_id for s in _plan(brief).skipped}


def test_niche_restriction_is_respected():
    brief = load_brief(EXAMPLE)
    assert brief.niche == Niche.beaute
    plan = _plan(brief)
    assert "carte_produit_catalogue" in {s.format_id for s in plan.skipped}
    assert all(v.format_id != "carte_produit_catalogue" for v in plan.variants)


def test_plan_respects_variant_count_and_ratios():
    brief = load_brief(EXAMPLE)
    plan = _plan(brief)
    assert 0 < len(plan.variants) <= brief.variants_count
    for v in plan.variants:
        assert v.ratios and set(v.ratios) <= set(brief.ratios)
    assert len({(v.format_id, v.hook) for v in plan.variants}) == len(plan.variants)  # pas de doublon


def test_readable_accent_falls_back_when_contrast_is_low():
    assert readable_on("#C9A27E", "#F4E9DD") == "#111111"          # or clair sur beige : illisible
    assert readable_on("#1B4D3E", "#F4E9DD") == "#1B4D3E"          # vert foncé : lisible
    assert contrast_ratio("#000000", "#FFFFFF") > 20


def test_run_produces_all_artifacts_and_respects_zone_limits(tmp_path):
    run_dir = run(EXAMPLE, out_root=tmp_path, render_png=False)
    for name in ("brief.normalized.json", "angles.json", "variant_plan.json", "copy.json",
                 "manifest.json", "review.md"):
        assert (run_dir / name).is_file(), name

    formats = {f.id: f for f in load_all_formats()}
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["variants"]
    for v in manifest["variants"]:
        for zone in formats[v["format_id"]].zones:
            text = v["copy"].get(zone.id)
            if text and zone.max_chars:
                assert len(text) <= zone.max_chars, (v["id"], zone.id)
        for ratio, files in v["files"].items():
            html = (run_dir / files["html"]).read_text(encoding="utf-8")
            assert "<html" in html
            for text in v["copy"].values():
                assert str(escape(text)) in html, (v["id"], text)
