"""Poziomy nawigacji: mapa Drogi Mlecznej i Układ Słoneczny (sceny 3D są w holo/scenes).

Każdy poziom ma własną skalę (view_radius), domyślne ustawienie kamery
i rysuje się w dwóch krokach: punkty do warstwy gwiazd (draw_points)
oraz sprite'y obiektów na pełnej klatce (draw_sprites). Przy rysowaniu
poziom zapamiętuje, gdzie na ekranie wylądował każdy obiekt (hits) –
z tego korzysta wybieranie myszą.
"""
from __future__ import annotations

import math
import zlib

import numpy as np
import pygame

from .blackhole import BlackHole
from .camera import Camera
from .catalog import CelestialObject, solar_orbit_radius
from .galaxy import MilkyWay
from .planets import LOOKS, SaturnRings, make_texture, planet_axes, shade_planet, to_surface
from .render import StarLayer
from .sprites import blit_scaled, cluster_sprite, nebula_sprite, radial_glow, star_sprite, sun_sprite
from .ui import DIM, font, scaled, text

MIN_HIT_PX = 16  # najmniejszy promień "trafienia" kliknięciem


def make_sprite(o: CelestialObject) -> pygame.Surface | None:
    seed = zlib.crc32(o.id.encode())
    if o.kind in ("star", "system"):
        return star_sprite(128, o.color)
    if o.kind == "nebula":
        return nebula_sprite(160, o.color, seed)
    if o.kind == "cluster":
        return cluster_sprite(128, o.color, seed, globular="kulista" in o.type.lower())
    return None  # planety rysuje SolarLevel w 3D, czarną dziurę i pulsar – ich sceny  # czarną dziurę rysuje poziom


class Level:
    key = ""
    title = ""
    note = ""            # np. informacja o nieproporcjonalnej skali
    view_radius = 1.0
    home_tilt = 50.0
    home_zoom = 1.0
    tilt_range = (-80.0, 85.0)  # zakres pochylania myszą [stopnie]
    sprite_scale = 0.04  # rozmiar sprite'a jako ułamek krótszego boku ekranu

    def __init__(self, catalog: list[CelestialObject]):
        self.objects = [o for o in catalog if o.level == self.key]
        self.sprites = {o.id: make_sprite(o) for o in self.objects}
        self.hits: list[tuple[CelestialObject, float, float, float]] = []
        self.selected: CelestialObject | None = None  # ustawiane przez App
        self.show_text = False                         # napisy pomocnicze (ustawia App)

    # --- kamera ---
    def make_camera(self) -> Camera:
        cam = Camera(self.view_radius, self.home_tilt, yaw=self.home_yaw(), tilt_range=self.tilt_range)
        cam.zoom = cam.goal_zoom = self.home_zoom
        return cam

    def home_yaw(self) -> float:
        return 0.0

    def find(self, obj_id: str) -> CelestialObject | None:
        return next((o for o in self.objects if o.id == obj_id), None)

    # --- rysowanie ---
    def draw_points(self, layer: StarLayer, cam: Camera, size, t: float, alpha: float) -> None:
        pass

    def draw_sprites(self, frame: pygame.Surface, cam: Camera, t: float, alpha: float) -> None:
        self.draw_objects(frame, cam, t, alpha)

    def sprite_diameter(self, o: CelestialObject, cam: Camera, size, f: float) -> float:
        return min(size) * self.sprite_scale * o.size * f * cam.zoom ** 0.5

    def draw_objects(self, frame, cam, t, alpha) -> None:
        size = frame.get_size()
        self.hits = []
        for o in self.objects:
            x, y, f, vis = cam.project_one(o.position_at(t), size)
            if not vis:
                continue
            sprite = self.sprites.get(o.id)
            d = self.sprite_diameter(o, cam, size, f)
            if sprite is not None:
                blit_scaled(frame, sprite, (x, y), d, alpha)
            self.hits.append((o, x, y, max(d * 0.28, MIN_HIT_PX)))

    def draw_note(self, frame: pygame.Surface, alpha: float) -> None:
        if self.show_text and self.note and alpha > 0.05:
            w, h = frame.get_size()
            text(frame, self.note, max(16, h // 40), scaled(DIM, alpha * 0.8), center=(w // 2, h - h // 22))


class GalaxyLevel(Level):
    key = "galaxy"
    title = "Droga Mleczna"
    view_radius = 16.0  # kpc
    home_tilt = 52.0
    tilt_range = (10.0, 90.0)  # galaktykę oglądamy od góry lub ukośnie, nie od spodu
    sprite_scale = 0.035

    def __init__(self, catalog, cfg, rng: np.random.Generator):
        super().__init__(catalog)
        self.galaxy = MilkyWay(cfg.stars, rng)
        self.core = radial_glow(256, (1.0, 0.82, 0.55), core=0.12, halo=0.45, core_w=0.85, halo_w=0.3)
        self.black_hole = BlackHole()

    def home_yaw(self) -> float:
        # Słońce (x = -8,2 kpc) od strony widza, tak jak na typowych mapach galaktyki.
        return math.pi / 2

    def draw_points(self, layer, cam, size, t, alpha):
        g = self.galaxy
        sx, sy, f, vis = cam.project(g.points, size)
        cols = g.colors_at(t)[vis] * (alpha * np.minimum(f[vis], 2.0))[:, None]
        layer.add(sx[vis], sy[vis], cols)

    def sprite_diameter(self, o, cam, size, f):
        k = 1.8 if o.kind in ("nebula", "cluster") else 1.0
        return min(min(size) * self.sprite_scale * k * o.size * f * cam.zoom ** 0.5, 0.35 * min(size))

    def draw_sprites(self, frame, cam, t, alpha):
        size = frame.get_size()
        cx, cy, f, vis = cam.project_one((0.0, 0.0, 0.0), size)
        bh_d = 0.0
        if vis:
            # Poświata jądra gaśnie przy dużym przybliżeniu, żeby nie zalać czarnej dziury.
            core_k = min(1.0, max(0.0, 1.4 - cam.zoom / 8))
            d = 2 * 2.2 * cam.scale_px(size) * f
            blit_scaled(frame, self.core, (cx, cy), d, alpha * core_k * (0.85 + 0.08 * math.sin(t * 1.3)))
            # Sgr A*: na widoku całej galaktyki mały punkt, po przybliżeniu pełny obraz.
            bh_d = min(9.0 * cam.zoom * f, 0.75 * min(size))
            self.black_hole.draw(frame, (cx, cy), bh_d, t, alpha * min(1.0, 0.35 + cam.zoom / 12))
        self.draw_objects(frame, cam, t, alpha)
        # Czarna dziura nie ma sprite'a w draw_objects – poprawiamy jej obszar trafienia.
        self.hits = [(o, x, y, max(bh_d * 0.3, MIN_HIT_PX) if o.kind == "black_hole" else r)
                     for (o, x, y, r) in self.hits]
        if self.show_text:
            self.draw_markers(frame, alpha, t)

    def draw_markers(self, frame, alpha, t):
        """Podpisy obiektów na mapie (tylko w trybie z napisami)."""
        h = frame.get_height()
        for o, x, y, r in self.hits:
            if not o.label or o is self.selected or r > h * 0.12:
                continue
            col = (255, 220, 140) if o.kind == "system" else (150, 215, 255)
            ring = int(max(r * 1.5, h * 0.024))
            size = max(16, h // 40)
            crowded = any(other is not o and other.label and math.hypot(ox - x, oy - y) < ring * 3.5
                          for other, ox, oy, _ in self.hits)
            if crowded and o.kind != "system":
                # Obok innego znacznika (Krab jest blisko Słońca) – podpis z boku.
                img = font(size).render(o.label, True, scaled(col, 0.85 * alpha))
                frame.blit(img, (int(x + ring + h * 0.012), int(y - img.get_height() / 2)))
            elif crowded:
                text(frame, o.label, size, scaled(col, 0.85 * alpha), center=(int(x), int(y - ring - h * 0.02)))
            else:
                text(frame, o.label, size, scaled(col, 0.85 * alpha), center=(int(x), int(y + ring + h * 0.02)))


class SolarLevel(Level):
    key = "solar"
    title = "Układ Słoneczny"
    note = "Odległości w skali logarytmicznej, rozmiary planet powiększone"
    view_radius = 1.1
    home_tilt = 28.0
    sprite_scale = 0.045

    def __init__(self, catalog, rng: np.random.Generator):
        super().__init__(catalog)
        for o in self.objects:
            if o.kind == "star":
                self.sprites[o.id] = sun_sprite(192, o.color)
        # Planety 3D: tekstura i osie obrotu dla każdej planety.
        self.textures, self.axes = {}, {}
        for k, o in enumerate(self.objects):
            look = LOOKS.get(o.id)
            if o.kind == "planet" and look is not None:
                self.textures[o.id] = make_texture(look.style, seed=100 + k)
                self.axes[o.id] = planet_axes(look.tilt_deg)
        self.rings = SaturnRings(rng)
        a = np.linspace(0, 2 * math.pi, 400, endpoint=False)
        self.orbits = []
        for o in self.objects:
            if o.orbit_r > 0:
                r = o.orbit_r
                self.orbits.append(np.stack([r * np.cos(a), np.zeros_like(a), r * np.sin(a)], -1).astype(np.float32))
        # Pas planetoid między Marsem a Jowiszem (2,2–3,3 j.a.).
        n = 1400
        self.belt_r = np.array([solar_orbit_radius(x) for x in rng.uniform(2.2, 3.3, n)], np.float32)
        self.belt_a = rng.uniform(0, 2 * math.pi, n).astype(np.float32)
        self.belt_y = rng.normal(0, 0.006, n).astype(np.float32)
        self.belt_col = (np.array([0.75, 0.68, 0.6], np.float32) * rng.uniform(0.1, 0.35, (n, 1))).astype(np.float32)
        # Gwiazdy tła.
        m = 900
        v = rng.normal(0, 1, (m, 3))
        self.bg = (v / np.linalg.norm(v, axis=1, keepdims=True) * 1.6).astype(np.float32)
        self.bg_col = (np.array([0.8, 0.85, 1.0], np.float32) * rng.uniform(0.05, 0.3, (m, 1))).astype(np.float32)

    def sprite_diameter(self, o, cam, size, f):
        return min(min(size) * self.sprite_scale * o.size * f * cam.zoom ** 0.6, 0.45 * min(size))

    def planet_radius(self, o, cam) -> float:
        """Promień planety w jednostkach sceny (powiększony, żeby była widoczna)."""
        return self.sprite_scale * o.size * self.view_radius * cam.zoom ** -0.4

    def _planets_on_screen(self, cam, size, t):
        """(obiekt, pozycja 3D, x, y, średnica_px, promień_świata) dla widocznych planet."""
        out = []
        for o in self.objects:
            if o.id not in self.textures:
                continue
            pos = o.position_at(t)
            x, y, f, vis = cam.project_one(pos, size)
            if not vis:
                continue
            rw = self.planet_radius(o, cam)
            d = 2 * rw * f * cam.scale_px(size)
            out.append((o, pos, x, y, d, rw))
        return out

    def draw_points(self, layer, cam, size, t, alpha):
        sx, sy, f, vis = cam.project(self.bg, size)
        layer.add(sx[vis], sy[vis], self.bg_col[vis] * alpha)
        orbit_col = np.array([0.4, 0.6, 0.85], np.float32) * 0.3 * alpha
        for pts in self.orbits:
            sx, sy, f, vis = cam.project(pts, size)
            layer.add(sx[vis], sy[vis], np.broadcast_to(orbit_col, (int(vis.sum()), 3)))
        a = self.belt_a + t * 0.05
        belt = np.stack([self.belt_r * np.cos(a), self.belt_y, -self.belt_r * np.sin(a)], -1)
        sx, sy, f, vis = cam.project(belt, size)
        layer.add(sx[vis], sy[vis], self.belt_col[vis] * alpha)

        planets = self._planets_on_screen(cam, size, t)
        ring_front = None
        for o, pos, x, y, d, rw in planets:
            if o.id == "saturn":
                sun_dir = -pos / max(np.linalg.norm(pos), 1e-6)
                pts = self.rings.points(pos, rw, self.axes[o.id], t)
                rx, ry, rc, front = self.rings.visible(pts, pos, rw, cam, size, sun_dir, self.axes[o.id], layer.k)
                soft = d * 2.27 > 120   # z bliska gładko (warstwa gazu), z daleka wystarczą punkty
                ring_back = (rx[~front], ry[~front], rc[~front] * alpha, soft)
                ring_front = (rx[front], ry[front], rc[front] * alpha, soft)
                self._add_ring(layer, *ring_back)
        # Tarcze planet zasłaniają gwiazdy tła i orbity za nimi...
        if alpha > 0.3:
            for o, pos, x, y, d, rw in planets:
                layer.clear_circle(x, y, d / 2)
        # ...ale przednia część pierścieni Saturna jest przed planetą.
        if ring_front is not None:
            self._add_ring(layer, *ring_front)

    @staticmethod
    def _add_ring(layer, sx, sy, cols, soft):
        """Pierścienie: miękko w warstwie gazu + część cząstek ostro (gładko, ale z fakturą)."""
        gas = layer.gas
        if gas is None or not soft:
            layer.add(sx, sy, cols)
            return
        layer.add(sx[::3], sy[::3], cols[::3] * 1.2)
        # Piksel warstwy gazu jest większy – zbiera więcej cząstek, więc ściszamy proporcjonalnie.
        gas.add(sx, sy, cols * 0.6 * (gas.k / layer.k) ** 2)

    def draw_sprites(self, frame, cam, t, alpha):
        size = frame.get_size()
        self.draw_objects(frame, cam, t, alpha)   # Słońce (sprite)
        for o, pos, x, y, d, rw in self._planets_on_screen(cam, size, t):
            di = int(min(max(d, 4), 0.7 * min(size)))
            sun_dir = -pos / max(np.linalg.norm(pos), 1e-6)
            # Kierunek Słońca i trzy osie planety – jedno przeliczenie do układu kamery.
            vecs = np.vstack([sun_dir, *self.axes[o.id]]).astype(np.float32)
            light, *axes_cam = cam.to_camera(vecs, relative=False)
            light = light / max(np.linalg.norm(light), 1e-6)
            look = LOOKS[o.id]
            img = shade_planet(self.textures[o.id], di, light, axes_cam, look.spin * t, look.atmosphere)
            surf = to_surface(img * alpha)
            frame.blit(surf, (int(x - di / 2), int(y - di / 2)), special_flags=pygame.BLEND_ADD)
            hit_r = di / 2 * (1.4 if o.id == "saturn" else 1.0)
            self.hits.append((o, x, y, max(hit_r, MIN_HIT_PX)))
        self.draw_note(frame, alpha)
