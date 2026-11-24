"""Konfiguracja programu i parsowanie argumentów linii komend."""
from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class Config:
    mode: str = "pyramid"      # "pyramid" (4 widoki) albo "single" (1 widok)
    windowed: bool = False     # okno zamiast pełnego ekranu
    width: int = 1280          # rozmiar okna (tylko z --windowed)
    height: int = 720
    fps: int = 30
    stars: int = 6000          # liczba gwiazd galaktyki
    arms: int = 2              # liczba ramion spiralnych
    render_scale: float = 0.6  # rozdzielczość renderowania względem widoku
    tilt_deg: float = 30.0     # nachylenie galaktyki
    speed: float = 1.0         # mnożnik prędkości animacji
    trail: float = 0.6         # wygładzanie / smugi gwiazd (0..0.95)
    gap: float = 0.3           # pusty środek w trybie pyramid (ułamek widoku)
    glow: bool = True          # poświata (bloom)
    flip: bool = False         # odwrócenie orientacji obrazu
    show_fps: bool = False
    seed: int = 7              # ziarno losowości – ta sama galaktyka przy każdym starcie
    frames: int = 0            # (test) zakończ po tylu klatkach
    screenshot: str | None = None  # (test) zapisz ostatnią klatkę do pliku


def parse_args(argv: list[str] | None = None) -> Config:
    d = Config()
    p = argparse.ArgumentParser(
        prog="holo",
        description="Holograficzna galaktyka dla Raspberry Pi (efekt Pepper's ghost).",
    )
    p.add_argument("--mode", choices=["pyramid", "single"], default=d.mode,
                   help="pyramid = 4 widoki pod piramidę, single = jeden widok pod pojedynczą szybkę")
    p.add_argument("--windowed", action="store_true",
                   help="okno zamiast pełnego ekranu (do testów na komputerze)")
    p.add_argument("--width", type=int, default=d.width)
    p.add_argument("--height", type=int, default=d.height)
    p.add_argument("--fps", type=int, default=d.fps)
    p.add_argument("--stars", type=int, default=d.stars, help="liczba gwiazd galaktyki")
    p.add_argument("--arms", type=int, default=d.arms, help="liczba ramion spiralnych")
    p.add_argument("--render-scale", type=float, default=d.render_scale,
                   help="rozdzielczość renderowania względem widoku (mniej = szybciej)")
    p.add_argument("--tilt", dest="tilt_deg", type=float, default=d.tilt_deg,
                   help="nachylenie galaktyki w stopniach")
    p.add_argument("--speed", type=float, default=d.speed, help="mnożnik prędkości animacji")
    p.add_argument("--trail", type=float, default=d.trail, help="smugi gwiazd 0..0.95")
    p.add_argument("--gap", type=float, default=d.gap,
                   help="pusty środek w trybie pyramid, jako ułamek rozmiaru widoku")
    p.add_argument("--no-glow", dest="glow", action="store_false", help="wyłącz poświatę")
    p.add_argument("--flip", action="store_true",
                   help="odwróć orientację obrazu (gdy w piramidzie/szybce galaktyka jest do góry nogami)")
    p.add_argument("--show-fps", action="store_true")
    p.add_argument("--seed", type=int, default=d.seed)
    p.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)
    p.add_argument("--screenshot", default=None, help=argparse.SUPPRESS)
    return Config(**vars(p.parse_args(argv)))
