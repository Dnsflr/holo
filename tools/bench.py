"""Pomiar wydajności: ile milisekund zajmuje jedna klatka na każdym poziomie.

Uruchomienie (z katalogu projektu):
    python3 tools/bench.py                 # rozdzielczość logiczna jak w programie (wysokość 540)
    python3 tools/bench.py --render-height 720
    python3 tools/bench.py --quality low

Działa bez okna, więc można go odpalić np. na Raspberry Pi przez SSH.
Wynik poniżej ~30 ms oznacza, że program zmieści się w limicie 30 FPS.
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from holo.config import parse_args  # noqa: E402
from holo.main import App, logical_size  # noqa: E402
from holo.ui import Cursor  # noqa: E402

LEVELS = ("galaxy", "blackhole", "crab", "solar")


def main() -> None:
    cfg = parse_args(["--tour-after", "0"] + sys.argv[1:])
    screen = (1920, 1080)
    size = logical_size(screen, cfg.render_height)
    pygame.init()
    pygame.display.set_mode(size)
    app = App(cfg, size)
    if app.quality is not None:
        app.quality.locked = True  # stały stopień jakości – porównywalne wyniki
    cursor = Cursor(size)
    frame = pygame.Surface(size, 0, 32)
    print(f"Rozdzielczość logiczna {size[0]}×{size[1]} (ekran {screen[0]}×{screen[1]}), "
          f"jakość: {app.quality_name()}")
    total = 0.0
    for key in LEVELS:
        app.current = key

        def run(n):
            for _ in range(n):
                app.update(1 / 30, 1 / 30, cursor)
                frame.fill((0, 0, 0))
                app.draw(frame, cursor)

        run(5)
        t0 = time.perf_counter()
        run(40)
        ms = (time.perf_counter() - t0) / 40 * 1000
        total += ms
        print(f"  {key:10s} {ms:6.1f} ms/klatkę  (~{1000 / ms:4.0f} FPS)")
    print(f"  {'średnio':10s} {total / len(LEVELS):6.1f} ms/klatkę")
    pygame.quit()


if __name__ == "__main__":
    main()
