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


_scaled_cache: dict[tuple[int, int], pygame.Surface] = {}


def scaled_sprite(sprite: pygame.Surface, d: int) -> pygame.Surface:
    """Przeskalowany sprite z pamięci podręcznej (rozmiar zaokrąglany, żeby nie skalować co klatkę)."""
    d = max(2, int(round(d / 3) * 3)) if d > 24 else max(2, int(d))
    key = (id(sprite), d)
    img = _scaled_cache.get(key)
    if img is None:
        if len(_scaled_cache) > 400:
            _scaled_cache.clear()
        img = pygame.transform.smoothscale(sprite, (d, d))
        _scaled_cache[key] = img
    return img


def blit_scaled(target: pygame.Surface, sprite: pygame.Surface, center, diameter: float,
                brightness: float = 1.0) -> None:
    """Rysuje sprite addytywnie (czarne = przezroczyste) w zadanym rozmiarze i jasności."""
    d = int(diameter)
    if d < 2 or brightness <= 0.01:
        return
    max_d = 2 * max(target.get_size())
    d = min(d, max_d)
    img = scaled_sprite(sprite, d)
    d = img.get_width()
    if brightness < 0.999:
        img = img.copy()
        k = int(255 * min(brightness, 1.0))
        img.fill((k, k, k), special_flags=pygame.BLEND_MULT)
    target.blit(img, (int(center[0] - d / 2), int(center[1] - d / 2)), special_flags=pygame.BLEND_ADD)


def star_sprite(d: int, color, spikes: bool = True) -> pygame.Surface:
    """Gwiazda: biały środek, kolorowa poświata i cztery promienie dyfrakcyjne."""
    rr, dx, dy = radial(d)
    col = np.asarray(color, np.float32)
    core = np.exp(-(rr / 0.07) ** 2)
    glow = np.exp(-(rr / 0.28) ** 2) * 0.55 + np.exp(-(rr / 0.6) ** 2) * 0.12
    rgb = core[..., None] * np.array([1.0, 1.0, 1.0]) + glow[..., None] * col
    if spikes:
        w = d * 0.012
        spike = (np.exp(-(dx / w) ** 2) + np.exp(-(dy / w) ** 2)) * np.clip(1 - rr, 0, 1) ** 2.5 * 0.5
        rgb += spike[..., None] * (0.4 + 0.6 * col)
    rgb[rr > 1] = 0
    return array_to_surface(rgb)


def nebula_sprite(d: int, color, seed: int) -> pygame.Surface:
    """Mgławica: nieregularna chmura z kilkudziesięciu rozmytych plam."""
    rng = np.random.default_rng(seed)
    x, y = np.mgrid[0:d, 0:d].astype(np.float32) / d - 0.5
    col = np.asarray(color, np.float32)
    inten = np.zeros((d, d), np.float32)
    tint = np.zeros((d, d, 3), np.float32)
    for _ in range(40):
        cx, cy = rng.normal(0, 0.12, 2)
        s = rng.uniform(0.03, 0.12)
        a = rng.uniform(0.15, 0.5)
        blob = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * s * s)) * a
        inten += blob
        shift = rng.uniform(0.7, 1.15, 3)  # lekko różne odcienie plam
        tint += blob[..., None] * col * shift
    # Ciemne "pasma pyłu" i drobne gwiazdy wewnątrz mgławicy.
    dust = 1 - 0.45 * np.exp(-((x * 0.8 + y * 0.5) ** 2) / 0.002)
    rgb = tint / max(inten.max(), 1e-6) * np.minimum(inten / max(inten.max(), 1e-6) * 1.6, 1)[..., None]
    rgb *= dust[..., None]
    for _ in range(12):
        sx, sy = (rng.normal(0, 0.1, 2) * d + d / 2).astype(int)
        if 0 <= sx < d and 0 <= sy < d:
            rgb[sx, sy] += 0.9
    r = np.hypot(x, y) * 2
    rgb *= np.clip((1 - r) * 3, 0, 1)[..., None]
    return array_to_surface(rgb)


def cluster_sprite(d: int, color, seed: int, globular: bool = True) -> pygame.Surface:
    """Gromada: rój gwiazd, gęsty w środku (kulista) albo luźny (otwarta)."""
    rng = np.random.default_rng(seed)
    rgb = np.zeros((d, d, 3), np.float32)
    col = np.asarray(color, np.float32)
    n = 260 if globular else 45
    spread = 0.11 if globular else 0.2
    pts = rng.normal(0, spread, (n, 2)) * d + d / 2
    for (px, py) in pts:
        ix, iy = int(px), int(py)
        if 1 <= ix < d - 1 and 1 <= iy < d - 1:
            b = rng.uniform(0.3, 1.0) * (1.0 if globular else 1.6)
            rgb[ix, iy] += col * b
            rgb[ix - 1:ix + 2, iy] += col * b * 0.3
            rgb[ix, iy - 1:iy + 2] += col * b * 0.3
    rr, _, _ = radial(d)
    rgb += (np.exp(-(rr / (0.35 if globular else 0.6)) ** 2) * (0.35 if globular else 0.12))[..., None] * col
    rgb[rr > 1] = 0
    return array_to_surface(rgb)


def sun_sprite(d: int, color) -> pygame.Surface:
    """Słońce z bliska: jasna tarcza z pociemnieniem brzegowym i korona."""
    rr, _, _ = radial(d)
    col = np.asarray(color, np.float32)
    disk_r = 0.38
    u = np.clip(rr / disk_r, 0, 1)
    disk = (rr <= disk_r) * (0.55 + 0.45 * np.sqrt(1 - u * u))
    corona = np.exp(-((rr - disk_r).clip(0) / 0.12) ** 1.2) * 0.6 * (rr > disk_r)
    glow = np.exp(-(rr / 0.7) ** 2) * 0.18
    rgb = disk[..., None] * (0.55 + 0.5 * col) + (corona + glow)[..., None] * col * np.array([1.0, 0.85, 0.6])
    rgb[rr > 1] = 0
    return array_to_surface(rgb)
