"""Pętla główna: okno, mysz i klawisze, rysowanie klatki."""
from __future__ import annotations

import numpy as np
import pygame

from .config import Config, parse_args
from .levels import GalaxyLevel
from .output import Output
from .render import StarLayer
from .ui import Cursor, draw_calibration, text


class Backdrop:
    """Migoczące gwiazdy tła – nieruchome względem ekranu."""

    def __init__(self, size, rng: np.random.Generator):
        n = size[0] * size[1] // 3500
        self.x = rng.uniform(0, size[0], n)
        self.y = rng.uniform(0, size[1], n)
        self.col = rng.uniform(0.08, 0.35, (n, 1)) * np.array([[0.8, 0.85, 1.0]])
        self.phase = rng.uniform(0, 2 * np.pi, n)
        self.rate = rng.uniform(0.4, 2.0, n)

    def draw(self, layer: StarLayer, t: float) -> None:
        tw = 0.55 + 0.45 * np.sin(self.phase + self.rate * t)
        layer.add(self.x, self.y, self.col * tw[:, None])


def run(cfg: Config) -> None:
    pygame.init()
    pygame.display.set_caption("Holo – Droga Mleczna")
    if cfg.windowed:
        screen = pygame.display.set_mode((cfg.width, cfg.height))
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    size = screen.get_size()
    out = Output(screen, cfg.flip_h, cfg.flip_v)
    frame = pygame.Surface(size, 0, 32)

    # W oknie (testy na PC) kursor podąża za myszą systemową. Na pełnym ekranie
    # mysz jest "przechwycona" i liczy się tylko jej ruch – pozycja systemowego
    # kursora nie ma sensu, bo widz patrzy na odbicie.
    relative_mouse = not cfg.windowed
    pygame.mouse.set_visible(False)
    if relative_mouse:
        pygame.event.set_grab(True)
    cursor = Cursor(size)

    rng = np.random.default_rng(cfg.seed)
    layer = StarLayer(size, cfg.render_scale)
    backdrop = Backdrop(size, rng)
    level = GalaxyLevel(cfg, rng)
    cam = level.make_camera()

    clock = pygame.time.Clock()
    t = 0.0
    calibrating = cfg.calibrate
    paused = False
    frame_no = 0
    running = True

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.MOUSEMOTION:
                if relative_mouse:
                    cursor.move_by(*ev.rel)
                else:
                    cursor.move_to(out.to_logical(ev.pos))
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_q:
                    running = False
                elif k == pygame.K_c:
                    calibrating = not calibrating
                elif k == pygame.K_h and calibrating:
                    out.flip_h = not out.flip_h
                elif k == pygame.K_v and calibrating:
                    out.flip_v = not out.flip_v
                elif k == pygame.K_SPACE:
                    paused = not paused
                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    cfg.speed = min(cfg.speed * 1.25, 8.0)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    cfg.speed = max(cfg.speed / 1.25, 0.05)
                elif k == pygame.K_g:
                    cfg.glow = not cfg.glow
                elif k == pygame.K_f:
                    cfg.show_fps = not cfg.show_fps

        real_dt = clock.tick(cfg.fps) / 1000.0
        if cfg.frames:  # tryb testowy: stały krok czasu
            real_dt = 1.0 / cfg.fps
        real_dt = min(real_dt, 0.1)
        dt = 0.0 if paused else real_dt * cfg.speed
        t += dt
        cursor.update(real_dt)
        cam.update(dt)

        frame.fill((0, 0, 0))
        if calibrating:
            draw_calibration(frame, out.flip_h, out.flip_v)
        else:
            layer.begin()
            backdrop.draw(layer, t)
            level.draw_points(layer, cam, size, t, 1.0)
            frame.blit(layer.finish(cfg.glow), (0, 0))
            level.draw_sprites(frame, cam, t, 1.0)
        cursor.draw(frame)
        if cfg.show_fps:
            text(frame, f"{clock.get_fps():.0f} FPS", 24, (90, 90, 90), topleft=(8, 8))

        out.present(frame)
        frame_no += 1
        if cfg.frames and frame_no >= cfg.frames:
            running = False

    if cfg.screenshot:
        pygame.image.save(frame, cfg.screenshot)
    pygame.quit()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
