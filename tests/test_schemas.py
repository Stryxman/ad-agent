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
