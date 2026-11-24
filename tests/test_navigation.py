"""Scenariusz klikania: galaktyka → Słońce → Okolica Słońca → wstecz."""
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
    cfg = parse_args(["--windowed", "--stars", "3000", "--tour-after", "0"])
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


def test_klikanie_slonca_i_wejscie_do_okolicy(app):
    cursor = Cursor(SIZE)
    frames(app, 2, cursor)
    app.click(screen_pos(app, "sun"))
    assert app.selected.id == "sun"
    frames(app, 60, cursor)
    app.click(screen_pos(app, "sun"))          # drugie kliknięcie → wejście poziom niżej
    assert app.transition is not None
    frames(app, 60, cursor)
    assert app.current == "local" and app.transition is None


def test_klikniecie_w_pustke_odznacza(app):
    cursor = Cursor(SIZE)
    app.click(screen_pos(app, "sirius"))
    assert app.selected.id == "sirius"
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
