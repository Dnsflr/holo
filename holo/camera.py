"""Kamera: rzutowanie 3D → ekran oraz płynne loty i przybliżenia.

Układ współrzędnych sceny: płaszczyzna galaktyki to X-Z, oś Y to "góra"
(północny biegun galaktyki). Jednostka zależy od poziomu (np. kiloparsek).
"""
from __future__ import annotations

import math

import numpy as np

PERSPECTIVE = 4.0  # odległość kamery w "promieniach widoku" – mniej = mocniejsza perspektywa


class Camera:
    def __init__(self, view_radius: float, tilt_deg: float = 50.0, yaw: float = 0.0):
        # view_radius: ile jednostek świata mieści się w połowie krótszego boku ekranu przy zoom=1
        self.view_radius = view_radius
        self.target = np.zeros(3)
        self.zoom = 1.0
        self.tilt = math.radians(tilt_deg)
        self.yaw = yaw
        self.yaw_speed = 0.02  # powolny obrót wokół osi pionowej (rad/s)
        self.goal_target = self.target.copy()
        self.goal_zoom = self.zoom
        self.goal_tilt = self.tilt
        self.smooth = 2.2  # szybkość dochodzenia do celu (większa = szybciej)

    def fly_to(self, target=None, zoom: float | None = None, tilt_deg: float | None = None) -> None:
        if target is not None:
            self.goal_target = np.asarray(target, dtype=float)
        if zoom is not None:
            self.goal_zoom = zoom
        if tilt_deg is not None:
            self.goal_tilt = math.radians(tilt_deg)

    def jump(self) -> None:
        """Natychmiast przenosi kamerę do celu (bez animacji)."""
        self.target = self.goal_target.copy()
        self.zoom = self.goal_zoom
        self.tilt = self.goal_tilt

    @property
    def moving(self) -> bool:
        return (abs(math.log(self.zoom / self.goal_zoom)) > 0.01
                or np.linalg.norm(self.target - self.goal_target) > 1e-3 * self.view_radius / self.zoom)

    def update(self, dt: float, auto_rotate: bool = True) -> None:
        k = 1.0 - math.exp(-dt * self.smooth)
        self.target = self.target + (self.goal_target - self.target) * k
        # Zoom interpolowany w skali logarytmicznej – lot wygląda równomiernie.
        self.zoom = math.exp(math.log(self.zoom) + (math.log(self.goal_zoom) - math.log(self.zoom)) * k)
        self.tilt += (self.goal_tilt - self.tilt) * k
        if auto_rotate:
            self.yaw += self.yaw_speed * dt

    def scale_px(self, size: tuple[int, int]) -> float:
        """Ile pikseli ekranu przypada na jednostkę świata (w środku widoku)."""
        return min(size) * 0.5 / self.view_radius * self.zoom

    def project(self, points: np.ndarray, size: tuple[int, int]):
        """Zwraca (sx, sy, f, visible): pozycje w pikselach, współczynnik perspektywy, maskę widoczności."""
        p = np.asarray(points, dtype=np.float32) - self.target.astype(np.float32)
        x, y, z = p[:, 0], p[:, 1], p[:, 2]

        ca, sa = math.cos(self.yaw), math.sin(self.yaw)
        x1 = x * ca + z * sa
        z1 = -x * sa + z * ca
        ct, st = math.cos(self.tilt), math.sin(self.tilt)
        y2 = y * ct - z1 * st
        z2 = y * st + z1 * ct

        dist = PERSPECTIVE * self.view_radius / self.zoom
        visible = z2 < dist * 0.9
        f = dist / np.maximum(dist - z2, dist * 0.1)
        s = self.scale_px(size)
        sx = size[0] / 2 + x1 * f * s
        sy = size[1] / 2 - y2 * f * s
        return sx, sy, f, visible

    def project_one(self, point, size):
        sx, sy, f, v = self.project(np.asarray(point, dtype=np.float32)[None, :], size)
        return float(sx[0]), float(sy[0]), float(f[0]), bool(v[0])
