import math

import numpy as np
import pytest

from holo.scenes.blackhole3d import R_SHADOW, UNIT, kepler_position, kepler_rotation, lens


def test_soczewka_obrazy_po_obu_stronach_promienia_einsteina():
    rel = np.array([[0.05, 0.02, -0.3], [0.0, 0.2, -0.5], [0.3, 0.0, -0.1]], np.float32)
    img1, img2, mu1, mu2 = lens(rel)
    re = np.sqrt(2 * UNIT * -rel[:, 2])
    r1 = np.hypot(img1[:, 0], img1[:, 1])
    r2 = np.hypot(img2[:, 0], img2[:, 1])
    assert np.all(r1 >= re - 1e-6)
    assert np.all(r2 <= re + 1e-6)
    assert np.allclose(r1 * r2, re * re, rtol=1e-4)    # własność soczewki punktowej
    assert np.all(mu1 >= mu2)                          # obraz główny jaśniejszy


def test_soczewka_obraz_wtorny_po_przeciwnej_stronie():
    rel = np.array([[0.1, 0.0, -0.4]], np.float32)
    img1, img2, _, _ = lens(rel)
    assert img1[0, 0] > 0 and img2[0, 0] < 0


def test_punkt_tuz_za_dziura_daje_pierscien_poza_cieniem():
    rel = np.array([[1e-5, 0.0, -0.4]], np.float32)
    img1, _, _, _ = lens(rel)
    assert np.hypot(img1[0, 0], img1[0, 1]) > R_SHADOW


def test_orbita_keplera_peryapsis_i_okres():
    a, e, period = 1.0, 0.88, 10.0
    rot = kepler_rotation(math.radians(40), 0.3, 1.0)
    p0 = kepler_position(a, e, period, 0.0, rot, 0.0)[0]
    assert np.linalg.norm(p0) == pytest.approx(a * (1 - e), rel=1e-5)   # start w peryapsis
    p1 = kepler_position(a, e, period, 0.0, rot, period)[0]
    assert np.allclose(p0, p1, atol=1e-5)                               # po okresie ten sam punkt
    half = kepler_position(a, e, period, 0.0, rot, period / 2)[0]
    assert np.linalg.norm(half) == pytest.approx(a * (1 + e), rel=1e-4)  # apoapsis


def test_os_magnetyczna_pulsara_wiruje_pod_stalym_katem():
    from holo.scenes.crab import MAG_TILT, SPIN_HZ, CrabScene
    from holo.catalog import load_catalog
    scene = CrabScene(load_catalog(), np.random.default_rng(0))
    m0 = scene.magnetic_axis(0.0)
    m_half = scene.magnetic_axis(0.5 / SPIN_HZ)
    for m in (m0, m_half):
        assert math.acos(float(np.dot(m, scene.spin))) == pytest.approx(MAG_TILT, abs=1e-6)
    assert not np.allclose(m0, m_half)   # po pół obrotu oś wskazuje gdzie indziej
