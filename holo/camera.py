"""Kamera: rzutowanie 3D → ekran, płynne loty, przybliżenia i obracanie myszą.

Układ współrzędnych sceny: płaszczyzna galaktyki to X-Z, oś Y to "góra"
(północny biegun galaktyki). Jednostka zależy od poziomu (np. kiloparsek).
"""
from __future__ import annotations

import math

import numpy as np

PERSPECTIVE = 4.0     # odległość kamery w "promieniach widoku" – mniej = mocniejsza perspektywa
DRAG_SPEED = 0.006    # radiany obrotu na piksel przeciągnięcia
SPIN_DECAY = 2.5      # jak szybko wygasa bezwładność po puszczeniu (większe = szybciej)
AUTO_RESUME_S = 8.0   # po ilu sekundach od interakcji wraca automatyczny obrót


class Camera:
    def __init__(self, view_radius: float, tilt_deg: float = 50.0, yaw: float = 0.0,
                 tilt_range: tuple[float, float] = (-80.0, 85.0)):
        # view_radius: ile jednostek świata mieści się w połowie krótszego boku ekranu przy zoom=1
        self.view_radius = view_radius
        self.target = np.zeros(3)
        self.zoom = 1.0
        self.tilt_min, self.tilt_max = (math.radians(a) for a in tilt_range)
        self.tilt = self._clamp_tilt(math.radians(tilt_deg))
        self.yaw = yaw
        self.yaw_speed = 0.02  # powolny automatyczny obrót wokół osi pionowej (rad/s)
        self.goal_target = self.target.copy()
        self.goal_zoom = self.zoom
        self.goal_tilt = self.tilt
        self.smooth = 2.2  # szybkość dochodzenia do celu (większa = szybciej)
        # Przesunięcie środka obrazu (ułamek szerokości ekranu) – robi miejsce na kartę informacji.
        self.offset_x = 0.0
        self.goal_offset_x = 0.0
        # Obracanie myszą: prędkości kątowe (bezwładność) i czas od ostatniej interakcji.
        self.spin_yaw = 0.0
        self.spin_tilt = 0.0
        self.dragging = False
        self.since_user = AUTO_RESUME_S
        self.goal_yaw: float | None = None  # opcjonalny docelowy obrót (np. na oświetloną stronę planety)

    def _clamp_tilt(self, a: float) -> float:
        return min(max(a, self.tilt_min), self.tilt_max)

    # ---------------------------------------------------------------- loty
    def fly_to(self, target=None, zoom: float | None = None, tilt_deg: float | None = None,
               offset_x: float | None = None) -> None:
        if offset_x is not None:
            self.goal_offset_x = offset_x
        if target is not None:
            self.goal_target = np.asarray(target, dtype=float)
        if zoom is not None:
            self.goal_zoom = zoom
        if tilt_deg is not None:
            self.goal_tilt = self._clamp_tilt(math.radians(tilt_deg))

    def jump(self) -> None:
        """Natychmiast przenosi kamerę do celu (bez animacji)."""
        self.target = self.goal_target.copy()
        self.zoom = self.goal_zoom
        self.tilt = self.goal_tilt
        self.offset_x = self.goal_offset_x

    # ------------------------------------------------------- obracanie myszą
    def drag(self, dx: float, dy: float, dt: float) -> None:
        """Przeciąganie: w bok obraca wokół pionu, w górę/dół zmienia pochylenie."""
        self.dragging = True
        self.goal_yaw = None
        self.since_user = 0.0
        d_yaw = dx * DRAG_SPEED
        d_tilt = dy * DRAG_SPEED
        self.yaw += d_yaw
        self.tilt = self.goal_tilt = self._clamp_tilt(self.tilt + d_tilt)
        # Prędkość do bezwładności – wygładzona, żeby jedno szarpnięcie nie dawało skoku.
        if dt > 0:
            self.spin_yaw = 0.6 * self.spin_yaw + 0.4 * (d_yaw / dt)
            self.spin_tilt = 0.6 * self.spin_tilt + 0.4 * (d_tilt / dt)

    def release(self) -> None:
        self.dragging = False
        self.since_user = 0.0

    def stop_spin(self) -> None:
        self.spin_yaw = self.spin_tilt = 0.0

    # ----------------------------------------------------------- aktualizacja
    def update(self, dt: float, auto_rotate: bool = True, real_dt: float | None = None) -> None:
        real_dt = dt if real_dt is None else real_dt
        k = 1.0 - math.exp(-real_dt * self.smooth)
        self.target = self.target + (self.goal_target - self.target) * k
        # Zoom interpolowany w skali logarytmicznej – lot wygląda równomiernie.
        self.zoom = math.exp(math.log(self.zoom) + (math.log(self.goal_zoom) - math.log(self.zoom)) * k)
        self.offset_x += (self.goal_offset_x - self.offset_x) * k

        if self.goal_yaw is not None and not self.dragging:
            diff = (self.goal_yaw - self.yaw + math.pi) % (2 * math.pi) - math.pi
            self.yaw += diff * k
            if abs(diff) < 1e-3:
                self.goal_yaw = None

        if self.dragging:
            # Gdy mysz stoi z wciśniętym przyciskiem, prędkość powoli spada do zera.
            self.spin_yaw *= math.exp(-real_dt * 10)
            self.spin_tilt *= math.exp(-real_dt * 10)
        else:
            self.since_user += real_dt
            self.yaw += self.spin_yaw * real_dt
            self.goal_tilt = self._clamp_tilt(self.goal_tilt + self.spin_tilt * real_dt)
            decay = math.exp(-real_dt * SPIN_DECAY)
            self.spin_yaw *= decay
            self.spin_tilt *= decay
            self.tilt += (self.goal_tilt - self.tilt) * k

        if auto_rotate:
            # Automatyczny obrót wraca płynnie po chwili bez interakcji.
            ramp = min(1.0, max(0.0, (self.since_user - AUTO_RESUME_S) / 3.0))
            self.yaw += self.yaw_speed * dt * ramp

    # ------------------------------------------------------------- rzutowanie
    def scale_px(self, size: tuple[int, int]) -> float:
        """Ile pikseli ekranu przypada na jednostkę świata (w środku widoku)."""
        return min(size) * 0.5 / self.view_radius * self.zoom

    def to_camera(self, vectors: np.ndarray, relative: bool = True) -> np.ndarray:
        """Obraca punkty (lub wektory, gdy relative=False) do układu kamery.

        Wynik (x, y, z): x w prawo, y w górę, z w stronę widza (bez perspektywy).
        """
        p = np.asarray(vectors, dtype=np.float32)
        if relative:
            p = p - self.target.astype(np.float32)
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        ca, sa = math.cos(self.yaw), math.sin(self.yaw)
        x1 = x * ca + z * sa
        z1 = -x * sa + z * ca
        ct, st = math.cos(self.tilt), math.sin(self.tilt)
        y2 = y * ct - z1 * st
        z2 = y * st + z1 * ct
        return np.stack([x1, y2, z2], axis=-1)

    def perspective(self, cam_pts: np.ndarray, size: tuple[int, int]):
        """Punkty w układzie kamery → (sx, sy, f, visible)."""
        x1, y2, z2 = cam_pts[:, 0], cam_pts[:, 1], cam_pts[:, 2]
        dist = PERSPECTIVE * self.view_radius / self.zoom
        visible = z2 < dist * 0.9
        f = dist / np.maximum(dist - z2, dist * 0.1)
        s = self.scale_px(size)
        sx = size[0] * (0.5 + self.offset_x) + x1 * f * s
        sy = size[1] / 2 - y2 * f * s
        return sx, sy, f, visible

    def project(self, points: np.ndarray, size: tuple[int, int]):
        """Zwraca (sx, sy, f, visible): pozycje w pikselach, współczynnik perspektywy, maskę widoczności."""
        return self.perspective(self.to_camera(points), size)

    def project_one(self, point, size):
        sx, sy, f, v = self.project(np.asarray(point, dtype=np.float32)[None, :], size)
        return float(sx[0]), float(sy[0]), float(f[0]), bool(v[0])
