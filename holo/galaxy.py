"""Generator Drogi Mlecznej.

Model (uproszczony, ale zgodny z obecną wiedzą o kształcie naszej galaktyki):
- spiralna galaktyka z poprzeczką (dł. ~9 kpc, nachylona ~27° do linii Słońce–centrum),
- 4 ramiona logarytmiczne o kącie nachylenia ~13°:
  Strzelca–Kila, Perseusza, Tarczy–Centaura, Węgielnicy/Zewnętrzne,
- krótkie Ramię Oriona (ostroga), w którym leży Słońce, 8,2 kpc od centrum,
- pasma pyłu po wewnętrznej stronie ramion, różowe obszary H II, młode niebieskie gwiazdy.

Jednostka: kiloparsek (kpc, ok. 3260 lat świetlnych).

Współrzędne galaktocentryczne (X, Y, Z): X od Słońca w stronę centrum, Y w kierunku
obrotu (l = 90°), Z na północ. Słońce jest w (-8,2; 0; 0,02). Scena używa układu
(x, y, z) = (X, Z, -Y), czyli płaszczyzna galaktyki to x-z, a oś y jest pionowa.
"""
from __future__ import annotations

import math

import numpy as np

SUN_R = 8.2                       # odległość Słońca od centrum [kpc]
ARM_K = math.tan(math.radians(13))  # nachylenie ramion
# Ramię Strzelca–Kila przechodzi przez r=6,8 kpc przy kącie 178° (między Słońcem a centrum),
# dzięki temu Mgławice Carina, Orzeł i Laguna leżą na nim zgodnie z rzeczywistością.
ARM_R0 = 6.8
ARM_THETA0 = math.radians(178)
ARMS = [
    # (nazwa, przesunięcie kątowe, waga = ile gwiazd)
    ("Ramię Strzelca–Kila", 0.0, 0.8),
    ("Ramię Perseusza", -math.pi / 2, 1.4),
    ("Ramię Tarczy–Centaura", math.pi / 2, 1.4),
    ("Ramię Węgielnicy", math.pi, 0.8),
]
BAR_ANGLE = math.radians(153)     # kierunek bliższego końca poprzeczki
BAR_HALF = 4.5

WARM = np.array([1.0, 0.80, 0.55])
WHITE = np.array([1.0, 0.94, 0.82])
BLUE = np.array([0.62, 0.76, 1.0])
PINK = np.array([1.0, 0.38, 0.62])


def to_scene(X, Y, Z) -> np.ndarray:
    """Współrzędne galaktocentryczne → układ sceny (x, y, z) = (X, Z, -Y)."""
    return np.stack([X, Z, -Y], axis=-1).astype(np.float32)


def arm_theta(r, offset):
    """Kąt ramienia (spirala logarytmiczna) na promieniu r."""
    return ARM_THETA0 + offset + np.log(r / ARM_R0) / ARM_K


def _trunc_exp(rng, n, scale, lo, hi):
    """Losowanie z rozkładu wykładniczego obciętego do [lo, hi]."""
    u = rng.random(n)
    a, b = math.exp(-lo / scale), math.exp(-hi / scale)
    return -scale * np.log(a - u * (a - b))


class MilkyWay:
    def __init__(self, n: int, rng: np.random.Generator):
        parts = []  # (X, Y, Z, kolor, jasność)

        def add(X, Y, Z, col, bright):
            col = np.broadcast_to(col, (len(X), 3))
            parts.append((X, Y, Z, col, bright))

        # --- Poprzeczka i zgrubienie centralne ---
        nb = int(n * 0.12)
        u = np.clip(rng.normal(0, 1.7, nb), -BAR_HALF, BAR_HALF)
        v = rng.normal(0, 0.5, nb) * (1 - 0.5 * np.abs(u) / BAR_HALF)
        ca, sa = math.cos(BAR_ANGLE), math.sin(BAR_ANGLE)
        add(u * ca - v * sa, u * sa + v * ca, rng.normal(0, 0.28, nb),
            WARM * rng.uniform(0.85, 1.1, (nb, 1)), rng.uniform(0.3, 0.8, nb))

        ng = int(n * 0.08)
        add(rng.normal(0, 0.8, ng), rng.normal(0, 0.8, ng), rng.normal(0, 0.55, ng),
            WARM, rng.uniform(0.3, 0.8, ng))

        # --- Ramiona spiralne ---
        na = int(n * 0.50)
        weights = np.array([a[2] for a in ARMS])
        arm = rng.choice(len(ARMS), na, p=weights / weights.sum())
        offsets = np.array([a[1] for a in ARMS])[arm]
        r = _trunc_exp(rng, na, 4.5, 3.3, 16.0)
        width = 0.22 + 0.03 * r
        d = rng.normal(0, 1, na) * width          # odchylenie od środka ramienia
        theta = arm_theta(r, offsets) + rng.normal(0, 0.03, na)
        rr = r + d
        bright = rng.uniform(0.35, 1.0, na) ** 2 * 1.1
        # Pas pyłu po wewnętrznej stronie ramienia przyciemnia gwiazdy.
        rel = d / width
        bright[(rel > -0.75) & (rel < -0.2)] *= 0.22
        young = (np.abs(rel) < 0.7) & (rng.random(na) < 0.65)
        col = np.where(young[:, None], BLUE, WHITE)
        add(rr * np.cos(theta), rr * np.sin(theta), rng.normal(0, 0.09, na), col, bright)

        # --- Obszary H II: różowe skupiska w ramionach ---
        knots = 90
        per = max(4, int(n * 0.06) // knots)
        k_arm = rng.choice(len(ARMS), knots, p=weights / weights.sum())
        k_r = rng.uniform(4.0, 13.5, knots)
        k_t = arm_theta(k_r, np.array([a[1] for a in ARMS])[k_arm])
        kx = np.repeat(k_r * np.cos(k_t), per) + rng.normal(0, 0.12, knots * per)
        ky = np.repeat(k_r * np.sin(k_t), per) + rng.normal(0, 0.12, knots * per)
        add(kx, ky, rng.normal(0, 0.05, knots * per), PINK, rng.uniform(0.4, 1.0, knots * per))

        # --- Ramię Oriona (ostroga ze Słońcem) ---
        no = int(n * 0.04)
        r_o = rng.uniform(7.3, 9.6, no)
        t_o = math.pi + (r_o - SUN_R) * 0.42 + rng.normal(0, 0.025, no)
        r_o = r_o + rng.normal(0, 0.22, no)
        add(r_o * np.cos(t_o), r_o * np.sin(t_o), rng.normal(0, 0.08, no),
            np.where((rng.random(no) < 0.5)[:, None], BLUE, WHITE), rng.uniform(0.3, 1.0, no) ** 2)

        # --- Dysk: gwiazdy między ramionami ---
        nf = n - sum(len(p[0]) for p in parts)
        r_f = _trunc_exp(rng, nf, 3.4, 1.5, 17.0)
        t_f = rng.uniform(0, 2 * math.pi, nf)
        add(r_f * np.cos(t_f), r_f * np.sin(t_f), rng.normal(0, 0.18, nf),
            WHITE * 0.95, rng.uniform(0.15, 0.6, nf))

        X = np.concatenate([p[0] for p in parts])
        Y = np.concatenate([p[1] for p in parts])
        Z = np.concatenate([p[2] for p in parts])
        self.points = to_scene(X, Y, Z)
        cols = np.concatenate([p[3] for p in parts])
        bright = np.concatenate([p[4] for p in parts])[:, None]
        self.colors = (cols * bright * 0.55).astype(np.float32)
        self.tw_phase = rng.uniform(0, 2 * math.pi, len(X)).astype(np.float32)
        self.tw_rate = rng.uniform(0.8, 3.0, len(X)).astype(np.float32)

    def colors_at(self, t: float) -> np.ndarray:
        """Kolory z delikatnym migotaniem."""
        tw = 0.85 + 0.15 * np.sin(self.tw_phase + self.tw_rate * t)
        return self.colors * tw[:, None]
