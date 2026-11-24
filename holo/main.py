"""Pętla główna: nawigacja między poziomami, mysz i klawisze, rysowanie klatki."""
from __future__ import annotations

import math

import numpy as np
import pygame

from .catalog import CelestialObject, load_catalog
from .config import Config, parse_args
from .levels import GalaxyLevel, Level, LocalLevel, SolarLevel
from .output import Output
from .picking import pick
from .render import StarLayer
from .ui import (Cursor, InfoCard, draw_breadcrumb, draw_calibration, draw_highlight, draw_hints,
                 draw_label, text)

ORDER = ("galaxy", "local", "solar")
TRANSITION_S = 1.6     # czas przejścia między poziomami
CARD_OFFSET = -0.17    # o ile przesunąć obraz w lewo, gdy karta jest widoczna
TOUR_STEP_S = 14.0     # tryb pokazowy: co ile sekund następny obiekt
DRAG_THRESHOLD_PX = 6  # ruch myszy z wciśniętym przyciskiem większy niż to = przeciąganie, nie klik


class Backdrop:
    """Migoczące gwiazdy tła – nieruchome względem ekranu."""

    def __init__(self, size, rng: np.random.Generator):
        n = size[0] * size[1] // 3500
        self.x = rng.uniform(0, size[0], n)
        self.y = rng.uniform(0, size[1], n)
        self.col = rng.uniform(0.08, 0.35, (n, 1)) * np.array([[0.8, 0.85, 1.0]])
        self.phase = rng.uniform(0, 2 * np.pi, n)
        self.rate = rng.uniform(0.4, 2.0, n)

    def draw(self, layer: StarLayer, t: float, alpha: float = 1.0) -> None:
        tw = 0.55 + 0.45 * np.sin(self.phase + self.rate * t)
        layer.add(self.x, self.y, self.col * (tw * alpha)[:, None])


class App:
    def __init__(self, cfg: Config, size: tuple[int, int]):
        self.cfg = cfg
        self.size = size
        rng = np.random.default_rng(cfg.seed)
        catalog = load_catalog()
        self.levels: dict[str, Level] = {
            "galaxy": GalaxyLevel(catalog, cfg, rng),
            "local": LocalLevel(catalog, rng),
            "solar": SolarLevel(catalog, rng),
        }
        self.cams = {k: lv.make_camera() for k, lv in self.levels.items()}
        self.layer = StarLayer(size, cfg.render_scale)
        self.backdrop = Backdrop(size, rng)
        self.card = InfoCard(size)

        self.current = "galaxy"
        self.selected: CelestialObject | None = None
        self.hovered: CelestialObject | None = None
        self.entered_from: dict[str, CelestialObject] = {}  # poziom → obiekt, przez który weszliśmy
        self.transition: dict | None = None
        self.t = 0.0
        self.idle = 0.0
        self.tour_index = -1
        self.touring = False
        self.pressed = False      # lewy przycisk wciśnięty
        self.drag_travel = 0.0    # ile pikseli przejechała mysz od wciśnięcia
        self.last_real_dt = 1 / 30

    # ------------------------------------------------------------------ akcje
    @property
    def level(self) -> Level:
        return self.levels[self.current]

    @property
    def cam(self):
        return self.cams[self.current]

    def select(self, obj: CelestialObject) -> None:
        self.selected = obj
        self.card.show(obj)
        self.cam.fly_to(target=obj.position_at(self.t), zoom=obj.zoom, offset_x=CARD_OFFSET)

    def deselect(self) -> None:
        self.selected = None
        self.card.hide()
        lv = self.level
        self.cam.fly_to(target=(0.0, 0.0, 0.0), zoom=lv.home_zoom, offset_x=0.0)

    def click(self, pos) -> None:
        if self.transition:
            return
        obj = pick(self.level.hits, pos)
        if obj is None:
            if self.selected:
                self.deselect()
        elif obj is self.selected and obj.enter:
            self.descend(obj)
        else:
            self.select(obj)

    # ------------------------------------------------- mysz: klik albo obracanie
    @property
    def dragging(self) -> bool:
        return self.pressed and self.drag_travel > DRAG_THRESHOLD_PX

    def press(self) -> None:
        self.pressed = True
        self.drag_travel = 0.0
        self.cam.stop_spin()

    def motion(self, dx: float, dy: float) -> bool:
        """Ruch myszy. Zwraca True, gdy to przeciąganie (wtedy kursor ma stać w miejscu)."""
        if not self.pressed:
            return False
        self.drag_travel += abs(dx) + abs(dy)
        if self.dragging and not self.transition:
            self.cam.drag(dx, dy, self.last_real_dt)
            return True
        return False

    def release(self, pos) -> None:
        was_drag = self.dragging
        self.pressed = False
        self.cam.release()
        if not was_drag:
            self.click(pos)

    def back(self) -> None:
        if self.transition:
            return
        if self.selected:
            self.deselect()
        elif self.current != ORDER[0]:
            self.ascend()

    def descend(self, obj: CelestialObject) -> None:
        to = obj.enter
        self.entered_from[to] = obj
        # Stary poziom "wlatuje" w obiekt i gaśnie, nowy wyłania się z oddali.
        self.cam.fly_to(zoom=obj.zoom * 5, offset_x=0.0)
        new_cam = self.cams[to]
        lv = self.levels[to]
        new_cam.fly_to(target=(0.0, 0.0, 0.0), zoom=lv.home_zoom * 0.12, offset_x=0.0)
        new_cam.jump()
        new_cam.fly_to(zoom=lv.home_zoom)
        self._start_transition(to, then_select=None)

    def ascend(self) -> None:
        to = ORDER[ORDER.index(self.current) - 1]
        obj = self.entered_from.get(self.current)
        self.cam.fly_to(zoom=self.level.home_zoom * 0.12, offset_x=0.0)
        new_cam = self.cams[to]
        if obj is not None:
            # Wracamy do obiektu, przez który weszliśmy – z bliska, a potem lekko się oddalamy.
            new_cam.fly_to(target=obj.position_at(self.t), zoom=obj.zoom * 5, offset_x=0.0)
            new_cam.jump()
        self._start_transition(to, then_select=obj)

    def _start_transition(self, to: str, then_select: CelestialObject | None) -> None:
        self.selected = None
        self.hovered = None
        self.card.hide()
        self.transition = {"from": self.current, "to": to, "p": 0.0, "select": then_select}

    def rotate_view(self, yaw_deg: float, tilt_deg: float | None) -> None:
        """Ustawia obrót kamery bieżącego poziomu (do testów i zrzutów ekranu)."""
        cam = self.cam
        cam.yaw += math.radians(yaw_deg)
        if tilt_deg is not None:
            cam.tilt = cam.goal_tilt = cam._clamp_tilt(math.radians(tilt_deg))
        cam.since_user = 0.0

    def select_by_id(self, obj_id: str) -> bool:
        """Natychmiastowy wybór obiektu (do testów i zrzutów ekranu)."""
        for key, lv in self.levels.items():
            obj = lv.find(obj_id)
            if obj:
                self.current = key
                self.select(obj)
                self.cam.jump()
                self.card.alpha = 1.0
                return True
        return False

    # ------------------------------------------------------------ tryb pokazowy
    def input_activity(self) -> None:
        self.idle = 0.0
        self.touring = False

    def _tour_step(self) -> None:
        objs = self.level.objects
        if not objs or self.transition:
            return
        self.tour_index = (self.tour_index + 1) % len(objs)
        self.select(objs[self.tour_index])

    # ----------------------------------------------------------- aktualizacja
    def update(self, dt: float, real_dt: float, cursor: Cursor) -> None:
        self.t += dt
        self.idle += real_dt
        self.last_real_dt = max(real_dt, 1e-3)
        self.card.update(real_dt)

        tour_after = self.cfg.tour_after
        if tour_after > 0 and self.idle > tour_after:
            if not self.touring:
                self.touring = True
                self.tour_timer = 0.0
                self._tour_step()
            self.tour_timer += real_dt
            if self.tour_timer > TOUR_STEP_S:
                self.tour_timer = 0.0
                self._tour_step()

        if self.transition:
            tr = self.transition
            tr["p"] += real_dt / TRANSITION_S
            self.cams[tr["from"]].update(dt, real_dt=real_dt)
            self.cams[tr["to"]].update(dt, real_dt=real_dt)
            if tr["p"] >= 1.0:
                self.current = tr["to"]
                self.transition = None
                if tr["select"] is not None:
                    self.select(tr["select"])
            return

        # Kamera podąża za poruszającym się obiektem (np. planetą).
        if self.selected is not None:
            self.cam.goal_target = np.asarray(self.selected.position_at(self.t), dtype=float)
        self.cam.update(dt, auto_rotate=self.selected is None, real_dt=real_dt)

        self.hovered = pick(self.level.hits, cursor.pos) if cursor.alpha > 0 else None

    # ---------------------------------------------------------------- rysowanie
    def draw(self, frame: pygame.Surface, cursor: Cursor) -> None:
        size = self.size
        t = self.t
        if self.transition:
            tr = self.transition
            p = min(tr["p"], 1.0)
            layers = [(tr["from"], (1 - p) ** 1.5), (tr["to"], p ** 1.5)]
        else:
            layers = [(self.current, 1.0)]

        self.layer.begin()
        self.backdrop.draw(self.layer, t)
        for key, a in layers:
            if a > 0.01:
                self.levels[key].draw_points(self.layer, self.cams[key], size, t, a)
        frame.blit(self.layer.finish(self.cfg.glow), (0, 0))
        for key, a in layers:
            if a > 0.01:
                self.levels[key].draw_sprites(frame, self.cams[key], t, a)

        if not self.transition:
            self._draw_selection(frame, cursor)

        crumbs = [self.levels[k].title for k in ORDER[: ORDER.index(self.current) + 1]]
        draw_breadcrumb(frame, crumbs)
        draw_hints(frame, self.current != ORDER[0] or self.selected is not None, cursor.alpha)

    def _draw_selection(self, frame: pygame.Surface, cursor: Cursor) -> None:
        anchor = None
        for o, x, y, r in self.level.hits:
            if o is self.selected:
                draw_highlight(frame, x, y, r, self.t, 1.0, selected=True)
                anchor = (x, y, r)
            elif o is self.hovered:
                draw_highlight(frame, x, y, r, self.t, cursor.alpha, selected=False)
                draw_label(frame, o.name, x, y, r, cursor.alpha, sub=o.type)
        if self.selected is not None and self.hovered is self.selected and self.selected.enter and anchor:
            draw_label(frame, "Kliknij, aby wejść", anchor[0], anchor[1], anchor[2], cursor.alpha)
        self.card.draw(frame, anchor)


def run(cfg: Config) -> None:
    pygame.init()
    pygame.display.set_caption("Holo – Droga Mleczna")
    if cfg.windowed:
        screen = pygame.display.set_mode((cfg.width, cfg.height))
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    size = screen.get_size()
    out = Output(screen, cfg.flip_h, cfg.flip_v)
    frame = pygame.Surface(size, 0, 32)

    # W oknie (testy na PC) kursor podąża za myszą systemową. Na pełnym ekranie
    # mysz jest "przechwycona" i liczy się tylko jej ruch – pozycja systemowego
    # kursora nie ma sensu, bo widz patrzy na odbicie.
    relative_mouse = not cfg.windowed
    pygame.mouse.set_visible(False)
    if relative_mouse:
        pygame.event.set_grab(True)
    cursor = Cursor(size)

    app = App(cfg, size)
    if cfg.select and not app.select_by_id(cfg.select):
        print(f"Nie ma obiektu o id {cfg.select!r}")
    if cfg.yaw or cfg.tilt is not None:
        app.rotate_view(cfg.yaw, cfg.tilt)

    clock = pygame.time.Clock()
    calibrating = cfg.calibrate
    paused = False
    frame_no = 0
    running = True

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.MOUSEMOTION:
                app.input_activity()
                dx, dy = ev.rel
                if out.flip_h and not relative_mouse:
                    dx = -dx
                if out.flip_v and not relative_mouse:
                    dy = -dy
                if app.motion(dx, dy):
                    cursor.idle = 0.0  # obracamy – kursor stoi, ale nie gaśnie
                elif relative_mouse:
                    cursor.move_by(dx, dy)
                else:
                    cursor.move_to(out.to_logical(ev.pos))
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                app.input_activity()
                cursor.idle = 0.0
                if ev.button == 1:
                    app.press()
                elif ev.button == 3:
                    app.back()
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 1:
                    app.release(cursor.pos)
            elif ev.type == pygame.MOUSEWHEEL:
                app.input_activity()
                cam = app.cam
                cam.fly_to(zoom=min(max(cam.goal_zoom * (1.25 ** ev.y), app.level.home_zoom * 0.6), 120.0))
            elif ev.type == pygame.KEYDOWN:
                app.input_activity()
                k = ev.key
                if k == pygame.K_q:
                    running = False
                elif k in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    app.back()
                elif k == pygame.K_c:
                    calibrating = not calibrating
                elif k == pygame.K_h and calibrating:
                    out.flip_h = not out.flip_h
                elif k == pygame.K_v and calibrating:
                    out.flip_v = not out.flip_v
                elif k == pygame.K_SPACE:
                    paused = not paused
                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    cfg.speed = min(cfg.speed * 1.25, 8.0)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    cfg.speed = max(cfg.speed / 1.25, 0.05)
                elif k == pygame.K_g:
                    cfg.glow = not cfg.glow
                elif k == pygame.K_f:
                    cfg.show_fps = not cfg.show_fps

        real_dt = clock.tick(cfg.fps) / 1000.0
        if cfg.frames:  # tryb testowy: stały krok czasu
            real_dt = 1.0 / cfg.fps
        real_dt = min(real_dt, 0.1)
        dt = 0.0 if paused else real_dt * cfg.speed
        cursor.update(real_dt)
        app.update(dt, real_dt, cursor)

        frame.fill((0, 0, 0))
        if calibrating:
            draw_calibration(frame, out.flip_h, out.flip_v)
        else:
            app.draw(frame, cursor)
        cursor.draw(frame)
        if cfg.show_fps:
            text(frame, f"{clock.get_fps():.0f} FPS", 24, (90, 90, 90), topleft=(8, 8))

        out.present(frame)
        frame_no += 1
        if cfg.frames and frame_no >= cfg.frames:
            running = False

    if cfg.screenshot:
        pygame.image.save(frame, cfg.screenshot)
    pygame.quit()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
