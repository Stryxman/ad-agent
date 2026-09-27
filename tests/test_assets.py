"""Étape 2 (analyse des assets) : la détection d'isolement ne nécessite pas rembg ; le détourage est
vérifié en simulant `_remove_background`, sans télécharger de modèle."""

from PIL import Image

from agent import assets


def _save(img: Image.Image, path) -> None:
    img.save(path)


def test_transparent_background_is_detected():
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (200, 100, 50, 255))
    assert assets.has_transparent_background(img)
    assert not assets.has_transparent_background(Image.new("RGB", (100, 100), (250, 250, 250)))


def test_ensure_isolated_skips_detourage_when_background_is_transparent(tmp_path, monkeypatch):
    path = tmp_path / "packshot.png"
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (20, 20, 20, 255))
    _save(img, path)

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


def test_ensure_isolated_reports_failure_for_any_exception_type(tmp_path, monkeypatch):
    """rembg/onnxruntime peuvent lever autre chose qu'un RuntimeError (image invalide, modèle
    corrompu...) : ça doit rester un échec proprement rapporté, jamais un crash du run."""
    path = tmp_path / "photo.png"
    img = Image.new("RGB", (200, 200))
    px = img.load()
    for x in range(200):
        for y in range(200):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 5) % 256)
    _save(img, path)

    def fail(_path):
        raise ValueError("modèle onnx corrompu")

    monkeypatch.setattr(assets, "_remove_background", fail)
    report = assets.ensure_isolated(path, cache_dir=tmp_path / "cache")
    assert report.action == "echec" and "modèle onnx corrompu" in report.note


def test_ensure_isolated_reports_failure_for_unreadable_image(tmp_path):
    """Un fichier corrompu/illisible par PIL ne doit pas faire planter tout le run."""
    path = tmp_path / "corrompu.png"
    path.write_bytes(b"ceci n'est pas une image")
    report = assets.ensure_isolated(path, cache_dir=tmp_path / "cache")
    assert report.action == "echec" and not report.isolated


def test_detoured_image_is_cropped_to_the_product(tmp_path, monkeypatch):
    """Le détourage garde la taille de la photo d'origine (marges transparentes) : sans recadrage, le produit
    paraît plus petit qu'il ne pourrait l'être dans la zone utile du gabarit."""
    import io

    path = tmp_path / "photo.png"
    img = Image.new("RGB", (200, 200))
    px = img.load()
    for x in range(200):
        for y in range(200):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 5) % 256)
    _save(img, path)

    def fake_remove(_p):
        out = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        for x in range(75, 125):
            for y in range(75, 125):
                out.putpixel((x, y), (200, 100, 50, 255))   # produit de 50 x 50 au centre
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()

    monkeypatch.setattr(assets, "_remove_background", fake_remove)
    report = assets.ensure_isolated(path, cache_dir=tmp_path / "cache")
    with Image.open(report.used_path) as cropped:
        assert cropped.size == (54, 54)   # 50 px de produit + 2 px de marge de chaque côté


def test_crop_ignores_the_faint_alpha_halo_left_by_background_removal(tmp_path, monkeypatch):
    """rembg laisse des pixels presque transparents (alpha 1 à 8) loin du produit : ils ne doivent pas
    élargir le recadrage."""
    import io

    path = tmp_path / "photo.png"
    img = Image.new("RGB", (200, 200))
    px = img.load()
    for x in range(200):
        for y in range(200):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 5) % 256)
    _save(img, path)

    def fake_remove(_p):
        out = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        for x in range(75, 125):
            for y in range(75, 125):
                out.putpixel((x, y), (200, 100, 50, 255))
        out.putpixel((3, 3), (0, 0, 0, 2))          # halo résiduel, invisible
        out.putpixel((196, 196), (0, 0, 0, 6))
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()

    monkeypatch.setattr(assets, "_remove_background", fake_remove)
    report = assets.ensure_isolated(path, cache_dir=tmp_path / "cache")
    with Image.open(report.used_path) as cropped:
        assert cropped.size == (54, 54)


def test_uniform_opaque_background_is_still_detoured(tmp_path, monkeypatch):
    """Un packshot sur fond blanc opaque est « isolé » pour l'œil, mais ce blanc apparaît en rectangle sur les
    fonds colorés des gabarits : il faut le détourer quand même (seul un fond transparent s'en passe)."""
    path = tmp_path / "casque_fond_blanc.png"
    img = Image.new("RGB", (100, 100), (250, 250, 250))
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (20, 20, 20))
    _save(img, path)
    calls = []
    monkeypatch.setattr(assets, "_remove_background", lambda p: calls.append(p) or b"detoure")
    report = assets.ensure_isolated(path, cache_dir=tmp_path / "cache")
    assert calls and report.action == "detoure"
