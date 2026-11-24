import json

import numpy as np
import pytest

from holo.catalog import galactic_to_scene, load_catalog, solar_orbit_radius, temp_to_rgb


@pytest.fixture(scope="module")
def catalog():
    return {o.id: o for o in load_catalog()}


def test_kazdy_poziom_ma_obiekty(catalog):
    levels = {o.level for o in catalog.values()}
    assert levels == {"galaxy", "blackhole", "solar"} or levels == {"galaxy", "blackhole", "crab", "solar"}


def test_sgr_a_w_centrum(catalog):
    assert np.allclose(catalog["sgr_a"].pos, 0)


def test_slonce_8_2_kpc_od_centrum(catalog):
    sun = catalog["sun"].pos
    assert np.hypot(sun[0], sun[2]) == pytest.approx(8.2, abs=0.01)


def test_kierunek_na_centrum_galaktyki():
    # l = 0° patrzy ze Słońca prosto na centrum.
    p = galactic_to_scene(0, 0, 8.2)
    assert np.linalg.norm(p[[0, 2]]) < 0.05


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


def test_obiekty_na_mapie_prowadza_do_scen(catalog):
    assert catalog["sgr_a"].enter == "blackhole"
    assert catalog["sun"].enter == "solar"


def test_bledny_poziom_w_enter(tmp_path):
    bad = {"objects": [{"id": "x", "level": "galaxy", "kind": "star", "name": "X", "type": "T",
                        "params": [], "description": "", "l": 0, "b": 0, "dist_kpc": 1,
                        "enter": "nie_ma"}]}
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="enter"):
        load_catalog(f)
