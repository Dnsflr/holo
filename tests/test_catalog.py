import json

import numpy as np
import pytest

from holo.catalog import galactic_to_scene, load_catalog, solar_orbit_radius, temp_to_rgb


@pytest.fixture(scope="module")
def catalog():
    return {o.id: o for o in load_catalog()}


def test_kazdy_poziom_ma_obiekty(catalog):
    levels = {o.level for o in catalog.values()}
    assert levels == {"galaxy", "local", "solar"}


def test_sgr_a_w_centrum(catalog):
    assert np.allclose(catalog["sgr_a"].pos, 0)


def test_slonce_8_2_kpc_od_centrum(catalog):
    sun = catalog["sun"].pos
    assert np.hypot(sun[0], sun[2]) == pytest.approx(8.2, abs=0.01)


def test_mglawica_carina_na_ramieniu_strzelca_kila(catalog):
    p = catalog["carina"].pos
    assert 7.0 < np.hypot(p[0], p[2]) < 8.5


def test_kierunek_na_centrum_galaktyki():
    # l = 0° patrzy ze Słońca prosto na centrum.
    p = galactic_to_scene(0, 0, 8.2)
    assert np.linalg.norm(p[[0, 2]]) < 0.05


def test_okolica_slonca_kolejnosc_odleglosci(catalog):
    d = {k: np.linalg.norm(catalog[k].pos) for k in ("proxima", "sirius", "betelgeuse", "m42")}
    assert d["proxima"] < d["sirius"] < d["betelgeuse"] < d["m42"] <= 1.0


def test_orbity_rosna_z_odlegloscia():
    radii = [solar_orbit_radius(a) for a in (0.387, 1.0, 5.2, 30.07)]
    assert radii == sorted(radii)
    assert radii[-1] == pytest.approx(1.0)


def test_kolor_gwiazdy_z_temperatury():
    r, g, b = temp_to_rgb(3000)
    assert r > b  # chłodna – czerwonawa
    r, g, b = temp_to_rgb(15000)
    assert b >= r  # gorąca – niebieskawa


def test_brak_pola_w_danych_daje_czytelny_blad(tmp_path):
    bad = {"objects": [{"id": "x", "level": "galaxy", "kind": "star"}]}
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="brak pól"):
        load_catalog(f)
