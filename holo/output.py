"""Wyjście na ekran z uwzględnieniem odbicia w plexi.

Program rysuje wszystko w "logicznej" klatce – tak, jak ma ją zobaczyć widz
w odbiciu. Dopiero tutaj klatka jest odwracana pod fizyczny ekran.
"""
from __future__ import annotations

import pygame


class Output:
    def __init__(self, screen: pygame.Surface, flip_h: bool, flip_v: bool):
        self.screen = screen
        self.flip_h = flip_h
        self.flip_v = flip_v

    @property
    def size(self) -> tuple[int, int]:
        return self.screen.get_size()

    def present(self, frame: pygame.Surface) -> None:
        if self.flip_h or self.flip_v:
            frame = pygame.transform.flip(frame, self.flip_h, self.flip_v)
        self.screen.blit(frame, (0, 0))
        pygame.display.flip()

    def to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Przelicza punkt fizycznego ekranu (np. pozycję myszy) na klatkę logiczną."""
        return logical_point(pos, self.size, self.flip_h, self.flip_v)


def logical_point(pos, size, flip_h: bool, flip_v: bool) -> tuple[int, int]:
    x, y = pos
    w, h = size
    if flip_h:
        x = w - 1 - x
    if flip_v:
        y = h - 1 - y
    return x, y
