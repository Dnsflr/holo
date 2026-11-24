"""Renderowanie jednego widoku (jednej ścianki piramidy) do powierzchni pygame."""
from __future__ import annotations

import numpy as np
import pygame

from .camera import project
from .scene import Frame


def splat(buf: np.ndarray, sx: np.ndarray, sy: np.ndarray, cols: np.ndarray) -> None:
    """Dodaje kolory punktów do bufora (rs, rs, 3) indeksowanego [x, y]."""
    rs = buf.shape[0]
    m = (sx >= 0) & (sy >= 0) & (sx < rs) & (sy < rs)
    if not m.any():
        return
    flat = sx[m].astype(np.intp) * rs + sy[m].astype(np.intp)
    # Indeksy pojedynczych kanałów R,G,B w spłaszczonym buforze; add.at poprawnie
    # sumuje kilka gwiazd trafiających w ten sam piksel (wersja 1D jest ~5x szybsza).
    idx = (flat[:, None] * 3 + _RGB).ravel()
    np.add.at(buf.reshape(-1), idx, cols[m].astype(np.float32, copy=False).ravel())


_RGB = np.arange(3, dtype=np.intp)


def make_core_sprite(d: int) -> pygame.Surface:
    """Okrągła, ciepła poświata jądra galaktyki."""
    x, y = np.mgrid[0:d, 0:d]
    c = (d - 1) / 2
    rr = np.hypot(x - c, y - c) / (d / 2)
    inten = np.exp(-(rr / 0.18) ** 2) * 0.9 + np.exp(-(rr / 0.5) ** 2) * 0.22
    inten[rr > 1] = 0
    col = np.array([1.0, 0.85, 0.6])
    arr = (np.clip(inten[..., None] * col, 0, 1) * 255).astype(np.uint8)
    surf = pygame.Surface((d, d), 0, 32)
    pygame.surfarray.blit_array(surf, arr)
    return surf


class ViewRenderer:
    def __init__(self, view_size: int, azimuth: float, cfg, rng: np.random.Generator):
        self.cfg = cfg
        self.view_size = view_size
        self.azimuth = azimuth
        self.rs = rs = max(64, int(view_size * cfg.render_scale))
        self.scale = rs * 0.34  # galaktyka o promieniu 1 zajmuje ~68% widoku

        self.buf = np.zeros((rs, rs, 3), np.float32)      # gwiazdy ze smugami
        self.overlay = np.zeros((rs, rs, 3), np.float32)  # reszta, bez smug
        self.surface = pygame.Surface((rs, rs), 0, 32)

        # Migoczące gwiazdy tła (płaskie, osobne dla każdego widoku).
        nb = rs * rs // 450
        self.bg_x = rng.uniform(0, rs, nb)
        self.bg_y = rng.uniform(0, rs, nb)
        self.bg_col = rng.uniform(0.1, 0.45, (nb, 1)) * np.array([[0.8, 0.85, 1.0]])
        self.bg_phase = rng.uniform(0, 2 * np.pi, nb)
        self.bg_rate = rng.uniform(0.5, 2.5, nb)

        self.core = make_core_sprite(int(rs * 0.4))

    def render(self, frame: Frame, t: float, tilt: float, precession: float) -> pygame.Surface:
        cfg = self.cfg
        rs = self.rs
        az = self.azimuth + precession

        # Gwiazdy galaktyki z wygładzaniem w czasie.
        decay = 0.6
        sx, sy, f = project(frame.star_pts, az, tilt, rs, self.scale)
        self.buf *= decay
        splat(self.buf, sx, sy, frame.star_cols * (f[:, None] * (1 - decay)))

        # Warstwa bez smug: tło, orbity, komety.
        ov = self.overlay
        ov.fill(0)
        twinkle = 0.55 + 0.45 * np.sin(self.bg_phase + self.bg_rate * t)
        splat(ov, self.bg_x, self.bg_y, self.bg_col * twinkle[:, None])
        if len(frame.overlay_pts):
            ox, oy, _ = project(frame.overlay_pts, az, tilt, rs, self.scale)
            splat(ov, ox, oy, frame.overlay_cols)

        img = self.buf + ov
        np.clip(img, 0, 1, out=img)
        img *= 255
        pygame.surfarray.blit_array(self.surface, img.astype(np.uint8))

        # Ciała na orbitach.
        for pos, color, size in frame.bodies:
            bx, by, bf = project(pos[None, :], az, tilt, rs, self.scale)
            r = max(1, int(size * self.scale * bf[0]))
            center = (int(bx[0]), int(by[0]))
            pygame.draw.circle(self.surface, color, center, r)
            light = tuple(min(255, c + 90) for c in color)
            pygame.draw.circle(self.surface, light, center, max(1, r // 2))

        # Pulsujące jądro.
        core = self.core.copy()
        k = int(255 * frame.core_pulse)
        core.fill((k, k, k), special_flags=pygame.BLEND_MULT)
        d = core.get_width()
        self.surface.blit(core, (rs // 2 - d // 2, rs // 2 - d // 2), special_flags=pygame.BLEND_ADD)

        # Poświata: rozmyta kopia obrazu dodana na wierzch.
        if cfg.glow:
            small = pygame.transform.smoothscale(self.surface, (max(1, rs // 6), max(1, rs // 6)))
            big = pygame.transform.smoothscale(small, (rs, rs))
            big.fill((150, 150, 150), special_flags=pygame.BLEND_MULT)
            self.surface.blit(big, (0, 0), special_flags=pygame.BLEND_ADD)

        if rs != self.view_size:
            return pygame.transform.smoothscale(self.surface, (self.view_size, self.view_size))
        return self.surface
