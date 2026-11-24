"""Scenariusz klikania: mapa galaktyki → Słońce → Układ Słoneczny → wstecz."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from holo.config import parse_args
from holo.main import App
from holo.ui import Cursor

SIZE = (640, 360)


@pytest.fixture(scope="module")
def app():
    pygame.init()
    pygame.display.set_mode(SIZE)
    cfg = parse_args(["--windowed", "--stars", "3000", "--tour-after", "0", "--labels"])
    yield App(cfg, SIZE)
    pygame.quit()


def frames(app, n, cursor):
    frame = pygame.Surface(SIZE, 0, 32)
    for _ in range(n):
        app.update(1 / 30, 1 / 30, cursor)
        frame.fill((0, 0, 0))
        app.draw(frame, cursor)


def screen_pos(app, obj_id):
    return next((x, y) for o, x, y, r in app.level.hits if o.id == obj_id)


def test_klikanie_slonca_i_wejscie_do_ukladu_slonecznego(app):
    cursor = Cursor(SIZE)
    frames(app, 2, cursor)
    app.click(screen_pos(app, "sun"))
    assert app.selected.id == "sun"
    frames(app, 60, cursor)
    app.click(screen_pos(app, "sun"))          # drugie kliknięcie → wejście poziom niżej
    assert app.transition is not None
    frames(app, 60, cursor)
    assert app.current == "solar" and app.transition is None


def test_klikniecie_w_pustke_odznacza(app):
    cursor = Cursor(SIZE)
    frames(app, 2, cursor)
    app.click(screen_pos(app, "jupiter"))
    assert app.selected.id == "jupiter"
    app.click((5, 5))
    assert app.selected is None


def test_wstecz_wraca_do_galaktyki_i_zaznacza_slonce(app):
    cursor = Cursor(SIZE)
    app.back()
    frames(app, 60, cursor)
    assert app.current == "galaxy"
    assert app.selected.id == "sun"
    app.back()
    assert app.selected is None


def test_przeciaganie_nie_jest_kliknieciem(app):
    cursor = Cursor(SIZE)
    frames(app, 2, cursor)
    sel = app.selected
    yaw0 = app.cam.yaw
    app.press()
    for _ in range(10):
        app.motion(8, 0)
    app.release((5, 5))          # puszczenie w pustym miejscu – ale to było przeciąganie
    assert app.cam.yaw > yaw0
    assert app.selected is sel   # wybór się nie zmienił


def test_krotkie_klikniecie_dziala(app):
    cursor = Cursor(SIZE)
    frames(app, 2, cursor)
    app.press()
    app.motion(1, 1)
    app.release(screen_pos(app, "sun"))
    assert app.selected is not None and app.selected.id == "sun"


def test_wejscie_do_sceny_czarnej_dziury_i_powrot(app):
    cursor = Cursor(SIZE)
    if app.current != "galaxy":
        app.back(); frames(app, 60, cursor)
    if app.selected is not None:
        app.back()
    frames(app, 2, cursor)
    sgr = app.levels["galaxy"].find("sgr_a")
    app.select(sgr)
    frames(app, 30, cursor)
    app.click(screen_pos(app, "sgr_a"))
    frames(app, 60, cursor)
    assert app.current == "blackhole"
    app.click(screen_pos(app, "sgr_a_detail"))
    assert app.selected.id == "sgr_a_detail"
    app.back(); app.back()
    frames(app, 60, cursor)
    assert app.current == "galaxy" and app.selected.id == "sgr_a"


def test_scena_pulsara_klikanie_pulsara_i_mglawicy(app):
    cursor = Cursor(SIZE)
    if app.current != "galaxy":
        app.back(); app.back(); frames(app, 60, cursor)
    app.select(app.levels["galaxy"].find("crab"))
    frames(app, 30, cursor)
    app.click(screen_pos(app, "crab"))
    frames(app, 60, cursor)
    assert app.current == "crab"
    x, y = screen_pos(app, "crab_pulsar")
    app.click((x + 2, y + 1))
    assert app.selected.id == "crab_pulsar"
    app.click((x + 120, y))
    assert app.selected is None or app.selected.id == "crab_nebula"


def test_tryb_pokazowy_odwiedza_sceny(app):
    cursor = Cursor(SIZE)
    app.cfg.tour_after = 1.0
    app.idle = 5.0
    visited = set()
    for _ in range(30 * 120):           # do 2 minut pokazu
        app.update(1 / 30, 1 / 30, cursor)
        app.idle = 5.0                  # nikt nie rusza myszą
        visited.add(app.current)
        if {"blackhole", "crab"} <= visited:
            break
    app.cfg.tour_after = 0
    app.input_activity()
    assert {"blackhole", "crab"} <= visited


@pytest.fixture(scope="module")
def quiet_app():
    """Tryb bez napisów (domyślny)."""
    pygame.init()
    pygame.display.set_mode(SIZE)
    cfg = parse_args(["--windowed", "--stars", "3000", "--tour-after", "0"])
    return App(cfg, SIZE)


def test_bez_napisow_jedno_klikniecie_wlatuje_do_sceny(quiet_app):
    app = quiet_app
    cursor = Cursor(SIZE)
    frames(app, 2, cursor)
    app.click(screen_pos(app, "sgr_a"))
    assert app.transition is not None and app.transition["to"] == "blackhole"
    frames(app, 60, cursor)
    assert app.current == "blackhole"
    assert app.selected is not None and app.selected.id == "sgr_a_detail"   # focus z katalogu


def test_klawisz_t_przelacza_napisy(quiet_app):
    app = quiet_app
    assert app.labels is False
    app.set_labels(True)
    assert all(lv.show_text for lv in app.levels.values())
    app.set_labels(False)
    assert not any(lv.show_text for lv in app.levels.values())
