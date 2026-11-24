from holo.output import logical_point

SIZE = (100, 50)


def test_bez_odbicia_punkt_bez_zmian():
    assert logical_point((10, 20), SIZE, False, False) == (10, 20)


def test_odbicie_poziome():
    assert logical_point((0, 20), SIZE, True, False) == (99, 20)
    assert logical_point((99, 20), SIZE, True, False) == (0, 20)


def test_odbicie_pionowe():
    assert logical_point((10, 0), SIZE, False, True) == (10, 49)


def test_oba_odbicia_to_obrot_o_180():
    assert logical_point((10, 20), SIZE, True, True) == (89, 29)


def test_podwojne_przeliczenie_wraca_do_punktu():
    for fh in (False, True):
        for fv in (False, True):
            p = logical_point((37, 11), SIZE, fh, fv)
            assert logical_point(p, SIZE, fh, fv) == (37, 11)
