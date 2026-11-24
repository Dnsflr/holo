import math

import numpy as np

from holo.camera import Camera
from holo.planets import (SATURN_RINGS, SaturnRings, make_texture, planet_axes, shade_planet)


def test_strona_zwrocona_do_slonca_jest_jasniejsza():
    tex = np.full((96, 192, 3), 0.8, np.float32)
    axes = planet_axes(0.0)
    light = np.array([1.0, 0.0, 0.0])            # Słońce po prawej stronie ekranu
    img = shade_planet(tex, 64, light, axes, 0.0)
    left = img[10, 32].mean()                    # [x][y]: x=10 – lewa krawędź
    right = img[53, 32].mean()
    assert right > left * 3


def test_tekstury_maja_poprawny_rozmiar_i_zakres():
    for style in ("earth", "mars", "jupiter", "saturn", "uranus", "neptune", "venus", "rocky_grey"):
        tex = make_texture(style, 1)
        assert tex.shape == (96, 192, 3)
        assert tex.min() >= 0 and tex.max() <= 1


def test_przerwa_cassiniego_jest_pusta():
    rings = SaturnRings(np.random.default_rng(0))
    assert not np.any((rings.r > 1.95) & (rings.r < 2.03))
    assert rings.r.min() >= SATURN_RINGS[0][0] and rings.r.max() <= SATURN_RINGS[-1][1]


def test_pierscien_za_planeta_jest_zasloniety():
    cam = Camera(1.0, tilt_deg=0.0)
    size = (400, 400)
    center = np.zeros(3, np.float32)
    radius = 0.2
    # Dwa punkty na osi widzenia: jeden przed planetą (z > 0 – bliżej widza), jeden za nią.
    pts = np.array([[0.0, 0.0, 0.4], [0.0, 0.0, -0.4], [0.6, 0.0, -0.4]], np.float32)
    rings = SaturnRings(np.random.default_rng(0), n=3)
    rings.bright = np.ones(3, np.float32)
    sx, sy, col, front = rings.visible(pts, center, radius, cam, size, np.array([0.0, 0.0, 1.0]),
                                       planet_axes(0.0))
    assert len(sx) == 2                  # punkt dokładnie za tarczą odrzucony
    assert front.sum() == 1              # jeden przed planetą
