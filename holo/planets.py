"""Planety w 3D: kule oświetlone przez Słońce, obracające się wokół nachylonych osi,
oraz pierścienie Saturna z cząstek.

Obraz każdej planety liczony jest co klatkę w jej faktycznym rozmiarze na ekranie:
dla każdego piksela tarczy znamy normalną kuli (w układzie kamery), z niej
- jasność: iloczyn skalarny z kierunkiem do Słońca (widać fazy i stronę nocną),
- szerokość i długość geograficzną względem osi planety → kolor z tekstury.
Tekstury (mapy szerokość × długość) generowane są raz, z gładkiego szumu na sferze,
więc nie mają szwów.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pygame

TEX_W, TEX_H = 192, 96


@dataclass
class PlanetLook:
    style: str          # rodzaj tekstury
    tilt_deg: float     # nachylenie osi obrotu do płaszczyzny orbity
    spin: float         # prędkość obrotu na ekranie [rad/s] (umowna)
    atmosphere: tuple | None = None  # kolor poświaty atmosfery przy brzegu


# Nachylenia osi są prawdziwe; prędkości obrotu – poglądowe.
LOOKS = {
    "mercury": PlanetLook("rocky_grey", 0.03, 0.15),
    "venus": PlanetLook("venus", 177.4, -0.05, (1.0, 0.9, 0.6)),
    "earth": PlanetLook("earth", 23.4, 0.35, (0.45, 0.7, 1.0)),
    "mars": PlanetLook("mars", 25.2, 0.33, (1.0, 0.6, 0.4)),
    "jupiter": PlanetLook("jupiter", 3.1, 0.8, (1.0, 0.9, 0.75)),
    "saturn": PlanetLook("saturn", 26.7, 0.75, (1.0, 0.92, 0.7)),
    "uranus": PlanetLook("uranus", 97.8, -0.5, (0.6, 0.95, 1.0)),
    "neptune": PlanetLook("neptune", 28.3, 0.55, (0.45, 0.6, 1.0)),
}

# Pierścienie Saturna w promieniach planety: (od, do, jasność).
SATURN_RINGS = [
    (1.24, 1.53, 0.18),   # pierścień C – słaby
    (1.53, 1.95, 1.00),   # pierścień B – najjaśniejszy
    # 1,95–2,03: przerwa Cassiniego
    (2.03, 2.205, 0.62),  # pierścień A (wewnętrzna część)
    # 2,205–2,225: przerwa Enckego
    (2.225, 2.27, 0.55),  # pierścień A (zewnętrzna część)
]


# --------------------------------------------------------------------- tekstury
def _sphere_grid():
    lat = (0.5 - (np.arange(TEX_H) + 0.5) / TEX_H) * math.pi
    lon = (np.arange(TEX_W) + 0.5) / TEX_W * 2 * math.pi
    lon, lat = np.meshgrid(lon, lat)
    p = np.stack([np.cos(lat) * np.cos(lon), np.sin(lat), np.cos(lat) * np.sin(lon)], -1)
    return lat, lon, p


def sphere_noise(p: np.ndarray, rng: np.random.Generator, octaves: int = 5, base_freq: float = 1.5) -> np.ndarray:
    """Gładki szum na sferze: suma sinusoid o losowych kierunkach (bez szwów)."""
    out = np.zeros(p.shape[:-1])
    amp, freq, total = 1.0, base_freq, 0.0
    for _ in range(octaves):
        for _ in range(4):
            k = rng.normal(0, 1, 3)
            k = k / np.linalg.norm(k) * freq
            out += amp * np.sin(p @ k + rng.uniform(0, 2 * math.pi))
            total += amp
        amp *= 0.55
        freq *= 2.0
    return out / total


def make_texture(style: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    lat, lon, p = _sphere_grid()
    n = sphere_noise(p, rng)
    alat = np.abs(lat)

    def mix(a, b, t):
        t = np.clip(t, 0, 1)[..., None]
        return np.asarray(a) * (1 - t) + np.asarray(b) * t

    if style == "earth":
        land = n > 0.08
        tex = np.where(land[..., None],
                       mix((0.25, 0.45, 0.18), (0.55, 0.45, 0.28), (n - 0.08) * 4),
                       mix((0.05, 0.15, 0.45), (0.1, 0.3, 0.6), n + 0.6))
        ice = alat > math.radians(68) + 0.08 * n
        tex[ice] = (0.92, 0.95, 1.0)
        clouds = np.clip((sphere_noise(p, rng, base_freq=2.5) - 0.1) * 2.5, 0, 0.8)
        tex = tex * (1 - clouds[..., None]) + clouds[..., None] * np.array([0.95, 0.97, 1.0])
    elif style == "mars":
        tex = mix((0.75, 0.35, 0.18), (0.45, 0.22, 0.14), (n + 0.3) * 1.5)
        tex[alat > math.radians(78) + 0.05 * n] = (0.95, 0.93, 0.9)
    elif style == "jupiter":
        band = np.sin(lat * 14 + 0.6 * n) + 0.35 * np.sin(lat * 31 + n)
        tex = mix((0.92, 0.85, 0.72), (0.66, 0.45, 0.3), band * 0.5 + 0.5)
        # Wielka Czerwona Plama: owal na ok. 22° S.
        dlat = (lat + math.radians(22)) / math.radians(5)
        dlon = (np.mod(lon - 1.0 + math.pi, 2 * math.pi) - math.pi) / math.radians(11)
        spot = np.exp(-(dlat ** 2 + dlon ** 2) * 1.5)
        tex = tex * (1 - spot[..., None] * 0.7) + spot[..., None] * np.array([0.8, 0.35, 0.22]) * 0.7
    elif style == "saturn":
        band = np.sin(lat * 10 + 0.3 * n) + 0.3 * np.sin(lat * 25)
        tex = mix((0.95, 0.88, 0.66), (0.8, 0.68, 0.45), band * 0.5 + 0.5)
    elif style == "uranus":
        tex = mix((0.62, 0.88, 0.9), (0.55, 0.8, 0.86), np.sin(lat * 6) * 0.5 + 0.5 + 0.2 * n)
    elif style == "neptune":
        tex = mix((0.22, 0.38, 0.85), (0.3, 0.5, 0.95), np.sin(lat * 8 + 0.4 * n) * 0.5 + 0.5)
        dlat = (lat + math.radians(20)) / math.radians(6)
        dlon = (np.mod(lon - 2.0 + math.pi, 2 * math.pi) - math.pi) / math.radians(12)
        tex = tex * (1 - 0.5 * np.exp(-(dlat ** 2 + dlon ** 2))[..., None])
    elif style == "venus":
        tex = mix((0.95, 0.85, 0.6), (0.85, 0.7, 0.45), sphere_noise(p, rng, base_freq=1.0) + 0.5)
    else:  # rocky_grey – Merkury
        tex = mix((0.45, 0.43, 0.41), (0.72, 0.7, 0.67), n + 0.5)
    return np.clip(tex, 0, 1).astype(np.float32)


# ------------------------------------------------------------------- rysowanie
_grid_cache: dict[int, tuple] = {}


def _disk_grid(d: int):
    """Normalne kuli dla tarczy d×d pikseli (układ kamery: x w prawo, y w górę, z do widza)."""
    if d not in _grid_cache:
        c = (d - 1) / 2
        x, y = np.mgrid[0:d, 0:d].astype(np.float32)   # [x][y] jak w pygame.surfarray
        u = (x - c) / (d / 2)
        v = (y - c) / (d / 2)
        r2 = u * u + v * v
        inside = r2 <= 1.0
        z = np.sqrt(np.clip(1 - r2, 0, 1))
        normals = np.stack([u, -v, z], -1)
        _grid_cache[d] = (normals, inside, np.sqrt(r2))
        if len(_grid_cache) > 64:
            _grid_cache.pop(next(iter(_grid_cache)))
    return _grid_cache[d]


def planet_axes(tilt_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Oś obrotu P i dwa wektory równika (M, Q) w układzie sceny."""
    a = math.radians(tilt_deg)
    pole = np.array([0.0, math.cos(a), -math.sin(a)])
    m = np.array([1.0, 0.0, 0.0])
    q = np.cross(pole, m)
    return pole, m, q


def shade_planet(tex: np.ndarray, d: int, light_cam: np.ndarray, axes_cam, spin_angle: float,
                 atmosphere=None) -> np.ndarray:
    """Zwraca obraz (d, d, 3) 0..1 oświetlonej, obróconej planety."""
    normals, inside, rr = _disk_grid(d)
    pole, m, q = axes_cam
    nl = normals @ light_cam
    # Miękki terminator i odrobina światła rozproszonego (strona nocna nie jest idealnie czarna).
    light = np.clip((nl + 0.06) / 1.06, 0, 1) ** 0.85 + 0.09
    lat = np.arcsin(np.clip(normals @ pole, -1, 1))
    lon = np.arctan2(normals @ q, normals @ m) + spin_angle
    iy = np.clip(((0.5 - lat / math.pi) * TEX_H).astype(np.int32), 0, TEX_H - 1)
    ix = (np.mod(lon / (2 * math.pi), 1.0) * TEX_W).astype(np.int32) % TEX_W
    img = tex[iy, ix] * light[..., None]
    if atmosphere is not None:
        # Cienka atmosfera świecąca przy brzegu tarczy po stronie dziennej.
        rim = np.clip((rr - 0.75) / 0.25, 0, 1) ** 2 * np.clip(nl + 0.3, 0, 1)
        img += rim[..., None] * np.asarray(atmosphere, np.float32) * 0.45
    img[~inside] = 0.0
    return img


def to_surface(img: np.ndarray) -> pygame.Surface:
    arr = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    surf = pygame.Surface(arr.shape[:2], 0, 32)
    pygame.surfarray.blit_array(surf, arr)
    return surf


# ------------------------------------------------------------- pierścienie
class SaturnRings:
    def __init__(self, rng: np.random.Generator, n: int = 7000):
        widths = np.array([(b - a) * w for a, b, w in SATURN_RINGS])
        which = rng.choice(len(SATURN_RINGS), n, p=widths / widths.sum())
        lo = np.array([SATURN_RINGS[i][0] for i in which])
        hi = np.array([SATURN_RINGS[i][1] for i in which])
        self.r = (lo + (hi - lo) * rng.random(n)).astype(np.float32)
        self.a0 = rng.uniform(0, 2 * math.pi, n).astype(np.float32)
        b = np.array([SATURN_RINGS[i][2] for i in which])
        # Drobne "prążki" w pierścieniach.
        b = b * (0.75 + 0.25 * np.sin(self.r * 60)) * rng.uniform(0.6, 1.0, n)
        self.bright = b.astype(np.float32)

    def points(self, center: np.ndarray, radius: float, axes, t: float, stride: int = 1) -> np.ndarray:
        """Położenia cząstek w układzie sceny (pierścienie krążą – wewnętrzne szybciej)."""
        _, m, q = axes
        self._stride = stride
        r = self.r[::stride]
        a = self.a0[::stride] + t * 0.4 * (1.5 / r) ** 1.5
        rr = r * radius
        return (center[None, :] + (rr * np.cos(a))[:, None] * m + (rr * np.sin(a))[:, None] * q).astype(np.float32)

    def visible(self, pts: np.ndarray, center: np.ndarray, radius: float, cam, size, sun_dir: np.ndarray,
                axes, layer_k: float = 0.5):
        """Kolory cząstek z uwzględnieniem zasłaniania przez planetę i jej cienia.

        Zwraca (sx, sy, kolory, przed_planetą) tylko dla cząstek, które widać.
        """
        cp = cam.to_camera(pts)
        cc = cam.to_camera(center[None, :])[0]
        sx, sy, f, vis = cam.perspective(cp, size)
        cx, cy, cf, _ = cam.perspective(cc[None, :], size)
        r_px = radius * cf[0] * cam.scale_px(size)
        behind = cp[:, 2] < cc[2]
        covered = behind & ((sx - cx[0]) ** 2 + (sy - cy[0]) ** 2 < r_px * r_px)
        keep = vis & ~covered
        # Cień planety: cząstki po przeciwnej stronie niż Słońce, w "cylindrze" planety.
        w = pts - center[None, :]
        along = w @ sun_dir
        perp = np.linalg.norm(w - along[:, None] * sun_dir[None, :], axis=1)
        shadow = (along < 0) & (perp < radius)
        light = np.where(shadow, 0.1, 1.0)
        bright = self.bright[::getattr(self, "_stride", 1)][:len(pts)]
        # Jasność na piksel nie może zależeć od liczby cząstek: dzielimy przez ich gęstość
        # na ekranie (pole pierścieni w rzucie, w pikselach warstwy gwiazd).
        pole_cam = cam.to_camera(axes[0][None, :].astype(np.float32), relative=False)[0]
        facing = max(abs(float(pole_cam[2])), 0.12)
        k = layer_k * layer_k
        area = math.pi * (SATURN_RINGS[-1][1] ** 2 - SATURN_RINGS[0][0] ** 2) * r_px * r_px * facing * k
        density = len(pts) / max(area, 1.0)
        gain = 0.4 / max(density * float(bright.mean()), 0.4)
        col = np.array([0.9, 0.82, 0.66], np.float32)[None, :] * (bright * light * gain)[:, None]
        return sx[keep], sy[keep], col[keep], ~behind[keep]
