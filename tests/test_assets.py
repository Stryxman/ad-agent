"""Étape 2 (analyse des assets) : la détection d'isolement ne nécessite pas rembg ; le détourage est
vérifié en simulant `_remove_background`, sans télécharger de modèle."""

from PIL import Image

from agent import assets


def _save(img: Image.Image, path) -> None:
    img.save(path)


def test_solid_background_is_isolated(tmp_path):
    img = Image.new("RGB", (200, 200), (240, 235, 225))
    for x in range(60, 140):
        for y in range(60, 140):
            img.putpixel((x, y), (10, 10, 10))  # un "produit" sombre au centre
    assert assets.looks_isolated(img)


def test_transparent_background_is_isolated():
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (200, 100, 50, 255))
    assert assets.looks_isolated(img)


def test_busy_photo_is_not_isolated(tmp_path):
    path = tmp_path / "photo.png"
    img = Image.new("RGB", (200, 200))
    px = img.load()
    for x in range(200):
        for y in range(200):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 5) % 256)  # bruit sur tout le cadre
    _save(img, path)
    with Image.open(path) as loaded:
        assert not assets.looks_isolated(loaded)


def test_ensure_isolated_skips_detourage_when_already_isolated(tmp_path, monkeypatch):
    path = tmp_path / "packshot.png"
    _save(Image.new("RGB", (100, 100), (250, 250, 250)), path)

    def boom(_path):
        raise AssertionError("le détourage ne doit pas être appelé sur une image déjà isolée")

    monkeypatch.setattr(assets, "_remove_background", boom)
    report = assets.ensure_isolated(path, cache_dir=tmp_path / "cache")
    assert report.isolated and report.action == "aucune" and report.used_path == str(path)


def test_ensure_isolated_detours_and_caches_by_content(tmp_path, monkeypatch):
    path = tmp_path / "photo.png"
    img = Image.new("RGB", (200, 200))
    px = img.load()
    for x in range(200):
        for y in range(200):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 5) % 256)
    _save(img, path)

    calls = []

    def fake_remove(p):
        calls.append(p)
        return b"donnees-detourees"

    monkeypatch.setattr(assets, "_remove_background", fake_remove)
    cache_dir = tmp_path / "cache"

    report1 = assets.ensure_isolated(path, cache_dir=cache_dir)
    assert not report1.isolated and report1.action == "detoure"
    assert open(report1.used_path, "rb").read() == b"donnees-detourees"
    assert len(calls) == 1

    report2 = assets.ensure_isolated(path, cache_dir=cache_dir)  # même contenu -> pas de recalcul
    assert report2.used_path == report1.used_path
    assert len(calls) == 1


def test_ensure_isolated_reports_failure_without_crashing(tmp_path, monkeypatch):
    path = tmp_path / "photo.png"
    img = Image.new("RGB", (200, 200))
    px = img.load()
    for x in range(200):
        for y in range(200):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 5) % 256)
    _save(img, path)

    def fail(_path):
        raise RuntimeError("rembg absent")

    monkeypatch.setattr(assets, "_remove_background", fail)
    report = assets.ensure_isolated(path, cache_dir=tmp_path / "cache")
    assert report.action == "echec" and "rembg absent" in report.note


def test_ensure_isolated_missing_file_is_reported(tmp_path):
    report = assets.ensure_isolated(tmp_path / "absent.png")
    assert report.action == "introuvable" and not report.isolated
