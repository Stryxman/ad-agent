import json

from markupsafe import escape

from agent.loader import BRIEFS_DIR, load_all_formats, load_brief
from agent.pipeline import _safe_path, eligibility, run, select_variants
from agent.render import available_templates, contrast_color, contrast_ratio, readable_on, render_html
from agent.schemas import AdFormat, Niche, Variant, Zone
from agent.writers import OfflineWriter, fit_text

EXAMPLE = BRIEFS_DIR / "example_soin_peau.yaml"


def _plan(brief):
    return select_variants(brief, OfflineWriter().propose_angles(brief), load_all_formats())


def test_fit_text_cuts_on_word_boundary_within_limit():
    out = fit_text("Un texte beaucoup trop long pour la zone", 20)
    assert len(out) <= 20 and out.endswith("…")
    assert fit_text("court", 20) == "court"


def test_before_after_format_requires_tagged_real_photos():
    brief = load_brief(EXAMPLE)  # aucune photo étiquetée before/after dans cet exemple
    fmt = next(f for f in load_all_formats() if f.id == "avant_apres_beaute")
    assert "assets.before" in eligibility(brief, fmt, available_templates())


def test_forbidden_before_after_excludes_the_format_even_with_real_photos():
    from agent.schemas import AssetRef

    brief = load_brief(EXAMPLE).model_copy(update={"assets": [
        AssetRef(path="assets/products/serum_packshot.png", role="before"),
        AssetRef(path="assets/products/serum_packshot.png", role="after"),
    ]})
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


def test_offline_writer_fills_new_special_zones():
    brief = load_brief(EXAMPLE)
    writer_ = OfflineWriter()
    fmt = next(f for f in load_all_formats() if f.id == "carte_produit_catalogue")
    zones, _ = writer_.write_copy(brief, brief.offer, fmt)
    assert zones["product_name"] == brief.product.name  # jamais reformulé
    assert brief.product.price in zones["price_line"]


def test_tech_brief_unlocks_mode_tech_only_formats():
    tech_brief = load_brief(BRIEFS_DIR / "example_ecouteurs_tech.yaml")
    plan = _plan(tech_brief)
    selected = {v.format_id for v in plan.variants}
    assert "carte_produit_catalogue" in selected or "spotlight_fonctionnalite" in selected
    beauty_plan = _plan(load_brief(EXAMPLE))
    assert all(f not in {"carte_produit_catalogue", "spotlight_fonctionnalite"}
              for f in {v.format_id for v in beauty_plan.variants})  # toujours exclus en beauté


def test_before_after_disclaimer_is_fixed_and_labels_come_from_asset_metadata():
    from agent.schemas import AssetRef

    brief = load_brief(EXAMPLE).model_copy(update={"assets": [
        AssetRef(path="assets/products/serum_packshot.png", role="before", label="Jour 1"),
        AssetRef(path="assets/products/serum_packshot.png", role="after", label="Jour 30"),
    ]})
    fmt = next(f for f in load_all_formats() if f.id == "avant_apres_beaute")
    zones, _ = OfflineWriter().write_copy(brief, "peu importe", fmt)
    assert zones["disclaimer"] == "Résultats variables selon les personnes."
    assert zones["before_label"] == "Jour 1" and zones["after_label"] == "Jour 30"


def test_before_after_format_is_selected_when_real_photos_are_tagged():
    from agent.schemas import AssetRef

    # forbidden_claims vidé : le brief d'exemple interdit lui-même « avant/après sur la peau »,
    # ce test isole la seule condition qui nous intéresse ici (les photos étiquetées).
    brief = load_brief(EXAMPLE).model_copy(update={
        "assets": [
            AssetRef(path="assets/products/serum_packshot.png", role="before", label="Jour 1"),
            AssetRef(path="assets/products/serum_packshot.png", role="after", label="Jour 30"),
        ],
        "forbidden_claims": [],
    })
    plan = _plan(brief)
    assert all(s.format_id != "avant_apres_beaute" for s in plan.skipped)


def test_offline_writer_leaves_list_zone_empty_without_inventing_content():
    brief = load_brief(EXAMPLE)
    fmt = next(f for f in load_all_formats() if f.id == "infographie_probleme")
    zones, _ = OfflineWriter().write_copy(brief, "Un vrai plaisir", fmt)
    assert "lines" not in zones  # aucune source factuelle : le rédacteur hors ligne n'invente rien


def test_readable_accent_falls_back_when_contrast_is_low():
    assert readable_on("#C9A27E", "#F4E9DD") == "#111111"          # or clair sur beige : illisible
    assert readable_on("#1B4D3E", "#F4E9DD") == "#1B4D3E"          # vert foncé : lisible
    assert contrast_ratio("#000000", "#FFFFFF") > 20


def test_before_after_angle_is_produced_by_offline_writer_when_photos_are_tagged():
    from agent.schemas import AssetRef, HookType

    brief = load_brief(EXAMPLE).model_copy(update={"assets": [
        AssetRef(path="assets/products/serum_packshot.png", role="before"),
        AssetRef(path="assets/products/serum_packshot.png", role="after"),
    ]})
    angles = OfflineWriter().propose_angles(brief)
    assert any(a.hook_type == HookType.before_after for a in angles)  # sinon le format correspondant
    # reste éligible mais n'a jamais de candidat (voir test_eligible_format_with_no_matching_angle...)


def test_eligible_format_with_no_matching_angle_is_reported_as_skipped(monkeypatch):
    import agent.pipeline as pipeline_mod

    brief = load_brief(EXAMPLE)
    fmt = AdFormat(
        id="x_comparatif_test", name="Comparatif (test)", description="format de test",
        ratios=list(brief.ratios), objectives=[brief.objective], hook_types=["comparison"],
        zones=[Zone(id="headline", role="headline")],
    )
    # aucun rédacteur (hors ligne ou Claude) ne propose d'angle "comparison" aujourd'hui : sans le
    # garde-fou de select_variants, ce format éligible disparaîtrait sans laisser de trace.
    monkeypatch.setattr(pipeline_mod, "available_templates", lambda: {fmt.id})
    angles = OfflineWriter().propose_angles(brief)
    plan = select_variants(brief, angles, [fmt])
    skipped = {s.format_id: s.reason for s in plan.skipped}
    assert fmt.id in skipped and "comparison" in skipped[fmt.id]
    assert all(v.format_id != fmt.id for v in plan.variants)


def test_product_and_scene_image_come_from_the_same_asset(monkeypatch, tmp_path):
    """Avant le correctif, product_image sautait les assets en échec pendant que scene_image restait
    sur le premier fichier existant : deux photos différentes du même produit dans un même run."""
    import base64

    import agent.pipeline as pipeline_mod
    from agent.schemas import AssetAnalysis, AssetRef

    asset_a = tmp_path / "a.png"
    asset_b = tmp_path / "b.png"
    asset_a.write_bytes(b"CONTENU_A_ECHOUE")
    asset_b.write_bytes(b"CONTENU_B_ORIGINAL")
    cache = tmp_path / "b_detoure.png"

    def fake_ensure_isolated(path, cache_dir=None):
        if path.name == "a.png":
            return AssetAnalysis(path=str(path), isolated=False, action="echec",
                                 used_path=str(path), note="echec test")
        cache.write_bytes(b"CONTENU_B_DETOURE")
        return AssetAnalysis(path=str(path), isolated=False, action="detoure", used_path=str(cache), note="ok")

    brief = load_brief(EXAMPLE).model_copy(update={"assets": [AssetRef(path="a.png"), AssetRef(path="b.png")]})
    monkeypatch.setattr(pipeline_mod, "ensure_isolated", fake_ensure_isolated)
    monkeypatch.setattr(pipeline_mod, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline_mod, "load_brief", lambda _p: brief)

    run_dir = pipeline_mod.run(EXAMPLE, out_root=tmp_path / "out", render_png=False)
    html = "\n".join(p.read_text(encoding="utf-8") for p in (run_dir / "renders").glob("*.html"))

    assert base64.b64encode(b"CONTENU_A_ECHOUE").decode() not in html  # jamais utilisé, isolement en échec
    assert base64.b64encode(b"CONTENU_B_ORIGINAL").decode() in html    # scene_img : la photo d'origine
    assert base64.b64encode(b"CONTENU_B_DETOURE").decode() in html    # product_img : le produit détouré
    # les deux viennent du même asset (b.png) : jamais a.png pour l'un et b.png pour l'autre


def test_asset_path_escaping_project_root_is_refused():
    assert _safe_path("../../../../etc/hostname") is None
    assert _safe_path("/etc/hostname") is None
    assert _safe_path("assets/products/serum_packshot.png") is not None  # chemin normal, inchangé


def test_scene_placeholder_text_is_readable_against_accent_not_background(tmp_path):
    # Régression : titre_produit_en_situation utilisait `accent_text` (contraste vs. le fond de page)
    # pour du texte posé sur un bloc `accent`, ce qui pouvait rendre le texte invisible.
    tech_brief = load_brief(BRIEFS_DIR / "example_ecouteurs_tech.yaml")
    fmt = next(f for f in load_all_formats() if f.id == "titre_produit_en_situation")
    accent, bg = tech_brief.da.palette[2], tech_brief.da.palette[0]
    assert contrast_ratio(accent, bg) >= 3.0  # condition qui déclenchait le bug (accent déjà lisible sur bg)

    variant = Variant(id="v1", angle_id="a", format_id=fmt.id, ratios=["4:5"], hook="x", score=1.0, rationale="r")
    html_path = render_html(variant, fmt, {"headline": "Titre"}, tech_brief, "4:5", tmp_path,
                            product_image=None, scene_image=None)
    html = html_path.read_text(encoding="utf-8")
    on_accent = contrast_color(accent)
    assert f"background: var(--accent); color: {on_accent};" in html
    assert contrast_ratio(on_accent, accent) >= 3.0


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
