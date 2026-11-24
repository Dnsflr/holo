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


class StarLayer:
    """Bufor w obniżonej rozdzielczości, do którego poziomy dodają chmury punktów."""

    def __init__(self, size: tuple[int, int], render_scale: float, bilinear: bool = True):
        self.size = size
        self.splat = splat if bilinear else splat_nearest
        self.k = render_scale
        self.w = max(32, int(size[0] * render_scale))
        self.h = max(32, int(size[1] * render_scale))
        self.buf = np.zeros((self.w, self.h, 3), np.float32)
        self.surface = pygame.Surface((self.w, self.h), 0, 32)
        self.used = False
        # Opcjonalna druga warstwa w niższej rozdzielczości – miękki, rozmyty "gaz".
        self.gas: StarLayer | None = None

    def begin(self) -> None:
        self.buf.fill(0)
        self.used = False
        if self.gas is not None:
            self.gas.begin()

    def add(self, sx: np.ndarray, sy: np.ndarray, cols: np.ndarray) -> None:
        """Dodaje punkty; sx, sy w pikselach pełnego ekranu."""
        if len(sx):
            self.splat(self.buf, sx * self.k, sy * self.k, cols)
            self.used = True

    def clear_circle(self, cx: float, cy: float, r: float) -> None:
        """Zeruje koło (np. cień czarnej dziury zasłania to, co za nim); współrzędne pełnego ekranu."""
        k = self.k
        cx, cy, r = cx * k, cy * k, r * k
        x0, x1 = max(0, int(cx - r)), min(self.w, int(cx + r) + 2)
        y0, y1 = max(0, int(cy - r)), min(self.h, int(cy + r) + 2)
        if x0 >= x1 or y0 >= y1:
            return
        xs = np.arange(x0, x1)[:, None] + 0.5
        ys = np.arange(y0, y1)[None, :] + 0.5
        inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
        self.buf[x0:x1, y0:y1][inside] = 0.0
        if self.gas is not None:
            self.gas.clear_circle(cx / k, cy / k, r / k)

    def finish(self, glow: bool) -> pygame.Surface:
        img = self._finish_own(glow)
        if self.gas is not None and self.gas.used:
            img.blit(self.gas._finish_own(True, strength=90), (0, 0), special_flags=pygame.BLEND_ADD)
        return img

    def _finish_own(self, glow: bool, strength: int = 150) -> pygame.Surface:
        b = self.buf
        np.multiply(b, 255.0, out=b)
        np.minimum(b, 255.0, out=b)
        pygame.surfarray.blit_array(self.surface, b.astype(np.uint8))
        if glow:
            add_glow(self.surface, strength=strength)
        return pygame.transform.smoothscale(self.surface, self.size)


def add_glow(surface: pygame.Surface, strength: int = 150, factor: int = 6) -> None:
    """Poświata: rozmyta (pomniejszona i powiększona) kopia obrazu dodana na wierzch."""
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, w // factor), max(1, h // factor)))
    big = pygame.transform.smoothscale(small, (w, h))
    big.fill((strength, strength, strength), special_flags=pygame.BLEND_MULT)
    surface.blit(big, (0, 0), special_flags=pygame.BLEND_ADD)
