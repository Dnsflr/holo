"""Katalog klikalnych obiektów: wczytywanie z JSON-a i przeliczanie pozycji."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Callable
from pathlib import Path

import numpy as np

from .galaxy import SUN_R

DATA_FILE = Path(__file__).parent / "data" / "milky_way.json"
LEVELS = ("galaxy", "blackhole", "crab", "solar")
KINDS = ("black_hole", "star", "nebula", "cluster", "system", "planet", "pulsar")
REQUIRED = ("id", "level", "kind", "name", "type", "params", "description")

# Układ Słoneczny: promienie orbit w skali logarytmicznej; Merkury = 0,28, Neptun = 1.
SOLAR_MIN_AU = 0.387
SOLAR_MAX_AU = 30.07
# Czas jednego obiegu Ziemi wokół Słońca na ekranie [s].
EARTH_ORBIT_S = 24.0


@dataclass
class CelestialObject:
    id: str
    level: str
    kind: str
    name: str
    type: str
    params: list[tuple[str, str]]
    description: str
    pos: np.ndarray                      # pozycja w układzie sceny poziomu
    color: tuple[float, float, float]
    size: float = 1.0
    zoom: float = 4.0                    # przybliżenie kamery po wybraniu
    enter: str | None = None             # poziom, do którego prowadzi ponowne kliknięcie
    orbit_r: float = 0.0                 # tylko planety: promień orbity (jednostki sceny)
    orbit_w: float = 0.0                 # prędkość kątowa [rad/s]
    phase: float = 0.0
    ring: bool = False
    label: str | None = None             # stały podpis na mapie (np. „Czarna dziura”)
    focus: str | None = None             # obiekt zaznaczany po wejściu do sceny (enter)
    mover: Callable[[float], np.ndarray] | None = None  # własny ruch nadany przez scenę (np. S2)
    extra: dict = field(default_factory=dict)

    def position_at(self, t: float) -> np.ndarray:
        """Pozycja w chwili t (planety krążą, reszta stoi)."""
        if self.mover is not None:
            return self.mover(t)
        if self.orbit_r <= 0:
            return self.pos
        a = self.phase + self.orbit_w * t
        return np.array([self.orbit_r * math.cos(a), 0.0, -self.orbit_r * math.sin(a)], np.float32)


def direction(l_deg: float, b_deg: float) -> np.ndarray:
    """Kierunek (l, b) ze Słońca jako wektor w układzie sceny (x, y, z) = (X, Z, -Y)."""
    l, b = math.radians(l_deg), math.radians(b_deg)
    return np.array([math.cos(b) * math.cos(l), math.sin(b), -math.cos(b) * math.sin(l)], np.float32)


def galactic_to_scene(l_deg: float, b_deg: float, dist_kpc: float) -> np.ndarray:
    """Współrzędne galaktyczne widziane z Ziemi → pozycja w galaktyce (kpc, układ sceny)."""
    sun = np.array([-SUN_R, 0.02, 0.0], np.float32)
    return sun + direction(l_deg, b_deg) * dist_kpc


def solar_orbit_radius(a_au: float) -> float:
    if a_au <= 0:
        return 0.0
    return 0.28 + 0.72 * math.log(a_au / SOLAR_MIN_AU) / math.log(SOLAR_MAX_AU / SOLAR_MIN_AU)


def temp_to_rgb(kelvin: float) -> tuple[float, float, float]:
    """Przybliżony kolor ciała doskonale czarnego o danej temperaturze."""
    t = kelvin / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708 * math.log(t) - 161.1196
        b = 0.0 if t <= 19 else 138.5177 * math.log(t - 10) - 305.0448
    else:
        r = 329.6987 * (t - 60) ** -0.1332
        g = 288.1222 * (t - 60) ** -0.0755
        b = 255.0
    return tuple(min(max(c, 0.0), 255.0) / 255.0 for c in (r, g, b))


def _from_dict(d: dict) -> CelestialObject:
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise ValueError(f"Obiekt {d.get('id', '?')}: brak pól {missing}")
    if d["level"] not in LEVELS:
        raise ValueError(f"Obiekt {d['id']}: nieznany poziom {d['level']!r}")
    if d["kind"] not in KINDS:
        raise ValueError(f"Obiekt {d['id']}: nieznany rodzaj {d['kind']!r}")

    if "temp_k" in d:
        color = temp_to_rgb(d["temp_k"])
    else:
        color = tuple(d.get("color", (1.0, 1.0, 1.0)))

    obj = CelestialObject(
        id=d["id"], level=d["level"], kind=d["kind"], name=d["name"], type=d["type"],
        params=[tuple(p) for p in d["params"]], description=d["description"],
        pos=np.zeros(3, np.float32), color=color, size=d.get("size", 1.0),
        zoom=d.get("zoom", 4.0), enter=d.get("enter"), ring=d.get("ring", False),
        label=d.get("label"), focus=d.get("focus"),
    )
    if d["level"] == "galaxy":
        if "pos_kpc" in d:
            obj.pos = np.asarray(d["pos_kpc"], np.float32)
        else:
            obj.pos = galactic_to_scene(d["l"], d["b"], d["dist_kpc"])
    elif d["level"] in ("blackhole", "crab"):
        obj.pos = np.asarray(d.get("pos", (0, 0, 0)), np.float32)
    else:
        obj.orbit_r = solar_orbit_radius(d.get("a_au", 0.0))
        obj.orbit_w = 2 * math.pi / (EARTH_ORBIT_S * d.get("period_y", 1.0) ** 0.5)
        obj.phase = d.get("phase", 0.0)
    return obj


def load_catalog(path: Path = DATA_FILE) -> list[CelestialObject]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    objects = [_from_dict(d) for d in data["objects"]]
    ids = [o.id for o in objects]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Powtórzone id w katalogu: {sorted(dupes)}")
    by_id = {o.id: o for o in objects}
    for o in objects:
        if o.enter is not None and o.enter not in LEVELS:
            raise ValueError(f"Obiekt {o.id}: pole enter wskazuje nieznany poziom {o.enter!r}")
        if o.focus is not None and (o.focus not in by_id or by_id[o.focus].level != o.enter):
            raise ValueError(f"Obiekt {o.id}: focus {o.focus!r} musi być obiektem sceny {o.enter!r}")
    return objects
