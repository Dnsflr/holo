"""Rozmieszczenie widoków na ekranie.

Tryb "pyramid" – klasyczna piramida holograficzna kładziona czubkiem na środek
ekranu. Cztery widoki ułożone w krzyż, każdy z dołem obrazu skierowanym do
środka (bo w odbiciu to, co bliżej środka ekranu, widać niżej). Każdy widok
pokazuje galaktykę z innej strony, więc obchodząc piramidę widzisz ją w 3D.

Tryb "single" – jeden duży widok pod pojedynczą szybę ustawioną pod kątem 45°.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame


@dataclass
class Slot:
    pos: tuple[int, int]  # lewy górny róg na ekranie
    size: int             # bok kwadratu widoku
    azimuth: float        # z której strony kamera patrzy na galaktykę
    rotate: int           # obrót obrazu w stopniach (przeciwnie do zegara)
    flip_h: bool
    flip_v: bool


def make_layout(mode: str, screen_size: tuple[int, int], gap: float, flip: bool) -> list[Slot]:
    w, h = screen_size
    m = min(w, h)
    cx, cy = w // 2, h // 2

    if mode == "single":
        s = int(m * 0.95)
        return [Slot((cx - s // 2, cy - s // 2), s, 0.0, 0, False, flip)]

    s = int(m / (2 + gap))
    g = int(s * gap)
    half = s // 2
    # Domyślnie: odbicie w pionie (dół do środka). Z --flip: obrót o 180°.
    flip_h, flip_v = (True, False) if flip else (False, True)
    specs = [
        (0.0, 0, (cx - half, cy + g // 2)),               # dół ekranu
        (-math.pi / 2, 90, (cx + g // 2, cy - half)),     # prawo
        (math.pi, 180, (cx - half, cy - g // 2 - s)),     # góra
        (math.pi / 2, 270, (cx - g // 2 - s, cy - half)), # lewo
    ]
    return [Slot(pos, s, az, rot, flip_h, flip_v) for az, rot, pos in specs]


def place(img: pygame.Surface, slot: Slot) -> pygame.Surface:
    """Odbija i obraca wyrenderowany widok zgodnie ze slotem."""
    if slot.flip_h or slot.flip_v:
        img = pygame.transform.flip(img, slot.flip_h, slot.flip_v)
    if slot.rotate:
        img = pygame.transform.rotate(img, slot.rotate)
    return img
