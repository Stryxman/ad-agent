from agent.colors import contrast_ratio, mix


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def test_mix_endpoints_return_the_inputs():
    for a, b in (("#F4E9DD", "#C9A27E"), ("#12131A", "#4FD1C5")):
        assert all(abs(x - y) <= 1 for x, y in zip(_rgb(mix(a, b, 0)), _rgb(a)))
        assert all(abs(x - y) <= 1 for x, y in zip(_rgb(mix(a, b, 1)), _rgb(b)))


def test_mix_is_perceptual_black_white_gives_mid_grey():
    r, g, b = _rgb(mix("#000000", "#FFFFFF", 0.5))
    assert max(r, g, b) - min(r, g, b) <= 1   # gris neutre
    assert 0x55 <= r <= 0x70                  # OKLab : ~#636363, pas le #808080 d'un mélange RGB naïf


def test_contrast_ratio_still_available_from_render():
    from agent.render import contrast_ratio as from_render
    assert from_render("#000000", "#FFFFFF") == contrast_ratio("#000000", "#FFFFFF") > 20
