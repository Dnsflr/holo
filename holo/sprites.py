"""Obrazki generowane w numpy: poświaty, gwiazdy, mgławice."""
from __future__ import annotations

import numpy as np
import pygame


def array_to_surface(rgb: np.ndarray) -> pygame.Surface:
    """rgb: tablica (d, d, 3) wartości 0..1, indeksowana [x, y]."""
    arr = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    surf = pygame.Surface(arr.shape[:2], 0, 32)
    pygame.surfarray.blit_array(surf, arr)
    return surf


def radial(d: int):
    """Odległość każdego piksela od środka, w promieniach (0 = środek, 1 = brzeg)."""
    x, y = np.mgrid[0:d, 0:d].astype(np.float32)
    c = (d - 1) / 2
    return np.hypot(x - c, y - c) / (d / 2), x - c, y - c


def radial_glow(d: int, color, core: float = 0.15, halo: float = 0.5,
                core_w: float = 0.9, halo_w: float = 0.25) -> pygame.Surface:
    """Miękka, okrągła poświata: jasny środek + szerokie halo."""
    rr, _, _ = radial(d)
    inten = np.exp(-(rr / core) ** 2) * core_w + np.exp(-(rr / halo) ** 2) * halo_w
    inten[rr > 1] = 0
    return array_to_surface(inten[..., None] * np.asarray(color, np.float32))


def blit_scaled(target: pygame.Surface, sprite: pygame.Surface, center, diameter: float,
                brightness: float = 1.0) -> None:
    """Rysuje sprite addytywnie (czarne = przezroczyste) w zadanym rozmiarze i jasności."""
    d = int(diameter)
    if d < 2 or brightness <= 0.01:
        return
    max_d = 2 * max(target.get_size())
    d = min(d, max_d)
    img = pygame.transform.smoothscale(sprite, (d, d))
    if brightness < 0.999:
        k = int(255 * min(brightness, 1.0))
        img.fill((k, k, k), special_flags=pygame.BLEND_MULT)
    target.blit(img, (int(center[0] - d / 2), int(center[1] - d / 2)), special_flags=pygame.BLEND_ADD)
