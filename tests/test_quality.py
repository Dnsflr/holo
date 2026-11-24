from holo.main import logical_size
from holo.quality import STEPS, Quality

DT = 1 / 30


def test_wolne_klatki_obnizaja_jakosc():
    q = Quality("auto", 30)
    for _ in range(90):              # 3 s klatek trwających 50 ms (budżet 33 ms)
        q.frame(0.050, DT)
    assert q.index >= 1


def test_szybkie_klatki_podnosza_jakosc():
    q = Quality("auto", 30)
    q.index = 2
    for _ in range(30 * 12):         # 12 s bardzo szybkich klatek
        q.frame(0.005, DT)
    assert q.index == 0


def test_brak_migotania_przy_czasie_na_granicy():
    q = Quality("auto", 30)
    q.index = 1
    changes = 0
    for i in range(30 * 20):         # czas klatki między progami – nic nie powinno się zmieniać
        changes += q.frame(0.025 if i % 2 else 0.028, DT)
    assert changes == 0


def test_staly_tryb_sie_nie_zmienia():
    q = Quality("low", 30)
    for _ in range(300):
        q.frame(0.2, DT)
    assert q.step is STEPS[2]


def test_rozmiar_logiczny_zachowuje_proporcje():
    assert logical_size((1920, 1080), 540) == (960, 540)
    w, h = logical_size((1280, 1024), 540)
    assert h == 540 and abs(w / h - 1280 / 1024) < 0.01
    assert logical_size((800, 480), 540) == (800, 480)      # ekran mniejszy niż limit
    assert logical_size((1920, 1080), 0) == (1920, 1080)    # 0 = pełna rozdzielczość
