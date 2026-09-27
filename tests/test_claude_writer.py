"""Tests du rédacteur Claude avec un faux client : aucun appel réseau, aucune clé."""

import json
from types import SimpleNamespace

import pytest

from agent.claude_writer import (
    AngleDraft, AnglesDraft, ClaudeWriter, CopyDraft, ZoneDraft, brief_facts, check_text,
)
from agent.loader import BRIEFS_DIR, load_all_formats, load_brief
from agent.pipeline import run
from agent.writers import WriterError

BRIEF = load_brief(BRIEFS_DIR / "example_soin_peau.yaml")
FORMATS = {f.id: f for f in load_all_formats()}


class FakeClient:
    """Imite `client.messages.parse` : renvoie des réponses préparées selon le schéma demandé."""

    def __init__(self, angles=None, copy=None):
        self.calls = []
        self._angles, self._copy = angles, copy
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        schema = kwargs["output_format"]
        parsed = self._angles if schema is AnglesDraft else self._copy
        usage = SimpleNamespace(input_tokens=100, output_tokens=50)
        return SimpleNamespace(parsed_output=parsed, stop_reason="end_turn", usage=usage)


def _angles(*angles):
    return AnglesDraft(angles=list(angles))


def test_angles_are_filtered_by_code_checks():
    client = FakeClient(angles=_angles(
        AngleDraft(hook_type="benefit", rationale="ok", hooks=[
            "Un teint plus lumineux au quotidien",   # accepté
            "Ce sérum guérit les taches",              # promesse interdite
            "Résultats visibles en 12 jours",          # chiffre absent du brief
        ]),
        AngleDraft(hook_type="curiosity", rationale="ok", hooks=["Et si votre routine tenait en un geste ?"]),
    ))
    angles = {a.id: a for a in ClaudeWriter(client=client).propose_angles(BRIEF)}
    assert angles["a_benefit"].hooks == ["Un teint plus lumineux au quotidien"]
    assert "a_curiosity" in angles


def test_offer_angle_starts_with_the_exact_offer_and_proof_uses_real_reviews():
    client = FakeClient(angles=_angles(
        AngleDraft(hook_type="offer", rationale="ok", hooks=["Offrez-vous l'éclat à -20 %"]),
    ))
    angles = {a.id: a for a in ClaudeWriter(client=client).propose_angles(BRIEF)}
    assert angles["a_offer"].hooks[0] == BRIEF.offer
    assert angles["a_proof"].hooks == [t.text for t in BRIEF.testimonials]  # jamais réécrits


def test_request_uses_structured_output_and_model_is_configurable(monkeypatch):
    client = FakeClient(angles=_angles(AngleDraft(hook_type="benefit", rationale="r", hooks=["Texture légère"])))
    ClaudeWriter(client=client, model="claude-sonnet-5").propose_angles(BRIEF)
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5"
    assert call["output_format"] is AnglesDraft
    prompt = call["messages"][0]["content"]
    assert "assets/products" not in prompt and "#F4E9DD" not in prompt  # ni chemins ni couleurs envoyés


def test_copy_keeps_prices_and_reviews_deterministic_and_rejects_bad_text():
    fmt = FORMATS["offre_prix_barre"]
    client = FakeClient(copy=CopyDraft(zones=[
        ZoneDraft(zone_id="headline", text="Le prix passe à 5 € seulement"),   # chiffre inventé
        ZoneDraft(zone_id="cta", text="Je découvre"),                          # accepté (≤ 15 car.)
        ZoneDraft(zone_id="price_new", text="1 €"),                            # zone protégée : ignorée
    ]))
    zones, warnings = ClaudeWriter(client=client).write_copy(BRIEF, BRIEF.offer, fmt)
    assert zones["price_new"] == BRIEF.product.price and zones["price_old"] == BRIEF.product.compare_at_price
    assert zones["headline"] == BRIEF.offer                    # repli sur le brief
    assert zones["cta"] == "Je découvre"
    assert any("headline" in w and "chiffre" in w for w in warnings)


def test_copy_rejects_text_over_the_zone_limit():
    fmt = FORMATS["fond_uni_packshots_prix"]
    limit = next(z.max_chars for z in fmt.zones if z.id == "headline")
    client = FakeClient(copy=CopyDraft(zones=[ZoneDraft(zone_id="headline", text="x" * (limit + 5))]))
    zones, warnings = ClaudeWriter(client=client).write_copy(BRIEF, "Texture légère, non grasse", fmt)
    assert zones["headline"] == "Texture légère, non grasse"
    assert any("trop long" in w for w in warnings)


def test_list_zone_is_split_validated_and_capped():
    fmt = FORMATS["infographie_probleme"]
    client = FakeClient(copy=CopyDraft(zones=[ZoneDraft(
        zone_id="lines",
        text="\n".join([
            "Une routine trop longue le matin",
            "Des produits qui ne conviennent pas",
            "Ce sérum guérit tout en une nuit",          # promesse interdite -> rejetée
            "Résultats visibles en 9 jours",              # chiffre absent du brief -> rejetée
            "Un flacon qui traîne dans le sac",
            "Une texture qui laisse un film gras",
            "Un rituel remis à plus tard",
        ]),
    )]))
    zones, warnings = ClaudeWriter(client=client).write_copy(BRIEF, "Un vrai plaisir", fmt)
    assert zones["lines"] == [
        "Une routine trop longue le matin",
        "Des produits qui ne conviennent pas",
        "Un flacon qui traîne dans le sac",
        "Une texture qui laisse un film gras",
        "Un rituel remis à plus tard",
    ]
    assert len(zones["lines"]) == 5  # 7 lignes - 2 rejetées = 5, sous le plafond de 6
    assert any("promesse interdite" in w for w in warnings)
    assert any("chiffre" in w for w in warnings)


def test_list_zone_below_minimum_keeps_valid_lines_and_warns():
    fmt = FORMATS["infographie_probleme"]
    client = FakeClient(copy=CopyDraft(zones=[ZoneDraft(
        zone_id="lines", text="Une seule ligne valide ici",
    )]))
    zones, warnings = ClaudeWriter(client=client).write_copy(BRIEF, "Un vrai plaisir", fmt)
    # sous le minimum, la ligne valide est gardée (mieux qu'une zone totalement vide) ; le warning
    # signale le manque pour que ça reste visible dans review.md.
    assert zones["lines"] == ["Une seule ligne valide ici"]
    assert any("minimum" in w for w in warnings)


def test_check_text_rules():
    facts = json.dumps(brief_facts(BRIEF), ensure_ascii=False)
    from agent.claude_writer import _numbers
    allowed = _numbers(facts)
    assert check_text("Texture légère", 40, BRIEF, allowed) is None
    assert "interdite" in check_text("Résultats garantis !", 40, BRIEF, allowed)
    assert "trop long" in check_text("a" * 50, 40, BRIEF, allowed)
    assert check_text("En 4 semaines", 40, BRIEF, allowed) is None          # « 4 » vient du brief
    assert "chiffre" in check_text("En 9 semaines", 40, BRIEF, allowed)


def test_product_name_and_price_line_are_never_rewritten_by_the_model():
    fmt = FORMATS["carte_produit_catalogue"]
    client = FakeClient(copy=CopyDraft(zones=[
        ZoneDraft(zone_id="product_name", text="Le meilleur sérum du monde"),  # doit être ignoré
        ZoneDraft(zone_id="price_line", text="gratuit"),                       # doit être ignoré
    ]))
    zones, _ = ClaudeWriter(client=client).write_copy(BRIEF, BRIEF.offer, fmt)
    assert zones["product_name"] == BRIEF.product.name
    assert BRIEF.product.price in zones["price_line"]


def test_usage_is_tracked():
    client = FakeClient(angles=_angles(AngleDraft(hook_type="benefit", rationale="r", hooks=["Texture légère"])))
    writer = ClaudeWriter(client=client)
    writer.propose_angles(BRIEF)
    assert writer.usage == {"input_tokens": 100, "output_tokens": 50, "calls": 1}


def test_unusable_response_raises_a_readable_error():
    class Empty(FakeClient):
        def _parse(self, **kwargs):
            return SimpleNamespace(parsed_output=None, stop_reason="refusal", usage=None)

    with pytest.raises(WriterError, match="refusal"):
        ClaudeWriter(client=Empty()).propose_angles(BRIEF)


def test_full_run_with_the_claude_writer(tmp_path):
    client = FakeClient(
        angles=_angles(AngleDraft(hook_type="benefit", rationale="r", hooks=["Texture légère, non grasse"])),
        copy=CopyDraft(zones=[ZoneDraft(zone_id="headline", text="Texture légère"),
                              ZoneDraft(zone_id="cta", text="Découvrir")]),
    )
    run_dir = run(BRIEFS_DIR / "example_soin_peau.yaml", writer=ClaudeWriter(client=client),
                  out_root=tmp_path, render_png=False)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["writer"] == "claude" and manifest["usage"]["calls"] >= 2
    assert manifest["variants"]


def test_writer_error_leaves_no_empty_run_folder(tmp_path):
    class Boom(FakeClient):
        def _parse(self, **kwargs):
            return SimpleNamespace(parsed_output=None, stop_reason="refusal", usage=None)

    with pytest.raises(WriterError):
        run(BRIEFS_DIR / "example_soin_peau.yaml", writer=ClaudeWriter(client=Boom()), out_root=tmp_path,
            render_png=False)
    assert list(tmp_path.iterdir()) == []
