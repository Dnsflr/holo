"""Animowany obraz supermasywnej czarnej dziury (Sagittarius A*).

Elementy, od tyłu:
- soczewkowany obraz tylnej części dysku – łuk nad cieniem (grawitacja zagina światło),
- tylna część dysku akrecyjnego (zasłaniana przez cień),
- cień czarnej dziury – na hologramie czarne jest przezroczyste, więc cień
  "rysuje" dopiero jasne otoczenie,
- przednia część dysku przechodząca przed cieniem,
- cienki pierścień fotonowy.
Strona dysku zbliżająca się do widza jest jaśniejsza (efekt Dopplera).

Klatki animacji liczone są raz przy starcie – na Raspberry Pi ważne, żeby
w trakcie działania tylko je wyświetlać.
"""
from __future__ import annotations

import math

import numpy as np
import pygame

from .sprites import array_to_surface

FRAMES = 40
ANIM_FPS = 12.0
SQUASH = 0.26  # spłaszczenie dysku (patrzymy prawie z boku)


def _make_frames(d: int, n_frames: int) -> list[pygame.Surface]:
    x, y = np.mgrid[0:d, 0:d].astype(np.float32)
    rs = d * 0.105                       # promień cienia w pikselach
    u = (x - (d - 1) / 2) / rs           # współrzędne w promieniach cienia
    v = (y - (d - 1) / 2) / rs           # v > 0 = niżej na ekranie = bliżej widza
    r = np.hypot(u, v)

    # Dysk w swojej płaszczyźnie (rozciągnięcie spłaszczenia).
    dv = v / SQUASH
    rd = np.hypot(u, dv)
    phi = np.arctan2(dv, u)
    r_in, r_out = 1.7, 4.6
    edge = np.clip((rd - r_in) / 0.35, 0, 1) * np.clip((r_out - rd) / 1.2, 0, 1)
    base = edge * (r_in / np.maximum(rd, r_in)) ** 1.6
    doppler = 1.0 - 0.6 * (u / np.maximum(rd, 1e-3))  # lewa strona (u<0) jaśniejsza

    # Łuk soczewkowania nad cieniem.
    arc_r = np.exp(-((r - 1.45) / 0.28) ** 2)
    arc_side = np.clip(0.25 - v / np.maximum(r, 1e-3), 0, 1.25)  # głównie u góry
    halo = np.exp(-(r / 3.2) ** 2) * 0.10
    ring = np.exp(-((r - 1.07) / 0.045) ** 2) * 1.1
    shadow = r < 1.0
    near = v > 0

    frames = []
    for i in range(n_frames):
        a = 2 * math.pi * i / n_frames
        # Turbulencje obracające się razem z dyskiem (całkowite częstotliwości → płynna pętla).
        texture = (1.0 + 0.28 * np.sin(5 * (phi + a) + 6.0 * rd)
                   + 0.16 * np.sin(11 * (phi + a) - 4.0 * rd)
                   + 0.10 * np.sin(17 * (phi + a) + 9.0 * rd))
        disk = base * doppler * texture
        lens = arc_r * arc_side * (1.0 - 0.25 * u / np.maximum(r, 1e-3)) * \
            (1.0 + 0.2 * np.sin(5 * (np.arctan2(v, u) + a)))

        back = (lens * 0.9 + np.where(near, 0, disk) + halo)
        back[shadow] = 0.0
        inten = back + np.where(near, disk, 0) + ring * (1 - 0.5 * near)

        # Kolor jak gorący gaz: pomarańczowy → żółty → biały wraz z jasnością.
        i3 = inten[..., None]
        rgb = i3 * np.array([1.0, 0.55, 0.18]) + (i3 ** 2) * np.array([0.0, 0.35, 0.6])
        frames.append(array_to_surface(rgb))
    return frames


class BlackHole:
    def __init__(self, size_px: int = 320):
        self.frames = _make_frames(size_px, FRAMES)
        self._cache_key = None
        self._cache: list[pygame.Surface] = []

    def draw(self, target: pygame.Surface, center, diameter: float, t: float, brightness: float = 1.0):
        d = int(min(diameter, 1.5 * min(target.get_size())))
        if d < 4 or brightness <= 0.01:
            return
        # Przeskalowane klatki trzymamy w pamięci podręcznej, dopóki rozmiar się nie zmienia
        # (rozmiar zaokrąglony, żeby podczas przybliżania nie liczyć ich co klatkę).
        d = max(4, int(round(d / 8) * 8))
        idx = int(t * ANIM_FPS) % FRAMES
        if self._cache_key != d:
            self._cache_key = d
            self._cache = [None] * FRAMES
        img = self._cache[idx]
        if img is None:
            img = pygame.transform.smoothscale(self.frames[idx], (d, d))
            self._cache[idx] = img
        if brightness < 0.999:
            img = img.copy()
            k = int(255 * brightness)
            img.fill((k, k, k), special_flags=pygame.BLEND_MULT)
        # Cień zasłania gwiazdy leżące za czarną dziurą.
        if brightness > 0.5:
            pygame.draw.circle(target, (0, 0, 0), (int(center[0]), int(center[1])), int(d * 0.1))
        target.blit(img, (int(center[0] - d / 2), int(center[1] - d / 2)), special_flags=pygame.BLEND_ADD)
