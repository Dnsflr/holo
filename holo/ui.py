"""Elementy interfejsu rysowane na klatce logicznej: kursor, napisy, kalibracja."""
from __future__ import annotations

import pygame

ACCENT = (120, 220, 255)
TEXT = (235, 240, 255)
DIM = (130, 150, 180)

_fonts: dict[int, pygame.font.Font] = {}


def font(size: int) -> pygame.font.Font:
    """Wbudowana czcionka pygame (ma polskie znaki, działa też na Raspberry Pi)."""
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def text(surface: pygame.Surface, msg: str, size: int, color, center=None, topleft=None) -> pygame.Rect:
    img = font(size).render(msg, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    elif topleft is not None:
        rect.topleft = topleft
    surface.blit(img, rect)
    return rect


def scaled(color, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * k))) for c in color)


class Cursor:
    """Własny, świecący kursor – systemowego nie widać w odbiciu."""

    HIDE_AFTER = 4.0  # sekundy bez ruchu, po których kursor gaśnie

    def __init__(self, size: tuple[int, int]):
        self.size = size
        self.x = size[0] / 2
        self.y = size[1] / 2
        self.idle = self.HIDE_AFTER + 1

    @property
    def pos(self) -> tuple[int, int]:
        return int(self.x), int(self.y)

    @property
    def alpha(self) -> float:
        """1 = w pełni widoczny, 0 = ukryty (płynne wygaszanie przez ostatnią sekundę)."""
        return max(0.0, min(1.0, self.HIDE_AFTER - self.idle))

    def move_to(self, pos) -> None:
        self.x, self.y = pos
        self._clamp()

    def move_by(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
        self._clamp()

    def _clamp(self) -> None:
        self.x = min(max(self.x, 0), self.size[0] - 1)
        self.y = min(max(self.y, 0), self.size[1] - 1)
        self.idle = 0.0

    def update(self, dt: float) -> None:
        self.idle += dt

    def draw(self, surface: pygame.Surface) -> None:
        a = self.alpha
        if a <= 0:
            return
        r = max(10, self.size[1] // 60)
        p = self.pos
        pygame.draw.circle(surface, scaled(ACCENT, 0.35 * a), p, r + 4, 2)
        pygame.draw.circle(surface, scaled(ACCENT, a), p, r, 2)
        pygame.draw.circle(surface, scaled((255, 255, 255), a), p, 3)


def draw_calibration(surface: pygame.Surface, flip_h: bool, flip_v: bool) -> None:
    """Ekran do ustawienia odbicia: napisy muszą być czytelne w plexi."""
    w, h = surface.get_size()
    big = max(40, h // 10)
    mid = max(24, h // 22)
    small = max(18, h // 34)
    col = ACCENT

    text(surface, "GÓRA", big, col, center=(w // 2, h // 8))
    text(surface, "DÓŁ", big, col, center=(w // 2, h - h // 8))
    text(surface, "LEWO", big, col, center=(w // 7, h // 2))
    text(surface, "PRAWO", big, col, center=(w - w // 7, h // 2))
    a = h // 14
    cx = w // 2
    pygame.draw.polygon(surface, col, [(cx, h // 4 - a), (cx - a // 2, h // 4), (cx + a // 2, h // 4)])

    lines = [
        ("Kalibracja odbicia", mid, TEXT),
        ("Napisy muszą być czytelne w odbiciu na plexi.", small, DIM),
        ("H – odbij lewo/prawo      V – odbij góra/dół", small, DIM),
        ("C – zakończ kalibrację", small, DIM),
    ]
    y = h // 2 - mid * 2
    for msg, size, c in lines:
        text(surface, msg, size, c, center=(cx, y))
        y += int(size * 1.4)

    flags = " ".join(f for f, on in (("--flip-h", flip_h), ("--flip-v", flip_v)) if on) or "(bez opcji)"
    text(surface, f"Uruchamiaj z:  {flags}", small, (255, 220, 140), center=(cx, y + small))
