"""Wybieranie obiektu najbliższego kursorowi."""
from __future__ import annotations

import math

SLACK_PX = 10  # tolerancja – nie trzeba trafiać idealnie w środek


def pick(hits, pos, slack: float = SLACK_PX):
    """hits: lista (obiekt, x, y, promień). Zwraca obiekt najbliższy pos albo None.

    Obiekt jest kandydatem, gdy kursor leży w jego promieniu (+ tolerancja).
    Wynik = odległość od środka + połowa promienia: przy równych rozmiarach wygrywa
    bliższy, a mały obiekt w środku dużego (pulsar w mgławicy) da się kliknąć osobno.
    """
    best, best_score = None, math.inf
    px, py = pos
    for obj, x, y, r in hits:
        d = math.hypot(x - px, y - py)
        if d <= r + slack:
            score = d + 0.5 * r
            if score < best_score:
                best, best_score = obj, score
    return best
