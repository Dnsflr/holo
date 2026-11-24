"""Wybieranie obiektu najbliższego kursorowi."""
from __future__ import annotations

import math

SLACK_PX = 10  # tolerancja – nie trzeba trafiać idealnie w środek


def pick(hits, pos, slack: float = SLACK_PX):
    """hits: lista (obiekt, x, y, promień). Zwraca obiekt najbliższy pos albo None.

    Obiekt jest kandydatem, gdy kursor leży w jego promieniu (+ tolerancja);
    spośród kandydatów wygrywa ten, którego środek jest najbliżej.
    """
    best, best_d = None, math.inf
    px, py = pos
    for obj, x, y, r in hits:
        d = math.hypot(x - px, y - py)
        if d <= r + slack and d < best_d:
            best, best_d = obj, d
    return best
