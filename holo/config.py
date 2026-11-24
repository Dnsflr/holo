"""Konfiguracja programu i parsowanie argumentów linii komend."""
from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class Config:
    windowed: bool = False     # okno zamiast pełnego ekranu
    width: int = 1280          # rozmiar okna (tylko z --windowed)
    height: int = 720
    fps: int = 30
    stars: int = 20000         # liczba gwiazd galaktyki
    render_scale: float = 0.5  # rozdzielczość renderowania gwiazd względem ekranu
    speed: float = 1.0         # mnożnik prędkości animacji
    glow: bool = True          # poświata (bloom)
    flip_h: bool = False       # odbicie lewo-prawo (lustro)
    flip_v: bool = False       # odbicie góra-dół
    calibrate: bool = False    # start od ekranu kalibracji odbicia
    tour_after: float = 60.0   # po tylu sekundach bez ruchu startuje tryb pokazowy (0 = wyłączony)
    show_fps: bool = False
    seed: int = 7              # ziarno losowości – ta sama galaktyka przy każdym starcie
    frames: int = 0            # (test) zakończ po tylu klatkach
    screenshot: str | None = None  # (test) zapisz ostatnią klatkę do pliku
    select: str | None = None      # (test) od razu wybierz obiekt o tym id
    yaw: float = 0.0               # (test) dodatkowy obrót kamery w stopniach
    tilt: float | None = None      # (test) pochylenie kamery w stopniach


def parse_args(argv: list[str] | None = None) -> Config:
    d = Config()
    p = argparse.ArgumentParser(
        prog="holo",
        description="Interaktywna holograficzna Droga Mleczna dla Raspberry Pi (ekran + plexi 45°).",
    )
    p.add_argument("--windowed", action="store_true",
                   help="okno zamiast pełnego ekranu (do testów na komputerze)")
    p.add_argument("--width", type=int, default=d.width)
    p.add_argument("--height", type=int, default=d.height)
    p.add_argument("--fps", type=int, default=d.fps)
    p.add_argument("--stars", type=int, default=d.stars, help="liczba gwiazd galaktyki")
    p.add_argument("--render-scale", type=float, default=d.render_scale,
                   help="rozdzielczość renderowania gwiazd (mniej = szybciej)")
    p.add_argument("--speed", type=float, default=d.speed, help="mnożnik prędkości animacji")
    p.add_argument("--no-glow", dest="glow", action="store_false", help="wyłącz poświatę")
    p.add_argument("--flip-h", action="store_true", help="odbij obraz lewo-prawo (napisy lustrzane)")
    p.add_argument("--flip-v", action="store_true", help="odbij obraz góra-dół (napisy do góry nogami)")
    p.add_argument("--calibrate", action="store_true",
                   help="zacznij od ekranu kalibracji odbicia (klawisze h / v)")
    p.add_argument("--tour-after", type=float, default=d.tour_after,
                   help="po ilu sekundach bezczynności program sam oprowadza po obiektach (0 = nigdy)")
    p.add_argument("--show-fps", action="store_true")
    p.add_argument("--seed", type=int, default=d.seed)
    p.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)
    p.add_argument("--screenshot", default=None, help=argparse.SUPPRESS)
    p.add_argument("--select", default=None, help=argparse.SUPPRESS)
    p.add_argument("--yaw", type=float, default=0.0, help=argparse.SUPPRESS)
    p.add_argument("--tilt", type=float, default=None, help=argparse.SUPPRESS)
    return Config(**vars(p.parse_args(argv)))
