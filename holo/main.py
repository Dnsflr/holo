"""Pętla główna: okno, klawisze, składanie widoków na ekranie."""
from __future__ import annotations

import math

import numpy as np
import pygame

from .config import Config, parse_args
from .layout import make_layout, place
from .renderer import ViewRenderer
from .scene import Scene

PRECESSION_SPEED = 0.04  # powolne "kołysanie" osi galaktyki (rad/s)


def build_views(cfg: Config, screen: pygame.Surface, rng: np.random.Generator):
    slots = make_layout(cfg.mode, screen.get_size(), cfg.gap, cfg.flip)
    renderers = [ViewRenderer(s.size, s.azimuth, cfg, rng) for s in slots]
    return slots, renderers


def run(cfg: Config) -> None:
    cfg.trail = min(max(cfg.trail, 0.0), 0.95)

    pygame.init()
    pygame.display.set_caption("Holo – galaktyka")
    if cfg.windowed:
        screen = pygame.display.set_mode((cfg.width, cfg.height))
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)

    rng = np.random.default_rng(cfg.seed)
    scene = Scene(cfg, rng)
    slots, renderers = build_views(cfg, screen, rng)
    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()

    t = 0.0
    tilt = math.radians(cfg.tilt_deg)
    paused = False
    frame_no = 0
    running = True

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                if k in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif k == pygame.K_SPACE:
                    paused = not paused
                elif k == pygame.K_m:
                    cfg.mode = "single" if cfg.mode == "pyramid" else "pyramid"
                    slots, renderers = build_views(cfg, screen, rng)
                elif k == pygame.K_UP:
                    tilt = min(tilt + math.radians(5), math.radians(85))
                elif k == pygame.K_DOWN:
                    tilt = max(tilt - math.radians(5), math.radians(-85))
                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    cfg.speed = min(cfg.speed * 1.25, 8.0)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    cfg.speed = max(cfg.speed / 1.25, 0.05)
                elif k == pygame.K_g:
                    cfg.glow = not cfg.glow
                elif k == pygame.K_f:
                    cfg.show_fps = not cfg.show_fps

        dt = clock.tick(cfg.fps) / 1000.0
        if cfg.frames:  # tryb testowy: stały krok czasu
            dt = 1.0 / cfg.fps
        dt = 0.0 if paused else min(dt, 0.1) * cfg.speed
        t += dt
        precession = PRECESSION_SPEED * t

        frame = scene.update(t, dt, precession)
        screen.fill((0, 0, 0))
        for slot, renderer in zip(slots, renderers):
            img = place(renderer.render(frame, t, tilt, precession), slot)
            # Dodawanie zamiast nadpisywania – rogi widoków mogą na siebie zachodzić.
            screen.blit(img, slot.pos, special_flags=pygame.BLEND_ADD)

        if cfg.show_fps:
            txt = font.render(f"{clock.get_fps():.0f} FPS", True, (90, 90, 90))
            screen.blit(txt, (8, 8))

        pygame.display.flip()
        frame_no += 1
        if cfg.frames and frame_no >= cfg.frames:
            running = False

    if cfg.screenshot:
        pygame.image.save(screen, cfg.screenshot)
    pygame.quit()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
