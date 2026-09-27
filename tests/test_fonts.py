from agent.fonts import find_local, missing, resolve, safe_family


def test_local_font_is_found_by_exact_then_prefixed_name(tmp_path):
    (tmp_path / "PlayfairDisplay-Bold.ttf").write_bytes(b"x")
    (tmp_path / "Inter.woff2").write_bytes(b"y")
    assert find_local("Playfair Display", tmp_path).name == "PlayfairDisplay-Bold.ttf"
    assert find_local("Inter", tmp_path).name == "Inter.woff2"
    assert find_local("Lora", tmp_path) is None


def test_local_font_is_embedded_as_data_uri(tmp_path):
    (tmp_path / "Inter.woff2").write_bytes(b"police")
    plan = resolve(["Inter"], tmp_path)
    assert plan.sources == {"Inter": "local"}
    assert "@font-face" in plan.head and "data:font/woff2;base64,cG9saWNl" in plan.head


def test_google_fallback_uses_one_link_per_family_and_a_weightless_link(tmp_path):
    plan = resolve(["Playfair Display", "Bebas Neue", "Playfair Display"], tmp_path)
    assert plan.sources == {"Playfair Display": "google", "Bebas Neue": "google"}
    assert "family=Playfair+Display&display=swap" in plan.head
    assert "family=Bebas+Neue:wght@700" in plan.head   # le gras, s'il n'existe pas, n'empêche pas le regular


def test_font_names_with_markup_are_refused(tmp_path):
    plan = resolve(['Inter</style><script>alert(1)</script>'], tmp_path)
    assert plan.sources == {} and "<script>" not in plan.head
    assert plan.warnings and "refusé" in plan.warnings[0]
    assert safe_family("serif") is None


def test_missing_compares_family_names_loosely():
    assert missing(["Playfair Display", "Inter"], ["Playfair Display"]) == ["Inter"]
    assert missing(["Inter"], ["inter"]) == []


def test_unsafe_font_name_never_reaches_the_rendered_css(tmp_path):
    from agent.loader import BRIEFS_DIR, load_all_formats, load_brief
    from agent.render import render_html
    from agent.schemas import Variant

    brief = load_brief(BRIEFS_DIR / "example_soin_peau.yaml")
    brief = brief.model_copy(update={"da": brief.da.model_copy(update={"fonts": ['X"}</style><script>', "Inter"]})})
    fmt = next(f for f in load_all_formats() if f.id == "offre_prix_barre")
    variant = Variant(id="v1", angle_id="a", format_id=fmt.id, ratios=["4:5"], hook="x", score=1.0, rationale="r")
    html = render_html(variant, fmt, {"headline": "T"}, brief, "4:5", tmp_path).read_text(encoding="utf-8")
    assert "<script>" not in html and 'font-family: "Georgia"' in html


def test_realistic_font_folder_uses_regular_and_bold_not_black_or_italic(tmp_path):
    for style in ("Black", "Bold", "Italic", "Regular"):
        (tmp_path / f"PlayfairDisplay-{style}.ttf").write_bytes(style.encode())
    head = resolve(["Playfair Display"], tmp_path).head
    import base64
    b64 = lambda s: base64.b64encode(s.encode()).decode()
    assert b64("Regular") in head and b64("Bold") in head
    assert b64("Black") not in head and b64("Italic") not in head
    assert "font-weight: 400" in head and "font-weight: 700" in head


def test_variable_font_prefers_the_upright_file(tmp_path):
    (tmp_path / "Inter-Italic-VariableFont_opsz,wght.ttf").write_bytes(b"italic")
    (tmp_path / "Inter-VariableFont_opsz,wght.ttf").write_bytes(b"upright")
    head = resolve(["Inter"], tmp_path).head
    assert "dXByaWdodA==" in head and "aXRhbGlj" not in head and "font-weight: 100 900" in head


def test_family_prefix_must_end_at_a_separator(tmp_path):
    (tmp_path / "InterTight-Regular.ttf").write_bytes(b"x")
    assert find_local("Inter", tmp_path) is None
    assert resolve(["Inter"], tmp_path).sources == {"Inter": "google"}
