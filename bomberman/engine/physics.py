"""Fizyka: kopanie, ślizg z tarciem, zderzenia, odrzut, ruchome przeszkody."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from bomberman.engine.state import EMPTY, Bomb, Player

if TYPE_CHECKING:
    from bomberman.ai.danger import TickInfo
    from bomberman.config import GameConfig
    from bomberman.engine.state import Cell, Event, GameState, Obstacle

EPS = 1e-9
MIN_SPEED = 1e-3      # wolniejsze ciało uznajemy za zatrzymane
MAX_HITS = 4          # najwięcej zderzeń jednego ciała w ticku
MAX_SLIDE_TICKS = 40  # bezpiecznik dla przewidywania ślizgu

Body = Bomb | Player


def obstacle_cells(o: Obstacle, width: int) -> tuple[int, ...]:
    """Pola zajmowane przez ruchomą przeszkodę (dwa, gdy stoi w położeniu połówkowym)."""
    if o.vx != 0.0:
        y = int(o.y + 0.5)
        fx = int(o.x + EPS)
        if o.x - fx > 1e-6:
            return (y * width + fx, y * width + fx + 1)
        return (y * width + fx,)
    x = int(o.x + 0.5)
    fy = int(o.y + EPS)
    if o.y - fy > 1e-6:
        return (fy * width + x, (fy + 1) * width + x)
    return (fy * width + x,)


def travel(speed: float, dt: float, mu: float) -> tuple[float, float]:
    """Droga i prędkość końcowa po czasie `dt` przy opóźnieniu `mu`."""
    if mu > 0.0 and speed <= mu * dt:
        return speed * speed / (2.0 * mu), 0.0
    return speed * dt - mu * dt * dt / 2.0, speed - mu * dt


def time_to(distance: float, speed: float, mu: float) -> float:
    """Czas przebycia drogi `distance` przy prędkości początkowej `speed` i opóźnieniu `mu`."""
    if distance <= 0.0:
        return 0.0
    if mu <= 0.0:
        return distance / speed
    disc = max(0.0, speed * speed - 2.0 * mu * distance)
    return (speed - math.sqrt(disc)) / mu


def _set_velocity(body: Body | Obstacle, vx: float, vy: float) -> None:
    """Ustawia prędkość; ciało porusza się zawsze wzdłuż jednej osi."""
    if abs(vx) < MIN_SPEED:
        vx = 0.0
    if abs(vy) < MIN_SPEED:
        vy = 0.0
    if vx and vy:
        if abs(vx) >= abs(vy):
            vy = 0.0
        else:
            vx = 0.0
    if vx:
        body.y = float(int(body.y + 0.5))
    elif vy:
        body.x = float(int(body.x + 0.5))
    else:
        body.x, body.y = float(int(body.x + 0.5)), float(int(body.y + 0.5))
    body.vx, body.vy = vx, vy


def _set_axis(body: Body, axis: int, v: float) -> None:
    if axis == 0:
        _set_velocity(body, v, body.vy)
    else:
        _set_velocity(body, body.vx, v)


def _along(body: Body | Obstacle, axis: int) -> float:
    return body.vx if axis == 0 else body.vy


def _mass(body: Body, cfg: GameConfig) -> float:
    return cfg.physics.mass_player if isinstance(body, Player) else cfg.physics.mass_bomb


def _wall_restitution(body: Body, cfg: GameConfig) -> float:
    return 0.0 if isinstance(body, Player) else cfg.physics.restitution_wall


def _mark(body: Body, state: GameState) -> None:
    if isinstance(body, Player):
        body.knocked_tick = state.tick
    else:
        body.moved = True


def _cell(body: Body | Obstacle, w: int) -> Cell:
    return int(body.y + 0.5) * w + int(body.x + 0.5)


def _blocker(state: GameState, cell: Cell, me: Body) -> tuple[str, object] | None:
    """Co stoi na polu `cell` z punktu widzenia ciała `me`."""
    if state.grid[cell] != EMPTY:
        return ("static", None)
    w = state.width
    for o in state.obstacles:
        if cell in obstacle_cells(o, w):
            return ("obstacle", o)
    for p in state.players:
        if p is not me and p.alive and _cell(p, w) == cell:
            return ("body", p) if p.vx or p.vy else ("anchor", p)
    for b in state.bombs:
        if b is not me and _cell(b, w) == cell:
            return ("body", b)
    return None


def _scan(state: GameState, body: Body, axis: int, s: int, reach: float) -> tuple[float, tuple | None]:
    """Odległość do punktu kontaktu z pierwszą przeszkodą w kierunku ruchu (najdalej `reach`)."""
    w = state.width
    pos = body.x if axis == 0 else body.y
    here = int(pos + 0.5)
    offset = s * (pos - here)
    step = s if axis == 0 else s * w
    cell = _cell(body, w)
    k = 1
    while True:
        contact = (k - 1) - offset
        if contact > reach:
            return math.inf, None
        cell += step
        hit = _blocker(state, cell, body)
        if hit is not None:
            return contact, hit
        k += 1


def _collide(state: GameState, body: Body, axis: int, v1: float, hit: tuple, cfg: GameConfig,
             events: list[Event] | None) -> bool:
    """Rozwiązuje zderzenie w punkcie kontaktu. Zwraca False, gdy ciała się nie zbliżają."""
    kind, other = hit
    s = 1.0 if v1 > 0 else -1.0
    ph = cfg.physics
    if kind == "static":
        _set_axis(body, axis, -_wall_restitution(body, cfg) * v1)
    elif kind == "anchor":
        _set_axis(body, axis, 0.0)
    elif kind == "obstacle":
        u = _along(other, axis)
        if (v1 - u) * s <= EPS:
            return False
        e = _wall_restitution(body, cfg)
        _set_axis(body, axis, (1.0 + e) * u - e * v1)
    else:
        v2 = _along(other, axis)
        if (v1 - v2) * s <= EPS:
            return False
        m1, m2, e = _mass(body, cfg), _mass(other, cfg), ph.restitution_body
        p = m1 * v1 + m2 * v2
        _set_axis(body, axis, (p - m2 * e * (v1 - v2)) / (m1 + m2))
        _set_axis(other, axis, (p + m1 * e * (v1 - v2)) / (m1 + m2))
        _mark(other, state)
    if events is not None:
        events.append({"type": "collision", "x": round(body.x, 3), "y": round(body.y, 3), "with": kind,
                       **({"player": body.id} if isinstance(body, Player) else {"bomb": body.id})})
    return True


def _advance(state: GameState, body: Body, cfg: GameConfig, events: list[Event] | None) -> None:
    """Jeden tick ruchu ciała dynamicznego: tarcie, kontakty i zderzenia w dokładnym czasie."""
    mu = cfg.physics.friction
    t_left = 1.0
    hits = 0
    while t_left > EPS and (body.vx or body.vy):
        axis = 0 if body.vx else 1
        v = _along(body, axis)
        s = 1 if v > 0 else -1
        speed = abs(v)
        dist, end_speed = travel(speed, t_left, mu)
        contact, hit = _scan(state, body, axis, s, dist)
        if hit is None or contact >= dist - EPS:
            _shift(body, axis, s * dist)
            _set_axis(body, axis, s * end_speed)
            return
        contact = max(contact, 0.0)
        tc = time_to(contact, speed, mu)
        _shift(body, axis, s * contact)
        speed_at = max(0.0, speed - mu * tc)
        t_left -= tc
        if not _collide(state, body, axis, s * speed_at, hit, cfg, events):
            _set_axis(body, axis, s * max(0.0, speed_at - mu * t_left))
            return
        hits += 1
        if hits >= MAX_HITS:
            return


def _shift(body: Body, axis: int, d: float) -> None:
    if axis == 0:
        body.x += d
    else:
        body.y += d


def _move_obstacle(state: GameState, o: Obstacle, cfg: GameConfig, events: list[Event] | None) -> None:
    """Ruch przeszkody: stała prędkość, zawraca przed przeszkodą, popycha bomby."""
    w = state.width
    axis = 0 if o.vx else 1
    u = _along(o, axis)
    if not u:
        return
    s = 1 if u > 0 else -1
    step = s if axis == 0 else s * w
    old = obstacle_cells(o, w)
    ox, oy = o.x, o.y
    _shift(o, axis, u)
    entered = [c for c in obstacle_cells(o, w) if c not in old]
    o.x, o.y = ox, oy
    e = cfg.physics.restitution_wall
    for cell in entered:
        if state.grid[cell] != EMPTY or _occupied_by_player(state, cell) or _other_obstacle(state, o, cell):
            _reverse(o)
            return
        bomb = next((b for b in state.bombs if _cell(b, w) == cell), None)
        if bomb is None:
            continue
        vb = _along(bomb, axis)
        if (u - vb) * s <= EPS:
            return
        beyond = cell + step
        if (state.grid[beyond] != EMPTY or _occupied_by_player(state, beyond)
                or _other_obstacle(state, None, beyond) or any(_cell(b, w) == beyond for b in state.bombs)):
            _reverse(o)
            return
        _set_axis(bomb, axis, (1.0 + e) * u - e * vb)
        bomb.moved = True
        if events is not None:
            events.append({"type": "push", "x": cell % w, "y": cell // w, "bomb": bomb.id, "obstacle": o.id})
    _shift(o, axis, u)


def _occupied_by_player(state: GameState, cell: Cell) -> bool:
    return any(p.alive and _cell(p, state.width) == cell for p in state.players)


def _other_obstacle(state: GameState, me: Obstacle | None, cell: Cell) -> bool:
    return any(o is not me and cell in obstacle_cells(o, state.width) for o in state.obstacles)


def _reverse(o: Obstacle) -> None:
    o.vx, o.vy = -o.vx, -o.vy


def kick(bomb: Bomb, dx: int, dy: int, cfg: GameConfig) -> None:
    """Kopnięcie: bomba dostaje prędkość `kick_speed` w kierunku ruchu gracza."""
    speed = cfg.physics.kick_speed
    _set_velocity(bomb, dx * speed, dy * speed)
    bomb.moved = True


def update(state: GameState, cfg: GameConfig, events: list[Event] | None) -> None:
    """Krok fizyki: przeszkody, bomby w ruchu (według id), ślizgający się gracze."""
    if cfg.physics.moving_obstacles:
        for o in state.obstacles:
            _move_obstacle(state, o, cfg, events)
    for b in sorted(state.bombs, key=lambda b: b.id):
        if b.vx or b.vy:
            _advance(state, b, cfg, events)
    for p in state.players:
        if p.alive and (p.vx or p.vy):
            _advance(state, p, cfg, events)


def knock_targets(state: GameState, cfg: GameConfig, blasts: list) -> list[tuple[Cell, int, int, float]]:
    """Pola objęte falą uderzeniową: (pole, dx, dy, impuls J)."""
    w, h = state.width, state.height
    rng = cfg.physics.knock_range
    j0 = cfg.physics.knock_impulse
    blocking: set[Cell] = set()
    for o in state.obstacles:
        blocking.update(obstacle_cells(o, w))
    out: list[tuple[Cell, int, int, float]] = []
    for cx, cy, radius, open_dirs in blasts:
        for dx, dy in open_dirs:
            for d in range(radius + 1, rng + 1):
                x, y = cx + dx * d, cy + dy * d
                if not (0 <= x < w and 0 <= y < h):
                    break
                cell = y * w + x
                if state.grid[cell] != EMPTY or cell in blocking:
                    break
                out.append((cell, dx, dy, j0 * (1.0 - d / (rng + 1))))
    return out


def apply_knockback(state: GameState, cfg: GameConfig, blasts: list, events: list[Event] | None) -> None:
    """Odrzut: ciało w zasięgu fali dostaje prędkość dv = J / m; ruch zaczyna się w następnym ticku."""
    if not blasts:
        return
    w = state.width
    for cell, dx, dy, impulse in knock_targets(state, cfg, blasts):
        bodies: list[Body] = [b for b in state.bombs if _cell(b, w) == cell]
        bodies += [p for p in state.players if p.alive and _cell(p, w) == cell]
        for body in bodies:
            dv = impulse / _mass(body, cfg)
            _set_velocity(body, body.vx + dx * dv, body.vy + dy * dv)
            _mark(body, state)
            if events is not None:
                key = "player" if isinstance(body, Player) else "bomb"
                events.append({"type": "knock", "x": cell % w, "y": cell // w, key: body.id,
                               "vx": round(body.vx, 3), "vy": round(body.vy, 3)})


def slide_cells(start: Cell, knock: tuple[int, int, float], cfg: GameConfig, info: TickInfo,
                w: int) -> list[Cell]:
    """Pola gracza w kolejnych tickach po odrzucie z pola `start` (przybliżenie)."""
    dx, dy, impulse = knock
    mu = cfg.physics.friction
    speed = impulse / cfg.physics.mass_player
    step = dy * w + dx
    sx, sy = start % w, start // w

    def blocked(k: int) -> bool:
        cell = start + k * step
        return (info.grid[cell] != EMPTY or cell in info.occupied
                or (cell in info.players and cell != start))

    limit = 1
    while not blocked(limit):
        limit += 1
    contact = float(limit - 1)
    pos = 0.0
    cells: list[Cell] = []
    for _ in range(MAX_SLIDE_TICKS):
        if speed <= 0.0:
            break
        dist, speed = travel(speed, 1.0, mu)
        pos += dist
        if pos >= contact - EPS:
            pos, speed = contact, 0.0
        if speed < MIN_SPEED:
            speed = 0.0
        cells.append(int(sy + dy * pos + 0.5) * w + int(sx + dx * pos + 0.5))
    return cells
