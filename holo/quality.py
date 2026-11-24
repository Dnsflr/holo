"""Automatyczne dopasowanie jakości do szybkości komputera.

Program mierzy, ile czasu zajmuje policzenie klatki (bez czekania na kolejną).
Gdy przez dłuższą chwilę nie mieści się w budżecie (1/fps), obniża jakość o stopień;
gdy ma duży zapas – podnosi. Progi są różne w obie strony i jest czas uspokojenia,
żeby jakość nie "migotała" między stopniami.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    name: str
    particles: float  # jaka część cząstek jest rysowana (reszta – jaśniej, żeby wygląd się nie zmienił)
    gas: bool         # miękka warstwa gazu (dysk czarnej dziury, mgławica, pierścienie z bliska)
    glow: bool        # poświata


STEPS = [
    Step("wysoka", 1.0, True, True),
    Step("średnia", 0.6, True, True),
    Step("niska", 0.35, True, True),
    Step("minimalna", 0.2, False, False),
]
NAMED = {"high": 0, "medium": 1, "low": 2}

DOWN_RATIO = 1.0    # średni czas klatki > budżet → obniż
UP_RATIO = 0.55     # średni czas < 55% budżetu → podnieś
DOWN_AFTER_S = 1.5  # jak długo musi być za wolno
UP_AFTER_S = 5.0    # jak długo musi być zapas
SMOOTHING = 0.1     # wygładzanie średniej (EMA)


class Quality:
    def __init__(self, mode: str, fps: int):
        self.auto = mode == "auto"
        self.index = NAMED.get(mode, 0)
        self.budget = 1.0 / max(fps, 1)
        self.avg: float | None = None
        self.slow_for = 0.0
        self.fast_for = 0.0
        self.locked = False  # np. w testach wydajności

    @property
    def step(self) -> Step:
        return STEPS[self.index]

    @property
    def name(self) -> str:
        return self.step.name + (" (auto)" if self.auto else "")

    @property
    def stride(self) -> int:
        """Co która cząstka jest rysowana."""
        return max(1, round(1.0 / self.step.particles))

    def frame(self, work_s: float, real_dt: float) -> bool:
        """Zapisuje czas pracy nad klatką. Zwraca True, gdy stopień jakości się zmienił."""
        self.avg = work_s if self.avg is None else self.avg + (work_s - self.avg) * SMOOTHING
        if not self.auto or self.locked:
            return False
        if self.avg > self.budget * DOWN_RATIO:
            self.slow_for += real_dt
            self.fast_for = 0.0
        elif self.avg < self.budget * UP_RATIO:
            self.fast_for += real_dt
            self.slow_for = 0.0
        else:
            self.slow_for = self.fast_for = 0.0

        if self.slow_for > DOWN_AFTER_S and self.index < len(STEPS) - 1:
            self.index += 1
        elif self.fast_for > UP_AFTER_S and self.index > 0:
            self.index -= 1
        else:
            return False
        self.slow_for = self.fast_for = 0.0
        self.avg = None  # po zmianie mierzymy od nowa
        return True
