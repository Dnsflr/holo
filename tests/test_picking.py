from holo.picking import pick

A, B = object(), object()


def test_trafienie_w_obiekt():
    assert pick([(A, 100, 100, 20)], (110, 105)) is A


def test_chybienie():
    assert pick([(A, 100, 100, 20)], (200, 200)) is None


def test_wygrywa_blizszy_z_dwoch_nachodzacych():
    hits = [(A, 100, 100, 30), (B, 130, 100, 30)]
    assert pick(hits, (122, 100)) is B
    assert pick(hits, (105, 100)) is A


def test_tolerancja_przy_krawedzi():
    assert pick([(A, 0, 0, 10)], (18, 0)) is A
    assert pick([(A, 0, 0, 10)], (25, 0)) is None


def test_maly_obiekt_w_srodku_duzego():
    small, big = object(), object()
    hits = [(big, 100, 100, 200), (small, 100, 100, 15)]
    assert pick(hits, (103, 102)) is small   # w środku – mały pulsar
    assert pick(hits, (180, 100)) is big     # dalej – mgławica
