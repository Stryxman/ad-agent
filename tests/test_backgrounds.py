import pytest

from agent.backgrounds import build, make_look, resolve_kind, worst_contrast
from agent.colors import mix

BEAUTE = ("#F4E9DD", "#2B2B2B", "#C9A27E")
TECH = ("#12131A", "#F5F5F0", "#4FD1C5")


def test_uni_is_the_base_colour_alone():
    b = build("uni", "#F4E9DD", "#C9A27E", "#2B2B2B")
    assert b.css == "#F4E9DD" and b.stops == ("#F4E9DD",)


def test_lineaire_goes_from_base_to_32_percent_tint():
    b = build("lineaire", "#F4E9DD", "#C9A27E", "#2B2B2B")
    end = mix("#F4E9DD", "#C9A27E", 0.32)
    assert b.stops == ("#F4E9DD", end)
    assert b.css == f"linear-gradient(160deg, #F4E9DD 0%, {end} 100%)"


def test_mesh_lists_every_visible_colour_as_a_stop():
    b = build("mesh", "#12131A", "#4FD1C5", "#F5F5F0")
    assert b.stops == ("#12131A", mix("#12131A", "#4FD1C5", .55), mix("#12131A", "#4FD1C5", .35),
                       mix("#12131A", "#F5F5F0", .10))
    assert b.css.count("radial-gradient") == 3 and b.css.endswith("#12131A")


def test_unknown_kind_is_refused():
    with pytest.raises(ValueError, match="inconnu"):
        build("neon", "#000000", "#FFFFFF", "#FFFFFF")


def test_text_colour_is_chosen_on_the_worst_stop():
    look = make_look("lineaire", *BEAUTE)
    assert look.on_bg == "#111111"
    assert worst_contrast(look.on_bg, look.bg) >= 3.0
    tech = make_look("mesh", *TECH)
    assert tech.on_bg == "#FFFFFF" and worst_contrast(tech.on_bg, tech.bg) >= 3.0


def test_unreadable_gradient_falls_back_to_flat_with_a_warning():
    # blanc vers noir en mesh : la tache à 55 % est un gris moyen, ni le noir ni le blanc n'y atteignent 3:1
    look = make_look("mesh", "#FFFFFF", "#000000", "#000000")
    assert look.bg.stops == ("#FFFFFF",)
    assert len(look.warnings) == 1 and "repli en aplat" in look.warnings[0]


def test_accent_text_falls_back_when_accent_is_unreadable_on_the_surface():
    assert make_look("lineaire", *BEAUTE).accent_text == "#111111"   # or clair sur beige
    assert make_look("lineaire", *TECH).accent_text == "#4FD1C5"     # turquoise sur fond sombre : lisible


def test_priority_cli_then_brief_then_format():
    assert resolve_kind("uni", "mesh", "lineaire") == "uni"
    assert resolve_kind("auto", "mesh", "lineaire") == "mesh"
    assert resolve_kind(None, "auto", "lineaire") == "lineaire"
    assert resolve_kind(None, "auto", "mesh") == "mesh"
