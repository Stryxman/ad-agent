import pytest
from pydantic import ValidationError

from agent.loader import BRIEFS_DIR, load_all_formats, load_brief
from agent.schemas import AdFormat, Niche

BASE_FORMAT = {
    "id": "x", "name": "x", "description": "x", "ratios": ["4:5"],
    "objectives": ["conversion"], "hook_types": ["benefit"],
    "zones": [{"id": "h", "role": "headline"}],
}


def test_example_brief_is_valid():
    brief = load_brief(BRIEFS_DIR / "example_soin_peau.yaml")
    assert brief.variants_count == 6
    assert brief.product.benefits


def test_all_formats_are_valid_and_unique():
    formats = load_all_formats()
    assert formats, "la base de formats ne doit pas être vide"
    assert len({f.id for f in formats}) == len(formats)


def test_unknown_ratio_is_rejected():
    with pytest.raises(ValidationError):
        AdFormat.model_validate(
            {
                "id": "x", "name": "x", "description": "x", "ratios": ["3:2"],
                "objectives": ["conversion"], "hook_types": ["benefit"],
                "zones": [{"id": "h", "role": "headline"}],
            }
        )


def test_duplicate_zone_ids_are_rejected():
    with pytest.raises(ValidationError):
        AdFormat.model_validate(
            {
                "id": "x", "name": "x", "description": "x", "ratios": ["4:5"],
                "objectives": ["conversion"], "hook_types": ["benefit"],
                "zones": [{"id": "h", "role": "headline"}, {"id": "h", "role": "cta"}],
            }
        )


def test_format_without_niches_fit_is_universal():
    fmt = AdFormat.model_validate(BASE_FORMAT)
    assert all(fmt.fits_niche(n) for n in Niche)


def test_format_with_niches_fit_is_restricted():
    fmt = AdFormat.model_validate({**BASE_FORMAT, "niches_fit": ["mode", "beaute"]})
    assert fmt.fits_niche(Niche.mode)
    assert not fmt.fits_niche(Niche.tech)


def test_unknown_niche_is_rejected():
    with pytest.raises(ValidationError):
        AdFormat.model_validate({**BASE_FORMAT, "niches_fit": ["crypto"]})


def test_every_format_documents_its_source():
    for fmt in load_all_formats():
        assert fmt.source.ad_library_ids, f"{fmt.id}: aucune pub de référence"
        assert fmt.source.observed_on is not None, f"{fmt.id}: date d'observation manquante"


def test_beauty_only_format_excludes_health():
    fmt = next(f for f in load_all_formats() if f.id == "avant_apres_beaute")
    assert fmt.fits_niche(Niche.beaute)
    assert not fmt.fits_niche(Niche.sante_bien_etre)


@pytest.mark.parametrize("bad", ["red", "#12", "#GGGGGG", "12131A"])
def test_palette_rejects_non_hex_colours(bad):
    from agent.schemas import DA

    with pytest.raises(ValidationError, match="hexadécimale"):
        DA(palette=["#FFFFFF", bad], tone="x")


def test_da_fond_defaults_to_auto():
    from agent.schemas import DA

    assert DA(palette=["#FFF"], tone="x").fond == "auto"
