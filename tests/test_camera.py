import math

import numpy as np

from holo.camera import Camera


def test_przeciaganie_w_bok_obraca_wokol_pionu():
    cam = Camera(1.0, tilt_deg=30)
    yaw0 = cam.yaw
    cam.drag(100, 0, 1 / 30)
    assert cam.yaw > yaw0


def test_pochylenie_nie_wychodzi_poza_zakres():
    cam = Camera(1.0, tilt_deg=30, tilt_range=(10, 90))
    cam.drag(0, 10_000, 1 / 30)
    assert cam.tilt == math.radians(90)
    cam.drag(0, -100_000, 1 / 30)
    assert cam.tilt == math.radians(10)


def test_bezwladnosc_po_puszczeniu_i_jej_wygasanie():
    cam = Camera(1.0)
    for _ in range(5):
        cam.drag(30, 0, 1 / 30)
    cam.release()
    yaw0 = cam.yaw
    cam.update(1 / 30, auto_rotate=False)
    assert cam.yaw > yaw0                # dalej się kręci
    for _ in range(300):
        cam.update(1 / 30, auto_rotate=False)
    assert abs(cam.spin_yaw) < 1e-3      # i w końcu staje


def test_automatyczny_obrot_czeka_po_interakcji():
    cam = Camera(1.0)
    cam.drag(1, 0, 1 / 30)
    cam.release()
    cam.stop_spin()
    yaw0 = cam.yaw
    cam.update(1.0, auto_rotate=True)
    assert cam.yaw == yaw0               # zaraz po puszczeniu: bez automatycznego obrotu


def test_to_camera_zgodne_z_rzutowaniem():
    cam = Camera(1.0, tilt_deg=40, yaw=0.7)
    pts = np.array([[0.3, 0.1, -0.2], [0.0, 0.0, 0.5]], np.float32)
    sx1, sy1, _, _ = cam.project(pts, (800, 600))
    sx2, sy2, _, _ = cam.perspective(cam.to_camera(pts), (800, 600))
    assert np.allclose(sx1, sx2) and np.allclose(sy1, sy2)
