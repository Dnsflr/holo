"""Warstwa gwiazd: szybkie rysowanie tysięcy punktów przez numpy + poświata."""
from __future__ import annotations

import numpy as np
import pygame

_RGB = np.arange(3, dtype=np.intp)


def splat_nearest(buf: np.ndarray, sx: np.ndarray, sy: np.ndarray, cols: np.ndarray) -> None:
    """Szybsza wersja bez interpolacji – każdy punkt trafia w jeden piksel."""
    w, h = buf.shape[0], buf.shape[1]
    m = (sx >= 0) & (sy >= 0) & (sx < w) & (sy < h)
    if not m.any():
        return
    flat = sx[m].astype(np.intp) * h + sy[m].astype(np.intp)
    idx = (flat[:, None] * 3 + _RGB).ravel()
    np.add.at(buf.reshape(-1), idx, cols[m].astype(np.float32, copy=False).ravel())


def splat(buf: np.ndarray, sx: np.ndarray, sy: np.ndarray, cols: np.ndarray) -> None:
    """Dodaje punkty do bufora (w, h, 3) z interpolacją dwuliniową.

    Każdy punkt rozkłada się na 4 sąsiednie piksele proporcjonalnie do położenia,
    dzięki temu powoli przesuwające się gwiazdy nie "skaczą" o całe piksele.
    """
    w, h = buf.shape[0], buf.shape[1]
    fx = sx - 0.5
    fy = sy - 0.5
    x0 = np.floor(fx)
    y0 = np.floor(fy)
    ax = (fx - x0).astype(np.float32)[:, None]
    ay = (fy - y0).astype(np.float32)[:, None]
    x0 = x0.astype(np.intp)
    y0 = y0.astype(np.intp)
    cols = cols.astype(np.float32, copy=False)

    idx_parts, val_parts = [], []
    for dx, dy, wgt in ((0, 0, (1 - ax) * (1 - ay)), (1, 0, ax * (1 - ay)),
                        (0, 1, (1 - ax) * ay), (1, 1, ax * ay)):
        xi = x0 + dx
        yi = y0 + dy
        m = (xi >= 0) & (yi >= 0) & (xi < w) & (yi < h)
        flat = xi[m] * h + yi[m]
        idx_parts.append((flat[:, None] * 3 + _RGB).ravel())
        val_parts.append((cols[m] * wgt[m]).ravel())
    # add.at poprawnie sumuje wiele gwiazd trafiających w ten sam piksel.
    np.add.at(buf.reshape(-1), np.concatenate(idx_parts), np.concatenate(val_parts))


class Batch:
    """Zbiera punkty (w układzie kamery) dla jednej warstwy i rysuje je jednym wywołaniem.

    Wiele małych wywołań numpy kosztuje więcej niż jedno duże – dlatego sceny
    najpierw zbierają punkty, a rzutują i rysują je hurtem.
    """

    def __init__(self):
        self.pts: list[np.ndarray] = []
        self.cols: list[np.ndarray] = []

    def add(self, pts: np.ndarray, cols: np.ndarray) -> None:
        if len(pts):
            self.pts.append(pts)
            self.cols.append(cols)

    def flush(self, cam, size, layer: "StarLayer") -> None:
        if not self.pts:
            return
        pts = np.concatenate(self.pts)
        cols = np.concatenate(self.cols)
        self.pts, self.cols = [], []
        sx, sy, _, vis = cam.perspective(pts, size)
        layer.add(sx[vis], sy[vis], cols[vis])


GLOW_DIV = 3        # poświata i gaz liczone w buforze 3× mniejszym
GLOW_STRENGTH = 150  # siła poświaty (0–255)


class StarLayer:
    """Bufor punktów (gwiazd, cząstek) zamieniany co klatkę na obraz z poświatą.

    Ścieżka na klatkę: punkty → bufor (numpy) → obraz; obraz pomniejszony 3× + "gaz"
    (rozmyte światło rysowane od razu w małym buforze) → jedno powiększenie → dodane do obrazu.
    """

    def __init__(self, size: tuple[int, int], render_scale: float, bilinear: bool = False,
                 dims: tuple[int, int] | None = None, with_gas: bool = True):
        # Domyślnie bez interpolacji – ~6× szybciej; przy warstwie w rozdzielczości
        # klatki "skakanie" gwiazd o piksel jest niewidoczne (GPU i tak łagodnie powiększa obraz).
        self.size = size
        self.splat = splat if bilinear else splat_nearest
        if dims is None:
            dims = (max(32, int(size[0] * render_scale)), max(32, int(size[1] * render_scale)))
        self.w, self.h = dims
        self.k = self.w / size[0]
        self.buf = np.zeros((self.w, self.h, 3), np.float32)
        self.u8 = np.zeros((self.w, self.h, 3), np.uint8)   # bufor do konwersji – bez alokacji co klatkę
        self.surface = pygame.Surface((self.w, self.h), 0, 32)
        self.used = False
        self.small_size = (max(8, self.w // GLOW_DIV), max(8, self.h // GLOW_DIV))
        # Miękki "gaz" – rysowany od razu w rozdzielczości poświaty.
        self._gas = StarLayer(size, 0, dims=self.small_size, with_gas=False) if with_gas else None
        self.gas: StarLayer | None = self._gas

    def set_gas(self, enabled: bool) -> None:
        """Bez gazu poziomy rysują wszystko w warstwie ostrej (szybciej, mniej miękko)."""
        self.gas = self._gas if enabled else None

    def begin(self) -> None:
        self.buf.fill(0)
        self.used = False
        if self.gas is not None:
            self.gas.begin()

    def add(self, sx: np.ndarray, sy: np.ndarray, cols: np.ndarray) -> None:
        """Dodaje punkty; sx, sy w pikselach klatki, kolory 0..1."""
        if len(sx):
            # Mnożenie przez 255 na punktach (tanio) zamiast na całym buforze.
            self.splat(self.buf, sx * self.k, sy * self.k, np.asarray(cols, np.float32) * 255.0)
            self.used = True

    def clear_circle(self, cx: float, cy: float, r: float) -> None:
        """Zeruje koło (np. cień czarnej dziury zasłania to, co za nim); współrzędne klatki."""
        k = self.k
        kx, ky, kr = cx * k, cy * k, r * k
        x0, x1 = max(0, int(kx - kr)), min(self.w, int(kx + kr) + 2)
        y0, y1 = max(0, int(ky - kr)), min(self.h, int(ky + kr) + 2)
        if x0 < x1 and y0 < y1:
            xs = np.arange(x0, x1)[:, None] + 0.5
            ys = np.arange(y0, y1)[None, :] + 0.5
            inside = (xs - kx) ** 2 + (ys - ky) ** 2 <= kr * kr
            self.buf[x0:x1, y0:y1][inside] = 0.0
        if self.gas is not None:
            self.gas.clear_circle(cx, cy, r)

    def finish(self, glow: bool) -> pygame.Surface:
        """Zamienia bufor na obraz klatki (z poświatą i gazem)."""
        surf = self._to_surface()
        gas_used = self.gas is not None and self.gas.used
        if glow or gas_used:
            if glow:
                small = pygame.transform.smoothscale(surf, self.small_size)
                small.fill((GLOW_STRENGTH,) * 3, special_flags=pygame.BLEND_MULT)
            else:
                small = pygame.Surface(self.small_size, 0, 32)
            if gas_used:
                small.blit(self.gas._to_surface(), (0, 0), special_flags=pygame.BLEND_ADD)
            surf.blit(pygame.transform.smoothscale(small, (self.w, self.h)), (0, 0),
                      special_flags=pygame.BLEND_ADD)
        if (self.w, self.h) == tuple(self.size):
            return surf
        return pygame.transform.smoothscale(surf, self.size)

    def _to_surface(self) -> pygame.Surface:
        b = self.buf
        np.minimum(b, 255.0, out=b)
        np.copyto(self.u8, b, casting="unsafe")
        pygame.surfarray.blit_array(self.surface, self.u8)
        return self.surface


def add_glow(surface: pygame.Surface, strength: int = 150, factor: int = 6) -> None:
    """Poświata: rozmyta (pomniejszona i powiększona) kopia obrazu dodana na wierzch."""
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, w // factor), max(1, h // factor)))
    big = pygame.transform.smoothscale(small, (w, h))
    big.fill((strength, strength, strength), special_flags=pygame.BLEND_MULT)
    surface.blit(big, (0, 0), special_flags=pygame.BLEND_ADD)
