"""Zawartość sceny: galaktyka, orbitujące ciała i komety.

Scena liczy wszystko w 3D raz na klatkę; renderery widoków tylko to rzutują.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

EMPTY = np.zeros((0, 3), np.float32)


@dataclass
class Frame:
    """Jedna klatka sceny."""
    star_pts: np.ndarray      # gwiazdy galaktyki (N,3) – idą do bufora ze smugami
    star_cols: np.ndarray     # kolory RGB 0..1 (N,3)
    overlay_pts: np.ndarray   # orbity, ogony, komety – rysowane bez smug
    overlay_cols: np.ndarray
    bodies: list              # [(pozycja (3,), kolor RGB 0..255, promień)]
    core_pulse: float         # jasność pulsującego jądra 0..1


class Galaxy:
    """Spiralna galaktyka z gwiazd rozłożonych wzdłuż ramion + centralne zgrubienie."""

    def __init__(self, n: int, arms: int, rng: np.random.Generator):
        arms = max(arms, 1)
        n_bulge = int(n * 0.2)
        n_disk = n - n_bulge

        # Dysk: promień z obciętego rozkładu wykładniczego (więcej gwiazd bliżej środka).
        length = 0.32
        u = rng.random(n_disk)
        r = -length * np.log(1 - u * (1 - np.exp(-1.0 / length)))
        r = 0.04 + r * 0.96
        arm = rng.integers(0, arms, n_disk)
        spread = rng.normal(0.0, 0.28, n_disk) * (1.1 - 0.6 * r)
        # Ramiona "wleką się" za obrotem, stąd minus.
        theta = arm * (2 * np.pi / arms) - r * 5.5 + spread
        between = rng.random(n_disk) < 0.15  # część gwiazd poza ramionami
        theta[between] = rng.uniform(0, 2 * np.pi, between.sum())
        height = rng.normal(0.0, 0.025, n_disk) * (1.0 - 0.5 * r)

        # Zgrubienie centralne: spłaszczona kula.
        bx = rng.normal(0, 0.12, n_bulge)
        bz = rng.normal(0, 0.12, n_bulge)
        by = rng.normal(0, 0.07, n_bulge)

        self.r = np.concatenate([r, np.hypot(bx, bz)]).astype(np.float32)
        self.theta = np.concatenate([theta, np.arctan2(bz, bx)]).astype(np.float32)
        self.h = np.concatenate([height, by]).astype(np.float32)
        self.n = n

        # Kolory: ciepłe w środku, niebieskie na zewnątrz, różowe mgławice w ramionach.
        warm = np.array([1.0, 0.82, 0.55])
        blue = np.array([0.55, 0.72, 1.0])
        pink = np.array([1.0, 0.4, 0.75])
        mix = np.clip(r / 0.7, 0, 1)[:, None]
        disk_col = warm * (1 - mix) + blue * mix
        nebula = (rng.random(n_disk) < 0.05) & ~between
        disk_col[nebula] = pink
        bulge_col = np.tile(warm, (n_bulge, 1)) * rng.uniform(0.9, 1.1, (n_bulge, 1))

        bright = rng.uniform(0.25, 1.0, n) ** 2 * 0.9
        bright[:n_disk][nebula] *= 1.6
        cols = np.concatenate([disk_col, bulge_col]) * bright[:, None]
        self.base_cols = cols.astype(np.float32)

        self.tw_phase = rng.uniform(0, 2 * np.pi, n).astype(np.float32)
        self.tw_rate = rng.uniform(1.0, 4.0, n).astype(np.float32)

    def update(self, spin: float, t: float):
        a = self.theta + spin
        pts = np.empty((self.n, 3), np.float32)
        pts[:, 0] = self.r * np.cos(a)
        pts[:, 1] = self.h
        pts[:, 2] = self.r * np.sin(a)
        twinkle = 0.8 + 0.2 * np.sin(self.tw_phase + self.tw_rate * t)
        return pts, self.base_cols * twinkle[:, None]


@dataclass
class Orbiter:
    """Świecące ciało na nachylonej orbicie wokół galaktyki."""
    radius: float
    speed: float      # rad/s (znak = kierunek)
    phase: float
    incl: float       # nachylenie orbity
    node: float       # obrót orbity wokół osi pionowej
    color: tuple      # RGB 0..255
    size: float

    def points(self, angles: np.ndarray, node_offset: float) -> np.ndarray:
        x = self.radius * np.cos(angles)
        z = self.radius * np.sin(angles)
        y = -z * math.sin(self.incl)
        z = z * math.cos(self.incl)
        node = self.node + node_offset
        cn, sn = math.cos(node), math.sin(node)
        return np.stack([x * cn + z * sn, y, -x * sn + z * cn], axis=-1).astype(np.float32)


DEFAULT_ORBITERS = [
    Orbiter(1.18, 0.45, 0.0, 0.35, 0.0, (120, 200, 255), 0.035),
    Orbiter(1.32, -0.30, 2.0, -0.55, 1.2, (255, 170, 90), 0.045),
    Orbiter(1.25, 0.22, 4.0, 0.95, 2.4, (200, 130, 255), 0.03),
]

RING_SAMPLES = np.linspace(0, 2 * np.pi, 260, endpoint=False)
TAIL_SAMPLES = 40
TAIL_ARC = 1.1  # długość ogona w radianach


class Comets:
    """Komety przelatujące co kilka sekund przez scenę."""

    PALETTE = [(0.7, 0.9, 1.0), (1.0, 0.9, 0.7), (0.8, 0.7, 1.0)]

    def __init__(self, rng: np.random.Generator):
        self.rng = rng
        self.items: list[dict] = []
        self.next_spawn = 1.5

    def _spawn(self):
        rng = self.rng
        start = rng.normal(size=3)
        start = start / np.linalg.norm(start) * 1.7
        target = rng.normal(0, 0.35, 3)
        direction = target - start
        speed = rng.uniform(0.5, 0.9)
        vel = direction / np.linalg.norm(direction) * speed
        self.items.append({
            "pos": start.astype(np.float32),
            "vel": vel.astype(np.float32),
            "age": 0.0,
            "life": 3.4 / speed,
            "color": np.array(self.PALETTE[rng.integers(len(self.PALETTE))], np.float32),
        })

    def update(self, t: float, dt: float):
        while t >= self.next_spawn:
            self._spawn()
            self.next_spawn += self.rng.uniform(2.5, 6.0)

        pts, cols = [], []
        alive = []
        k = np.linspace(0, 1, 30, dtype=np.float32)[:, None]
        for c in self.items:
            c["pos"] = c["pos"] + c["vel"] * dt
            c["age"] += dt
            if c["age"] > c["life"]:
                continue
            alive.append(c)
            # Łagodne pojawianie się i znikanie.
            life_frac = c["age"] / c["life"]
            fade = min(1.0, life_frac * 5, (1 - life_frac) * 5)
            tail = c["pos"] - c["vel"] * (k * 0.45)
            pts.append(tail)
            cols.append(c["color"] * ((1 - k) ** 2) * fade)
        self.items = alive
        if not pts:
            return EMPTY, EMPTY
        return np.concatenate(pts), np.concatenate(cols)


class Scene:
    def __init__(self, cfg, rng: np.random.Generator):
        self.galaxy = Galaxy(cfg.stars, 2, rng)
        self.orbiters = DEFAULT_ORBITERS
        self.comets = Comets(rng)

    def update(self, t: float, dt: float, precession: float) -> Frame:
        star_pts, star_cols = self.galaxy.update(0.12 * t - precession, t)

        o_pts, o_cols, bodies = [], [], []
        tail_k = np.linspace(0, 1, TAIL_SAMPLES)
        for o in self.orbiters:
            a = o.phase + o.speed * t
            col = np.array(o.color, np.float32) / 255.0
            # Delikatny pierścień całej orbity.
            o_pts.append(o.points(RING_SAMPLES, -precession))
            o_cols.append(np.tile(col * 0.12, (len(RING_SAMPLES), 1)))
            # Świecący ogon za ciałem.
            tail_angles = a - math.copysign(TAIL_ARC, o.speed) * tail_k
            o_pts.append(o.points(tail_angles, -precession))
            o_cols.append((col[None, :] * ((1 - tail_k) ** 1.5)[:, None] * 0.9).astype(np.float32))
            bodies.append((o.points(np.array([a]), -precession)[0], o.color, o.size))

        c_pts, c_cols = self.comets.update(t, dt)
        o_pts.append(c_pts)
        o_cols.append(c_cols)

        return Frame(
            star_pts=star_pts,
            star_cols=star_cols,
            overlay_pts=np.concatenate(o_pts).astype(np.float32),
            overlay_cols=np.concatenate(o_cols).astype(np.float32),
            bodies=bodies,
            core_pulse=0.8 + 0.2 * math.sin(t * 1.7),
        )
