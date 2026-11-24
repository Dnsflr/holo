"""Scena 3D: Sagittarius A* z bliska.

Co tu jest fizyką (uproszczoną), a nie tylko grafiką:
- dysk akrecyjny krąży ruchem keplerowskim (wewnętrzne części szybciej) i powoli
  opada do środka,
- efekt Dopplera: gaz lecący w stronę widza świeci jaśniej (natężenie ~ D³),
  a grawitacyjne poczerwienienie przygasza najbliższe okolice horyzontu,
- soczewkowanie grawitacyjne: światło z punktów za czarną dziurą biegnie po
  zakrzywionych torach; wzór soczewki punktowej daje dwa obrazy każdego punktu
  (łuk nad cieniem i słabszy pod nim) – dlatego widać tylną część dysku,
- cień ma promień ~2,6 promienia Schwarzschilda i z każdej strony jest kołem,
- gwiazdy S krążą po orbitach Keplera (S2 z prawdziwym mimośrodem 0,88).

Jednostka sceny: UNIT = 1 promień Schwarzschilda (r_s) * skala.
"""
from __future__ import annotations

import math

import numpy as np

from ..catalog import CelestialObject, temp_to_rgb
from ..levels import MIN_HIT_PX, Level
from ..sprites import blit_scaled, star_sprite

UNIT = 0.04                 # r_s w jednostkach sceny
R_SHADOW = 2.6 * UNIT       # promień cienia (≈ 3√3/2 r_s)
R_IN = 3.0 * UNIT           # wewnętrzna krawędź dysku (najmniejsza stabilna orbita)
R_OUT = 11.0 * UNIT
OMEGA_IN = 1.6              # prędkość kątowa na wewnętrznej krawędzi [rad/s] (zwolniona)
BETA_IN = 0.38              # prędkość gazu na wewnętrznej krawędzi jako ułamek c
INFLOW = 0.004              # tempo opadania gazu [jednostki/s]
GAS_WEIGHT = 0.5            # jasność rozmytej warstwy gazu względem ostrych punktów


def lens(rel: np.ndarray):
    """Soczewka punktowa dla punktów ZA czarną dziurą.

    rel – położenia względem czarnej dziury w układzie kamery (z < 0 = dalej od widza).
    Zwraca (obraz_główny, obraz_wtórny, jasność_główna, jasność_wtórna) w układzie kamery.
    Promień Einsteina dla źródła w odległości d za soczewką: R_E = sqrt(2 r_s d).
    """
    bx, by = rel[:, 0], rel[:, 1]
    beta = np.maximum(np.hypot(bx, by), 1e-6)
    re = np.sqrt(2 * UNIT * np.maximum(-rel[:, 2], 1e-6))
    root = np.sqrt(beta * beta + 4 * re * re)
    r1 = (beta + root) / 2          # obraz główny – po tej samej stronie, dalej od środka
    r2 = (root - beta) / 2          # obraz wtórny – po przeciwnej stronie, bliżej środka
    u = beta / re
    base = (u * u + 2) / (2 * u * np.sqrt(u * u + 4))
    mu1 = np.minimum(base + 0.5, 4.0)
    mu2 = np.minimum(np.maximum(base - 0.5, 0.0), 1.5)
    ux, uy = bx / beta, by / beta
    img1 = np.stack([ux * r1, uy * r1, rel[:, 2]], -1)
    img2 = np.stack([-ux * r2, -uy * r2, rel[:, 2]], -1)
    return img1, img2, mu1, mu2


def kepler_rotation(inc: float, node: float, argp: float) -> np.ndarray:
    """Macierz obrotu płaszczyzny orbity (płaszczyzna x-z, oś y = normalna)."""
    def ry(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])

    def rx(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    return ry(node) @ rx(inc) @ ry(argp)


def kepler_position(a: float, e: float, period: float, phase: float, rot: np.ndarray,
                    t: np.ndarray | float) -> np.ndarray:
    """Położenie na orbicie eliptycznej w chwili t (równanie Keplera, metoda Newtona)."""
    t = np.atleast_1d(np.asarray(t, dtype=float))
    m = 2 * math.pi * t / period + phase
    ecc = m.copy()
    for _ in range(12):
        ecc -= (ecc - e * np.sin(ecc) - m) / (1 - e * np.cos(ecc))
    x = a * (np.cos(ecc) - e)
    z = a * math.sqrt(1 - e * e) * np.sin(ecc)
    pts = np.stack([x, np.zeros_like(x), z], -1)
    return (pts @ rot.T).astype(np.float32)


class SStar:
    def __init__(self, a, e, inc_deg, node_deg, argp_deg, period, phase, temp_k, size):
        self.a, self.e, self.period, self.phase = a, e, period, phase
        self.rot = kepler_rotation(math.radians(inc_deg), math.radians(node_deg), math.radians(argp_deg))
        self.color = temp_to_rgb(temp_k)
        self.size = size
        self.path = kepler_position(a, e, period, 0.0, self.rot, np.linspace(0, period, 500, endpoint=False))

    def at(self, t: float) -> np.ndarray:
        return kepler_position(self.a, self.e, self.period, self.phase, self.rot, t)[0]


class BlackHoleScene(Level):
    key = "blackhole"
    title = "Sagittarius A*"
    note = "Rozmiary nieproporcjonalne, ruch zwolniony"
    view_radius = 0.7
    home_tilt = 12.0
    sprite_scale = 0.03

    def __init__(self, catalog: list[CelestialObject], rng: np.random.Generator):
        super().__init__(catalog)
        self._make_disk(rng)
        self._make_background(rng)

        # Gwiazdy S. Pierwsza to S2 (klikalna); orbity reszty są poglądowe.
        self.sstars = [
            SStar(1.05, 0.88, 40, 20, 60, 34.0, 1.2, 25000, 0.8),       # S2
            SStar(0.62, 0.55, 110, 70, 10, 22.0, 3.0, 22000, 0.55),
            SStar(0.78, 0.35, 75, 150, 200, 28.0, 0.4, 18000, 0.5),
            SStar(0.55, 0.70, 140, 250, 120, 18.0, 5.1, 30000, 0.5),
            SStar(0.9, 0.25, 20, 300, 40, 31.0, 2.2, 15000, 0.45),
        ]
        self.s_sprites = [star_sprite(96, s.color) for s in self.sstars]
        s2 = self.find("s2")
        if s2 is not None:
            s2.mover = self.sstars[0].at

    # ------------------------------------------------------------ budowa
    def _make_disk(self, rng):
        n = 12000
        r0 = R_IN + (R_OUT - R_IN) * rng.random(n) ** 1.5
        a0 = rng.uniform(0, 2 * math.pi, n)
        # Zgęstki gazu – rozciągają się w spiralne smugi przez różnicę prędkości.
        clumped = rng.random(n) < 0.4
        k = int(clumped.sum())
        centers_r = R_IN + (R_OUT - R_IN) * rng.random(180) ** 1.3
        centers_a = rng.uniform(0, 2 * math.pi, 180)
        idx = rng.integers(0, 180, k)
        r0[clumped] = np.clip(centers_r[idx] + rng.normal(0, 0.25 * UNIT, k), R_IN, R_OUT)
        a0[clumped] = centers_a[idx] + rng.normal(0, 0.15, k)
        self.r0 = r0.astype(np.float32)
        self.a0 = a0.astype(np.float32)
        self.h = (rng.normal(0, 1, n) * 0.025 * r0).astype(np.float32)
        bright = rng.uniform(0.45, 1.0, n)
        bright[clumped] *= 1.5
        self.bright = bright.astype(np.float32)
        self.sharp = rng.random(n) < 0.4  # część cząstek rysowana też ostro (szczegóły)

    def _make_background(self, rng):
        m = 2500
        v = rng.normal(0, 1, (m, 3))
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        self.bg = (v * rng.uniform(2.5, 4.0, (m, 1))).astype(np.float32)
        temps = rng.choice([3500, 5000, 6500, 9000, 20000], m)
        cols = np.array([temp_to_rgb(k) for k in temps], np.float32)
        self.bg_col = (cols * rng.uniform(0.1, 0.6, (m, 1)) ** 2).astype(np.float32)

    # ---------------------------------------------------------- dysk w chwili t
    def disk_state(self, t: float):
        span = R_OUT - R_IN
        r = R_IN + np.mod(self.r0 - R_IN - INFLOW * t, span)
        omega = OMEGA_IN * (r / R_IN) ** -1.5
        a = self.a0 + omega * t
        ca, sa = np.cos(a), np.sin(a)
        pos = np.stack([r * ca, self.h, r * sa], -1)
        beta = BETA_IN * np.sqrt(R_IN / r)
        vel = np.stack([-sa * beta, np.zeros_like(r), ca * beta], -1)
        # Kolor z temperatury: najgoręcej przy wewnętrznej krawędzi.
        x = (r - R_IN) / (R_OUT - R_IN)
        col = np.empty((len(r), 3), np.float32)
        col[:, 0] = 1.0
        col[:, 1] = np.clip(0.92 - 0.75 * x, 0.15, 1)
        col[:, 2] = np.clip(0.75 - 1.3 * x, 0.05, 1)
        # Wygaszanie na brzegach (gaz pojawia się na zewnątrz i znika przy horyzoncie).
        edge = np.clip((r - R_IN) / (0.4 * UNIT), 0, 1) * np.clip((R_OUT - r) / (2.5 * UNIT), 0, 1)
        grav = np.sqrt(np.clip(1 - UNIT / r, 0, 1))
        return pos, vel, col * (self.bright * edge * grav)[:, None]

    # ------------------------------------------------------------- rysowanie
    def draw_points(self, layer, cam, size, t, alpha):
        bh = cam.to_camera(np.zeros((1, 3), np.float32))[0]
        bx, by, bf, bvis = cam.project_one((0.0, 0.0, 0.0), size)
        shadow_px = R_SHADOW * bf * cam.scale_px(size)

        pos, vel, col = self.disk_state(t)
        cp = cam.to_camera(pos)
        cv = cam.to_camera(vel, relative=False)
        doppler = 1.0 / np.clip(1.0 - cv[:, 2], 0.3, None)
        col = col * (np.minimum(doppler ** 3, 6.0) * 0.55 * alpha)[:, None]

        rel = cp - bh
        behind = rel[:, 2] < 0

        gas = layer.gas or layer

        def add_cam(points_cam, colors, target=layer):
            sx, sy, f, vis = cam.perspective(points_cam, size)
            target.add(sx[vis], sy[vis], colors[vis])

        def add_disk(points_cam, colors, sharp):
            # Gaz: miękko w warstwie rozmytej + część cząstek ostro dla szczegółu.
            add_cam(points_cam, colors * GAS_WEIGHT * (gas.k / layer.k) ** 2, gas)
            add_cam(points_cam[sharp], colors[sharp] * 0.6)

        def add_lensed(rel_pts, colors, sharp=None):
            """Dodaje oba obrazy punktów leżących za czarną dziurą (poza cieniem)."""
            img1, img2, mu1, mu2 = lens(rel_pts)
            for img, mu in ((img1, mu1), (img2, mu2)):
                keep = np.hypot(img[:, 0], img[:, 1]) > R_SHADOW * 1.02
                if sharp is None:
                    add_cam(img[keep] + bh, colors[keep] * mu[keep, None])
                else:
                    add_disk(img[keep] + bh, colors[keep] * mu[keep, None], sharp[keep])

        # 1) Tło gwiazd za czarną dziurą też jest soczewkowane.
        bg_rel = cam.to_camera(self.bg) - bh
        bg_behind = bg_rel[:, 2] < 0
        add_lensed(bg_rel[bg_behind], self.bg_col[bg_behind] * alpha)
        add_cam(bg_rel[~bg_behind] + bh, self.bg_col[~bg_behind] * alpha)

        # 2) Tylna część dysku (soczewkowana) i tylne odcinki orbit.
        add_lensed(rel[behind], col[behind], self.sharp[behind])
        orbit_back, orbit_front = self._orbit_points(cam, bh, alpha)
        add_cam(orbit_back[0], orbit_back[1])

        # 3) Cień zasłania wszystko, co jest za nim.
        if bvis and alpha > 0.3:
            layer.clear_circle(bx, by, shadow_px)

        # 4) Przednia część dysku i orbit.
        add_disk(cp[~behind], col[~behind], self.sharp[~behind])
        add_cam(orbit_front[0], orbit_front[1])

        # 5) Pierścień fotonowy – jaśniejszy po stronie zbliżającego się gazu.
        if bvis:
            n_axis = cam.to_camera(np.array([[0.0, 1.0, 0.0]], np.float32), relative=False)[0]
            th_app = math.atan2(n_axis[0], -n_axis[1])
            th = np.linspace(0, 2 * math.pi, 720, endpoint=False)
            rr = shadow_px * 1.04
            ring_b = (0.35 + 0.5 * np.cos(th - th_app).clip(-0.6, 1)) * 0.7 * alpha
            ring_col = np.array([1.0, 0.78, 0.5], np.float32)[None, :] * ring_b[:, None]
            layer.add(bx + rr * np.cos(th), by - rr * np.sin(th), ring_col)

    def _orbit_points(self, cam, bh, alpha):
        back_p, back_c, front_p, front_c = [], [], [], []
        for i, s in enumerate(self.sstars):
            cp = cam.to_camera(s.path)
            col = np.array(s.color, np.float32) * (0.22 if i == 0 else 0.08) * alpha
            behind = (cp[:, 2] - bh[2]) < 0
            back_p.append(cp[behind])
            back_c.append(np.broadcast_to(col, (int(behind.sum()), 3)))
            front_p.append(cp[~behind])
            front_c.append(np.broadcast_to(col, (int((~behind).sum()), 3)))
        return ((np.concatenate(back_p), np.concatenate(back_c)),
                (np.concatenate(front_p), np.concatenate(front_c)))

    def draw_sprites(self, frame, cam, t, alpha):
        size = frame.get_size()
        bh = cam.to_camera(np.zeros((1, 3), np.float32))[0]
        bx, by, bf, _ = cam.project_one((0.0, 0.0, 0.0), size)
        shadow_px = R_SHADOW * bf * cam.scale_px(size)
        self.hits = []
        for i, s in enumerate(self.sstars):
            p = s.at(t)
            x, y, f, vis = cam.project_one(p, size)
            if not vis:
                continue
            # Gwiazda schowana za cieniem jest niewidoczna.
            behind = (cam.to_camera(p[None, :])[0, 2] - bh[2]) < 0
            if behind and math.hypot(x - bx, y - by) < shadow_px:
                continue
            d = min(size) * self.sprite_scale * s.size * f * cam.zoom ** 0.5 * 2.2
            blit_scaled(frame, self.s_sprites[i], (x, y), d, alpha)
            if i == 0:
                s2 = self.find("s2")
                if s2 is not None:
                    self.hits.append((s2, x, y, max(d * 0.3, MIN_HIT_PX)))
        detail = self.find("sgr_a_detail")
        if detail is not None:
            self.hits.append((detail, bx, by, max(shadow_px * 1.2, MIN_HIT_PX)))
        self.draw_note(frame, alpha)
