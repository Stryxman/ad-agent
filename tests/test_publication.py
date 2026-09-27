import json

from agent.loader import BRIEFS_DIR, load_brief
from agent.pipeline import run
from agent.publication import HEADLINE_MAX, PRIMARY_MAX, offline_publication, sentence
from agent.publication import testimonial_text as quoted_testimonial  # nom sans "test_" : pas collecté par pytest
from agent.schemas import Testimonial as Review  # alias : pytest collecte les classes « Test* »

BRIEF = load_brief(BRIEFS_DIR / "example_soin_peau.yaml")
HOOK = BRIEF.product.benefits[1]   # « Texture légère, non grasse » : 26 caractères


def test_hook_equal_to_a_benefit_is_not_repeated():
    pub, _ = offline_publication(BRIEF, HOOK)   # HOOK est aussi le 2e bénéfice du brief
    assert all(t.count(sentence(HOOK)) <= 1 for t in pub.primary_texts)


def test_lengths_are_respected():
    pub, _ = offline_publication(BRIEF, HOOK)
    assert pub.headlines and all(len(h) <= HEADLINE_MAX for h in pub.headlines)
    assert pub.primary_texts and all(len(p) <= PRIMARY_MAX for p in pub.primary_texts)
    assert len(pub.headlines) <= 3 and len(pub.primary_texts) <= 3


def test_offline_texts_only_contain_brief_sentences():
    pub, _ = offline_publication(BRIEF, HOOK)
    facts = [HOOK, BRIEF.product.description, BRIEF.offer, *BRIEF.product.benefits]
    for text in pub.primary_texts:
        if text == quoted_testimonial(BRIEF):
            continue
        rest = text
        for f in facts:
            rest = rest.replace(sentence(f), "")
        assert rest.strip() == "", text
    assert set(pub.headlines) <= {HOOK, BRIEF.offer, BRIEF.product.name}


def test_real_testimonial_is_quoted_verbatim_with_its_author():
    brief = BRIEF.model_copy(update={"testimonials": [Review(text="Léger et agréable.", author="Julie")]})
    pub, _ = offline_publication(brief, HOOK)
    assert "« Léger et agréable. » — Julie" in pub.primary_texts


def test_forbidden_claim_in_a_benefit_is_never_reused():
    brief = BRIEF.model_copy(update={"forbidden_claims": ["non grasse"]})
    pub, warnings = offline_publication(brief, "Un vrai plaisir")
    assert not any("non grasse" in t.lower() for t in pub.primary_texts + pub.headlines)


def test_brief_without_short_facts_gives_no_headline_and_a_warning():
    long_name = "Sérum Éclat Vitamine C Édition Limitée 30 ml"
    brief = BRIEF.model_copy(update={"offer": None, "testimonials": [],
                                     "product": BRIEF.product.model_copy(update={"name": long_name})})
    pub, warnings = offline_publication(brief, "Une accroche beaucoup trop longue pour un titre")
    assert pub.headlines == []
    assert any("titre" in w for w in warnings)


def test_run_exposes_publication_in_manifest_and_review(tmp_path):
    run_dir = run(BRIEFS_DIR / "example_soin_peau.yaml", out_root=tmp_path, render_png=False)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert all("publication" in v for v in manifest["variants"])
    assert any(v["publication"]["primary_texts"] for v in manifest["variants"])
    assert "Texte principal (" in (run_dir / "review.md").read_text(encoding="utf-8")


def test_testimonial_hook_is_quoted_with_its_author_never_spliced_into_brand_copy():
    t = BRIEF.testimonials[1]              # la variante « preuve sociale » porte cet avis-là
    pub, _ = offline_publication(BRIEF, t.text)
    assert t.text not in pub.headlines
    assert all(t.text not in p or p == f"« {t.text} » — {t.author}" for p in pub.primary_texts)
    assert f"« {t.text} » — {t.author}" in pub.primary_texts   # l'avis de CETTE variante, pas le premier
