"""Rzutowanie punktów 3D na płaski obraz widoku.

Układ współrzędnych galaktyki: płaszczyzna dysku to X-Z, oś Y to "góra".
Kamera patrzy z kierunku +Z; `tilt` pochyla galaktykę w stronę widza,
a `azimuth` obraca kamerę wokół osi pionowej (każda ścianka piramidy
patrzy z innej strony).
"""
from __future__ import annotations

import numpy as np

# Odległość kamery od środka – im mniejsza, tym mocniejsza perspektywa.
DISTANCE = 4.0


def project(points: np.ndarray, azimuth: float, tilt: float, size: int, scale: float):
    """Zwraca (sx, sy, f): współrzędne ekranowe i współczynnik perspektywy."""
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]

    ct, st = np.cos(tilt), np.sin(tilt)
    y1 = y * ct - z * st
    z1 = y * st + z * ct

    ca, sa = np.cos(azimuth), np.sin(azimuth)
    x2 = x * ca + z1 * sa
    z2 = -x * sa + z1 * ca

    f = DISTANCE / (DISTANCE - z2)
    half = size / 2.0
    sx = half + x2 * f * scale
    sy = half - y1 * f * scale
    return sx, sy, f
