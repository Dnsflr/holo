"""Poziomy nawigacji: Droga Mleczna → Okolica Słońca → Układ Słoneczny.

Każdy poziom ma własną skalę (view_radius), domyślne ustawienie kamery
i rysuje się w dwóch krokach: punkty do warstwy gwiazd + sprite'y na klatce.
"""
from __future__ import annotations

import math

import numpy as np
import pygame

from .camera import Camera
from .galaxy import MilkyWay
from .render import StarLayer
from .sprites import blit_scaled, radial_glow


class Level:
    title = ""
    view_radius = 1.0
    home_tilt = 50.0
    home_zoom = 1.0

    def make_camera(self) -> Camera:
        cam = Camera(self.view_radius, self.home_tilt, yaw=self.home_yaw())
        cam.zoom = cam.goal_zoom = self.home_zoom
        return cam

    def home_yaw(self) -> float:
        return 0.0

    def draw_points(self, layer: StarLayer, cam: Camera, size, t: float, alpha: float) -> None:
        pass

    def draw_sprites(self, frame: pygame.Surface, cam: Camera, t: float, alpha: float) -> None:
        pass


class GalaxyLevel(Level):
    title = "Droga Mleczna"
    view_radius = 16.0  # kpc
    home_tilt = 52.0

    def __init__(self, cfg, rng: np.random.Generator):
        self.galaxy = MilkyWay(cfg.stars, rng)
        self.core = radial_glow(256, (1.0, 0.82, 0.55), core=0.12, halo=0.45, core_w=0.85, halo_w=0.3)

    def home_yaw(self) -> float:
        # Słońce (x = -8,2 kpc) od strony widza, tak jak na typowych mapach galaktyki.
        return math.pi / 2

    def draw_points(self, layer, cam, size, t, alpha):
        g = self.galaxy
        sx, sy, f, vis = cam.project(g.points, size)
        cols = g.colors_at(t)[vis] * (alpha * np.minimum(f[vis], 2.0))[:, None]
        layer.add(sx[vis], sy[vis], cols)

    def draw_sprites(self, frame, cam, t, alpha):
        size = frame.get_size()
        cx, cy, f, vis = cam.project_one((0.0, 0.0, 0.0), size)
        if vis:
            d = 2 * 2.2 * cam.scale_px(size) * f
            blit_scaled(frame, self.core, (cx, cy), d, alpha * (0.85 + 0.08 * math.sin(t * 1.3)))
