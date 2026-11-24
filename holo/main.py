"""Pętla główna: nawigacja między poziomami, mysz i klawisze, rysowanie klatki."""
from __future__ import annotations

import math
import os
import time

import numpy as np
import pygame

from .catalog import CelestialObject, load_catalog
from .config import Config, parse_args
from .levels import GalaxyLevel, Level, SolarLevel
from .output import Output
from .picking import pick
from .quality import Quality
from .render import StarLayer
from .scenes.blackhole3d import BlackHoleScene
from .scenes.crab import CrabScene
from .ui import (Auras, Cursor, InfoCard, draw_breadcrumb, draw_calibration, draw_hints, draw_label,
                 text)

HOME = "galaxy"  # mapa – z niej wchodzi się do scen, do niej się wraca
TRANSITION_S = 1.6     # czas przejścia między poziomami
CARD_OFFSET = -0.17    # o ile przesunąć obraz w lewo, gdy karta jest widoczna
# Tryb pokazowy: obiekt na mapie → co pokazać w jego scenie.
TOUR = [("sgr_a", ["sgr_a_detail", "s2"]), ("crab", ["crab_pulsar", "crab_nebula"]), ("sun", ["earth", "saturn"])]
DRAG_THRESHOLD_PX = 6  # ruch myszy z wciśniętym przyciskiem większy niż to = przeciąganie, nie klik


def sunlit_yaw(planet_pos, side_deg: float = 40.0) -> float:
    """Obrót kamery, przy którym Słońce (w środku układu) świeci na planetę z ukosa zza widza.

    Na hologramie strona nocna jest niewidoczna, więc nie chcemy patrzeć na planetę "pod światło".
    """
    s = -np.asarray(planet_pos, dtype=float)
    a = math.atan2(s[0], s[2]) + math.radians(side_deg)
    vx, vz = math.sin(a), math.cos(a)
    # Kierunek do widza w układzie sceny to (-sin yaw, cos yaw).
    return math.atan2(-vx, vz)


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
            "blackhole": BlackHoleScene(catalog, rng),
            "crab": CrabScene(catalog, rng),
            "solar": SolarLevel(catalog, rng),
        }
        self.cams = {k: lv.make_camera() for k, lv in self.levels.items()}
        self.layer = StarLayer(size, cfg.render_scale)
        self.backdrop = Backdrop(size, rng)
        self.card = InfoCard(size)
        self.auras = Auras()
        self.real_t = 0.0   # czas rzeczywisty – poświaty "oddychają" także w pauzie

        self.current = HOME
        self.selected: CelestialObject | None = None
        self.hovered: CelestialObject | None = None
        self.entered_from: dict[str, CelestialObject] = {}  # poziom → obiekt, przez który weszliśmy
        self.transition: dict | None = None
        self.t = 0.0
        self.idle = 0.0
        self.touring = False
        self.tour_steps: list = []
        self.tour_wait = 0.0
        self.pressed = False      # lewy przycisk wciśnięty
        self.drag_travel = 0.0    # ile pikseli przejechała mysz od wciśnięcia
        self.last_real_dt = 1 / 30
        self.quality = Quality(cfg.quality, cfg.fps)
        self.apply_quality()
        self.set_labels(cfg.labels)

    # ------------------------------------------------------------------ akcje
    @property
    def level(self) -> Level:
        return self.levels[self.current]

    @property
    def cam(self):
        return self.cams[self.current]

    def select(self, obj: CelestialObject) -> None:
        self.selected = obj
        self.level.selected = obj
        self.card.show(obj)
        self.cam.fly_to(target=obj.position_at(self.t), zoom=obj.zoom, offset_x=CARD_OFFSET)
        if obj.kind == "planet":
            self.cam.goal_yaw = sunlit_yaw(obj.position_at(self.t))

    def quality_name(self) -> str:
        return "—" if self.quality is None else self.quality.name

    def apply_quality(self) -> None:
        step = self.quality.step
        for lv in self.levels.values():
            lv.stride = self.quality.stride
        self.layer.set_gas(step.gas)

    def frame_done(self, work_s: float, real_dt: float) -> None:
        """Czas pracy nad klatką → automatyczna jakość."""
        if self.quality.frame(work_s, real_dt):
            self.apply_quality()

    def set_labels(self, on: bool) -> None:
        """Napisy pomocnicze wł./wył. (karty po kliknięciu są zawsze)."""
        self.labels = on
        for lv in self.levels.values():
            lv.show_text = on

    def deselect(self) -> None:
        self.selected = None
        self.level.selected = None
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
        elif obj.enter and (obj is self.selected or not self.labels):
            # Bez napisów nie ma podpowiedzi "kliknij ponownie" – od razu wlatujemy do sceny.
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
        elif self.current != HOME:
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
        # Po przylocie scena sama pokazuje kartę swojego głównego obiektu.
        focus = lv.find(obj.focus) if obj.focus else None
        self._start_transition(to, then_select=focus)

    def ascend(self) -> None:
        to = HOME
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
        self.level.selected = None
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

    def _build_tour(self) -> list[tuple[str, str | None, float]]:
        """Scenariusz pokazu: (akcja, id obiektu, ile sekund trwa ten krok)."""
        steps: list[tuple[str, str | None, float]] = []
        if self.selected is not None:
            steps.append(("back", None, 2.0))
        if self.current != HOME:
            steps.append(("back", None, 3.0))
        for map_id, inner in TOUR:
            steps.append(("select", map_id, 7.0))
            steps.append(("enter", None, 6.0))
            for obj_id in inner:
                steps.append(("select", obj_id, 10.0))
            steps.append(("back", None, 2.0))   # odznacz
            steps.append(("back", None, 4.0))   # wróć na mapę
        return steps

    def _tour_do(self, action: str, obj_id: str | None) -> None:
        if action == "select":
            obj = self.level.find(obj_id)
            if obj is not None:
                self.select(obj)
        elif action == "enter":
            if self.selected is not None and self.selected.enter:
                self.descend(self.selected)
        elif action == "back":
            self.back()

    # ----------------------------------------------------------- aktualizacja
    def update(self, dt: float, real_dt: float, cursor: Cursor) -> None:
        self.t += dt
        self.idle += real_dt
        self.last_real_dt = max(real_dt, 1e-3)
        self.real_t += real_dt
        self.card.update(real_dt)

        tour_after = self.cfg.tour_after
        if tour_after > 0 and self.idle > tour_after and not self.transition:
            if not self.touring or not self.tour_steps:
                self.touring = True
                self.tour_steps = self._build_tour()
                self.tour_wait = 0.0
            self.tour_wait -= real_dt
            if self.tour_wait <= 0 and self.tour_steps:
                action, obj_id, duration = self.tour_steps.pop(0)
                self._tour_do(action, obj_id)
                self.tour_wait = duration

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
        frame.blit(self.layer.finish(self.cfg.glow and self.quality.step.glow), (0, 0))
        if not self.transition:
            # Poświaty pod obiektami (pozycje z poprzedniej klatki – różnica niezauważalna).
            self.auras.draw(frame, self.level.hits, self.hovered, self.selected, self.real_t,
                            self.last_real_dt, cursor.alpha)
        for key, a in layers:
            if a > 0.01:
                self.levels[key].draw_sprites(frame, self.cams[key], t, a)

        if not self.transition:
            self._draw_selection(frame, cursor)

        if self.labels:
            crumbs = [self.levels[HOME].title]
            if self.current != HOME:
                crumbs.append(self.levels[self.current].title)
            draw_breadcrumb(frame, crumbs)
            draw_hints(frame, self.current != HOME or self.selected is not None, cursor.alpha)

    def _draw_selection(self, frame: pygame.Surface, cursor: Cursor) -> None:
        anchor = None
        for o, x, y, r in self.level.hits:
            if o is self.selected:
                anchor = (x, y, r)
            elif o is self.hovered and self.labels:
                draw_label(frame, o.name, x, y, r, cursor.alpha, sub=o.type)
        self.card.draw(frame, anchor)


def logical_size(screen: tuple[int, int], render_height: int) -> tuple[int, int]:
    """Rozmiar klatki liczonej przez program – mniejszy od ekranu, z tymi samymi proporcjami."""
    sw, sh = screen
    if render_height <= 0 or render_height >= sh:
        return sw, sh
    h = render_height
    w = int(round(h * sw / sh / 2)) * 2
    return w, h


def run(cfg: Config) -> None:
    # Powiększanie klatki na ekran robi karta graficzna (SDL) – z wygładzaniem.
    os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "1")
    pygame.init()
    pygame.display.set_caption("Holo – Droga Mleczna")
    if cfg.windowed:
        size = logical_size((cfg.width, cfg.height), cfg.render_height)
        flags = pygame.SCALED if size != (cfg.width, cfg.height) else 0
        screen = pygame.display.set_mode(size, flags)
    else:
        info = pygame.display.Info()
        size = logical_size((info.current_w, info.current_h), cfg.render_height)
        screen = pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.SCALED)
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
                elif k == pygame.K_t:
                    app.set_labels(not app.labels)

        real_dt = clock.tick(cfg.fps) / 1000.0
        if cfg.frames:  # tryb testowy: stały krok czasu
            real_dt = 1.0 / cfg.fps
        real_dt = min(real_dt, 0.1)
        dt = 0.0 if paused else real_dt * cfg.speed
        cursor.update(real_dt)
        work_start = time.perf_counter()
        app.update(dt, real_dt, cursor)

        frame.fill((0, 0, 0))
        if calibrating:
            draw_calibration(frame, out.flip_h, out.flip_v)
        else:
            app.draw(frame, cursor)
        cursor.draw(frame)
        if cfg.show_fps:
            avg = app.quality.avg
            work = f" • praca {avg * 1000:.0f} ms" if avg else ""
            text(frame, f"{clock.get_fps():.0f} FPS • jakość: {app.quality_name()}{work}", 20,
                 (110, 110, 110), topleft=(8, 8))
        if not cfg.frames:
            app.frame_done(time.perf_counter() - work_start, real_dt)

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
