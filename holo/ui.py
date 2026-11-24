"""Elementy interfejsu rysowane na klatce logicznej: kursor, napisy, kalibracja."""
from __future__ import annotations

import math

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


def wrap(msg: str, size: int, width: int) -> list[str]:
    """Dzieli tekst na linie mieszczące się w danej szerokości."""
    f = font(size)
    lines, line = [], ""
    for word in msg.split():
        trial = f"{line} {word}".strip()
        if f.size(trial)[0] <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_highlight(surface: pygame.Surface, x: float, y: float, r: float, t: float,
                   alpha: float, selected: bool) -> None:
    """Pierścień wokół obiektu: cienki przy najechaniu, pulsujący przy zaznaczeniu."""
    if alpha <= 0.02 or r > surface.get_height() * 0.12:
        return  # duży obiekt (np. przybliżona czarna dziura) – pierścień tylko by zasłaniał
    rr = r * (1.35 + (0.08 * math.sin(t * 4) if selected else 0))
    p = (int(x), int(y))
    pygame.draw.circle(surface, scaled(ACCENT, alpha * (1.0 if selected else 0.7)), p, int(rr), 2)
    if selected:
        # Cztery "celowniki" na zewnątrz okręgu.
        for k in range(4):
            a = t * 0.8 + k * math.pi / 2
            x1, y1 = x + math.cos(a) * rr * 1.15, y + math.sin(a) * rr * 1.15
            x2, y2 = x + math.cos(a) * rr * 1.4, y + math.sin(a) * rr * 1.4
            pygame.draw.line(surface, scaled(ACCENT, alpha), (x1, y1), (x2, y2), 2)


def draw_label(surface: pygame.Surface, msg: str, x: float, y: float, r: float, alpha: float,
               sub: str | None = None) -> None:
    """Podpis pod obiektem (przy najechaniu kursorem)."""
    h = surface.get_height()
    size = max(18, h // 30)
    rect = text(surface, msg, size, scaled(TEXT, alpha), center=(int(x), int(y + r * 1.5 + size * 0.7)))
    if sub:
        text(surface, sub, max(14, h // 44), scaled(ACCENT, alpha * 0.9), center=(rect.centerx, rect.bottom + size // 2))


def draw_breadcrumb(surface: pygame.Surface, titles: list[str], alpha: float = 1.0) -> None:
    """Ścieżka nawigacji u góry: Droga Mleczna › Okolica Słońca › Układ Słoneczny."""
    w, h = surface.get_size()
    size = max(18, h // 30)
    parts = []
    for i, title in enumerate(titles):
        last = i == len(titles) - 1
        parts.append(font(size).render(title, True, scaled(TEXT if last else DIM, alpha)))
        if not last:
            parts.append(font(size).render("  ›  ", True, scaled(DIM, alpha)))
    total = sum(p.get_width() for p in parts)
    x = (w - total) // 2
    for p in parts:
        surface.blit(p, (x, h // 28))
        x += p.get_width()


def draw_hints(surface: pygame.Surface, can_go_back: bool, alpha: float) -> None:
    if alpha <= 0.02:
        return
    w, h = surface.get_size()
    msg = "Kliknij obiekt, aby poznać szczegóły"
    if can_go_back:
        msg += "   •   prawy przycisk: wstecz"
    text(surface, msg, max(14, h // 46), scaled(DIM, alpha * 0.8), topleft=(w // 40, h - h // 16))


class InfoCard:
    """Karta z parametrami wybranego obiektu – pojawia się płynnie obok niego."""

    FADE_SPEED = 3.0

    def __init__(self, size: tuple[int, int]):
        self.size = size
        self.obj = None
        self.alpha = 0.0
        self.goal = 0.0
        self.image: pygame.Surface | None = None

    def show(self, obj) -> None:
        if obj is not self.obj:
            self.obj = obj
            self.alpha = 0.0
            self.image = self._render(obj)
        self.goal = 1.0

    def hide(self) -> None:
        self.goal = 0.0

    def update(self, dt: float) -> None:
        step = self.FADE_SPEED * dt
        if self.alpha < self.goal:
            self.alpha = min(self.goal, self.alpha + step)
        else:
            self.alpha = max(self.goal, self.alpha - step)
        if self.alpha == 0.0 and self.goal == 0.0:
            self.obj = None
            self.image = None

    def _render(self, obj) -> pygame.Surface:
        w, h = self.size
        cw = max(360, int(w * 0.32))
        pad = cw // 14
        inner = cw - 2 * pad
        s_title, s_type = max(26, h // 17), max(16, h // 38)
        s_label, s_value, s_desc = max(14, h // 44), max(18, h // 32), max(15, h // 40)

        rows = []  # (tekst, rozmiar, kolor, odstęp_po)
        for line in wrap(obj.name, s_title, inner):
            rows.append((line, s_title, ACCENT, 0))
        rows.append((obj.type, s_type, DIM, int(s_type * 0.9)))
        rows.append(("__sep__", 0, None, int(s_type * 0.6)))
        for label, value in obj.params:
            rows.append((label.upper(), s_label, DIM, 0))
            for line in wrap(value, s_value, inner):
                rows.append((line, s_value, TEXT, 0))
            rows[-1] = rows[-1][:3] + (int(s_value * 0.45),)
        rows.append(("__sep__", 0, None, int(s_type * 0.6)))
        for line in wrap(obj.description, s_desc, inner):
            rows.append((line, s_desc, (200, 210, 230), 0))
        if obj.enter:
            rows[-1] = rows[-1][:3] + (int(s_desc * 0.8),)
            rows.append(("» Kliknij ponownie, aby wejść", s_desc, (255, 220, 140), 0))

        height = pad * 2 + sum(int(sz * 1.12) + gap if t != "__sep__" else gap for t, sz, _, gap in rows)
        img = pygame.Surface((cw, height), 0, 32)
        img.fill((0, 0, 0))
        y = pad
        for t, sz, col, gap in rows:
            if t == "__sep__":
                pygame.draw.line(img, scaled(ACCENT, 0.4), (pad, y + gap // 2), (cw - pad, y + gap // 2), 1)
                y += gap
                continue
            surf = font(sz).render(t, True, col)
            img.blit(surf, (pad, y))
            y += int(sz * 1.12) + gap
        # Ramka z mocniejszymi narożnikami.
        pygame.draw.rect(img, scaled(ACCENT, 0.35), img.get_rect(), 1)
        c = pad
        for (x0, y0, dx, dy) in ((0, 0, 1, 1), (cw - 1, 0, -1, 1), (0, height - 1, 1, -1), (cw - 1, height - 1, -1, -1)):
            pygame.draw.line(img, ACCENT, (x0, y0), (x0 + dx * c, y0), 2)
            pygame.draw.line(img, ACCENT, (x0, y0), (x0, y0 + dy * c), 2)
        return img

    def draw(self, surface: pygame.Surface, anchor: tuple[float, float, float] | None) -> None:
        if self.image is None or self.alpha <= 0.01:
            return
        w, h = surface.get_size()
        img = self.image
        margin = w // 30
        ax = anchor[0] if anchor else w / 2
        # Karta po przeciwnej stronie niż obiekt; lekko wsuwa się podczas pojawiania.
        slide = int((1 - self.alpha) * w * 0.03)
        if ax <= w * 0.55:
            x = w - img.get_width() - margin + slide
        else:
            x = margin - slide
        y = max(h // 9, (h - img.get_height()) // 2)
        rect = img.get_rect(topleft=(x, y))

        # Przyciemnienie tła pod kartą (żeby gwiazdy nie mieszały się z tekstem).
        k = int(255 * (1 - 0.92 * self.alpha))
        surface.fill((k, k, k), rect, special_flags=pygame.BLEND_MULT)
        shown = img.copy()
        a = int(255 * self.alpha)
        shown.fill((a, a, a), special_flags=pygame.BLEND_MULT)
        surface.blit(shown, rect, special_flags=pygame.BLEND_ADD)

        if anchor:
            # Linia łącząca obiekt z kartą.
            ox, oy, r = anchor
            ex = rect.left if x > ox else rect.right
            ey = rect.top + img.get_height() // 6
            sx = ox + (r * 1.6 if ex > ox else -r * 1.6)
            col = scaled(ACCENT, 0.6 * self.alpha)
            mid = (ex - (40 if ex > ox else -40), ey)
            pygame.draw.line(surface, col, (sx, oy), mid, 1)
            pygame.draw.line(surface, col, mid, (ex, ey), 1)
