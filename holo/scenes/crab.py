"""Scena 3D: Pulsar w Krabie i Mgławica Kraba.

- Pulsar wiruje wokół osi obrotu, a jego oś magnetyczna jest od niej odchylona
  (tu o 45°). Wzdłuż osi magnetycznej biegną dwie wiązki promieniowania – gdy
  któraś przechodzi przez kierunek do widza, pulsar mocno błyska (efekt latarni).
- Linie pola magnetycznego to pętle dipola r = L·sin²θ, obracające się z gwiazdą.
- Torus i dżety: świecący pierścień w płaszczyźnie równika i dwa strumienie
  wzdłuż osi obrotu – tak wnętrze Kraba wygląda na zdjęciach z teleskopu Chandra.
- Mgławica: niebieskawa poświata synchrotronowa w środku i kolorowe włókna gazu
  na zewnątrz, lekko "oddychająca".

Obrót pulsara jest bardzo zwolniony: naprawdę wykonuje ok. 30 obrotów na sekundę.
"""
from __future__ import annotations

import math

import numpy as np

from ..catalog import CelestialObject
from ..levels import MIN_HIT_PX, Level
from ..sprites import blit_scaled, radial_glow, star_sprite

SPIN_HZ = 0.35                      # obroty na sekundę na ekranie (naprawdę ~30)
MAG_TILT = math.radians(45)         # odchylenie osi magnetycznej od osi obrotu
SPIN_AXIS = np.array([0.0, math.sin(math.radians(60)), math.cos(math.radians(60))])  # celowo tak,
# żeby z domyślnego widoku wiązka omiatała widza
BEAM_LEN = 1.15
BEAM_HALF_ANGLE = math.radians(6)
NEB_AXES = np.array([1.0, 0.72, 0.78])  # Krab jest wydłużony (ok. 11 × 7 lat św.)


def basis(axis: np.ndarray):
    """Dwa wektory prostopadłe do osi (ortonormalna baza)."""
    a = axis / np.linalg.norm(axis)
    helper = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 0.0, 1.0])
    e1 = np.cross(a, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(a, e1)
    return a, e1, e2


class CrabScene(Level):
    key = "crab"
    title = "Pulsar w Krabie"
    note = "Obrót pulsara zwolniony – naprawdę 30 obrotów na sekundę; rozmiary nieproporcjonalne"
    view_radius = 1.25
    home_tilt = 15.0
    sprite_scale = 0.05

    def __init__(self, catalog: list[CelestialObject], rng: np.random.Generator):
        super().__init__(catalog)
        self.spin, self.s1, self.s2 = basis(SPIN_AXIS)
        self._make_nebula(rng)
        self._make_inner(rng)
        self._make_beams(rng)
        self._make_field_lines()
        self.pulsar_sprite = star_sprite(128, (0.75, 0.85, 1.0))
        self.flash_sprite = radial_glow(192, (0.7, 0.85, 1.0), core=0.08, halo=0.35, core_w=1.0, halo_w=0.4)
        self.flash = 0.0

    # ------------------------------------------------------------ budowa
    def _make_nebula(self, rng):
        # Wnętrze: rozmyta, niebieskawa poświata synchrotronowa.
        n = 6000
        v = rng.normal(0, 1, (n, 3))
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        r = rng.random(n) ** 0.6 * 0.85
        self.syn_pts = (v * r[:, None] * NEB_AXES).astype(np.float32)
        self.syn_col = (np.array([0.45, 0.6, 1.0]) * (0.25 * (1 - r) + 0.05)[:, None]).astype(np.float32)

        # Włókna: losowe "spacery" po powierzchni elipsoidy.
        fil_pts, fil_col = [], []
        palette = np.array([[1.0, 0.35, 0.2], [1.0, 0.55, 0.25], [0.85, 0.95, 0.4], [1.0, 0.75, 0.45]])
        for _ in range(140):
            d = rng.normal(0, 1, 3)
            d /= np.linalg.norm(d)
            step = rng.normal(0, 1, 3)
            step -= d * step.dot(d)
            step /= np.linalg.norm(step)
            shell = rng.uniform(0.7, 1.0)
            col = palette[rng.integers(len(palette))] * rng.uniform(0.5, 1.0)
            for _k in range(45):
                d = d + step * 0.035 + rng.normal(0, 0.012, 3)
                d /= np.linalg.norm(d)
                step = step + rng.normal(0, 0.25, 3)
                step -= d * step.dot(d)
                step /= np.linalg.norm(step)
                fil_pts.append(d * shell * NEB_AXES + rng.normal(0, 0.008, 3))
                fil_col.append(col)
        self.fil_pts = np.array(fil_pts, np.float32)
        self.fil_col = (np.array(fil_col) * 0.45).astype(np.float32)

    def _make_inner(self, rng):
        # Torus w płaszczyźnie równika pulsara + dwa słabsze pierścienie ("wisps").
        parts, cols = [], []
        for radius, n, b in ((0.17, 2200, 0.5), (0.26, 900, 0.25), (0.34, 700, 0.15)):
            a = rng.uniform(0, 2 * math.pi, n)
            rr = radius + rng.normal(0, 0.012, n)
            hh = rng.normal(0, 0.008, n)
            parts.append(np.stack([rr * np.cos(a), hh, rr * np.sin(a)], -1))
            cols.append(np.tile(np.array([0.75, 0.82, 1.0]) * b, (n, 1)) * rng.uniform(0.5, 1, (n, 1)))
        self.torus_local = np.concatenate(parts).astype(np.float32)   # (x, wzdłuż osi, z)
        self.torus_col = np.concatenate(cols).astype(np.float32)
        self.torus_angle = np.arctan2(self.torus_local[:, 2], self.torus_local[:, 0])
        self.torus_r = np.hypot(self.torus_local[:, 0], self.torus_local[:, 2])
        # Dżety wzdłuż osi obrotu.
        n = 700
        u = rng.random(n) ** 1.5 * 0.42 * rng.choice([-1, 1], n)
        spread = rng.normal(0, 0.012, (n, 2)) * (1 + 3 * np.abs(u)[:, None])
        self.jet_u = u.astype(np.float32)
        self.jet_spread = spread.astype(np.float32)
        self.jet_col = (np.array([0.6, 0.75, 1.0]) * (0.35 * (1 - np.abs(u) / 0.42))[:, None]).astype(np.float32)

    def _make_beams(self, rng):
        n = 1800
        self.beam_u0 = rng.random(n).astype(np.float32)                     # położenie wzdłuż wiązki 0..1
        ang = rng.uniform(0, 2 * math.pi, n)
        rad = np.sqrt(rng.random(n)) * math.tan(BEAM_HALF_ANGLE)
        self.beam_off = np.stack([rad * np.cos(ang), rad * np.sin(ang)], -1).astype(np.float32)
        self.beam_side = rng.choice([-1.0, 1.0], n).astype(np.float32)      # która z dwóch wiązek
        self.beam_b = rng.uniform(0.5, 1.0, n).astype(np.float32)

    def _make_field_lines(self):
        # Pętle dipola w układzie magnetycznym: r = L sin²θ.
        pts = []
        th = np.linspace(0.12, math.pi - 0.12, 90)
        for L in (0.1, 0.18, 0.28):
            for phi in np.linspace(0, 2 * math.pi, 8, endpoint=False):
                r = L * np.sin(th) ** 2
                pts.append(np.stack([r * np.sin(th) * math.cos(phi), r * np.cos(th),
                                     r * np.sin(th) * math.sin(phi)], -1))
        self.field_local = np.concatenate(pts).astype(np.float32)   # (x, wzdłuż osi mag., z)

    # ---------------------------------------------------------- stan w chwili t
    def magnetic_axis(self, t: float) -> np.ndarray:
        phase = 2 * math.pi * SPIN_HZ * t
        perp = self.s1 * math.cos(phase) + self.s2 * math.sin(phase)
        return self.spin * math.cos(MAG_TILT) + perp * math.sin(MAG_TILT)

    @staticmethod
    def _to_frame(local: np.ndarray, axis: np.ndarray, e1: np.ndarray, e2: np.ndarray) -> np.ndarray:
        """Punkty (x, wzdłuż osi, z) w lokalnym układzie → układ sceny."""
        return (local[:, 0:1] * e1 + local[:, 1:2] * axis + local[:, 2:3] * e2).astype(np.float32)

    # ------------------------------------------------------------- rysowanie
    def draw_points(self, layer, cam, size, t, alpha):
        gas = layer.gas or layer
        gas_k = (gas.k / layer.k) ** 2

        def add(points, cols, target=layer):
            sx, sy, f, vis = cam.project(points, size)
            target.add(sx[vis], sy[vis], cols[vis] * alpha)

        breathe = 1.0 + 0.015 * math.sin(t * 0.5)
        add(self.syn_pts * breathe, self.syn_col * gas_k * 2.2, gas)
        add(self.fil_pts * breathe, self.fil_col * gas_k * 1.2, gas)
        add(self.fil_pts * breathe, self.fil_col * 0.55)

        # Torus obraca się powoli razem z gazem wokół pulsara.
        a = self.torus_angle + t * 0.25
        local = np.stack([self.torus_r * np.cos(a), self.torus_local[:, 1], self.torus_r * np.sin(a)], -1)
        add(self._to_frame(local, self.spin, self.s1, self.s2), self.torus_col * 0.8)
        jets = self.jet_u[:, None] * self.spin + self.jet_spread[:, 0:1] * self.s1 + self.jet_spread[:, 1:2] * self.s2
        add(jets.astype(np.float32), self.jet_col)

        # Pole magnetyczne i wiązki – związane z osią magnetyczną, która wiruje.
        m, e1, e2 = basis(self.magnetic_axis(t))
        add(self._to_frame(self.field_local, m, e1, e2),
            np.tile(np.array([0.3, 0.75, 1.0], np.float32) * 0.22, (len(self.field_local), 1)))
        u = np.mod(self.beam_u0 + t * 0.6, 1.0)          # cząstki płyną wzdłuż wiązki
        along = (0.04 + u * BEAM_LEN) * self.beam_side
        dist = np.abs(along)
        beam = (along[:, None] * m + (self.beam_off[:, 0:1] * e1 + self.beam_off[:, 1:2] * e2) * dist[:, None])
        bcol = np.array([0.7, 0.85, 1.0], np.float32) * (self.beam_b * (1 - u) ** 1.3 * 0.9)[:, None]
        add(beam.astype(np.float32), bcol)
        add(beam.astype(np.float32), bcol * gas_k * 0.8, gas)

        # Błysk: jak blisko kierunku do widza jest któraś z wiązek.
        mc = cam.to_camera(m[None, :].astype(np.float32), relative=False)[0]
        ang = math.acos(min(1.0, abs(float(mc[2]))))
        self.flash = math.exp(-(ang / 0.16) ** 2)

    def draw_sprites(self, frame, cam, t, alpha):
        size = frame.get_size()
        x, y, f, vis = cam.project_one((0.0, 0.0, 0.0), size)
        self.hits = []
        if vis:
            base = min(size) * 0.05 * f * cam.zoom ** 0.5
            blit_scaled(frame, self.pulsar_sprite, (x, y), base, alpha)
            if self.flash > 0.02:
                blit_scaled(frame, self.flash_sprite, (x, y), base * (2 + 5 * self.flash), alpha * self.flash)
            neb = self.find("crab_nebula")
            pul = self.find("crab_pulsar")
            if neb is not None:
                self.hits.append((neb, x, y, 0.85 * cam.scale_px(size) * f))
            if pul is not None:
                self.hits.append((pul, x, y, max(base * 0.3, MIN_HIT_PX)))
        self.draw_note(frame, alpha)
