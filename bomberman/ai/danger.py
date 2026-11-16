"""Przewidywanie zagrożeń."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from bomberman.config import GameConfig
from bomberman.engine import physics
from bomberman.engine.rules import step
from bomberman.engine.state import BOX, DIR4, EMPTY, WALL, Action, Cell, GameState

_STAY2 = (Action.STAY, Action.STAY)


@dataclass(slots=True)
class TickInfo:
    grid: list[int]
    flames: set[Cell]
    occupied: set[Cell]                          # bomby i ruchome przeszkody na końcu ticku
    players: tuple[Cell, Cell]                   # pola graczy (-1, gdy gracz nie żyje)
    knocks: dict[Cell, tuple[int, int, float]]   # pole -> (dx, dy, J): odrzut w tym ticku


def _snapshot(sim: GameState, knocks: dict[Cell, tuple[int, int, float]],
              extra_flames: set[Cell] | None = None) -> TickInfo:
    w = sim.width
    occupied = {int(b.y + 0.5) * w + int(b.x + 0.5) for b in sim.bombs}
    for o in sim.obstacles:
        occupied.update(physics.obstacle_cells(o, w))
    players = (sim.player_cell(0) if sim.players[0].alive else -1,
               sim.player_cell(1) if sim.players[1].alive else -1)
    flames = set(sim.flames)
    if extra_flames:
        flames |= extra_flames
    return TickInfo(sim.grid[:], flames, occupied, players, knocks)


def blast_cross(grid: list[int], w: int, center: Cell, radius: int) -> set[Cell]:
    """Krzyż wybuchu z pola `center`."""
    cells = {center}
    for delta in (-w, w, -1, 1):
        c = center
        for _ in range(radius):
            c += delta
            if grid[c] == WALL:
                break
            cells.add(c)
            if grid[c] == BOX:
                break
    return cells


def predict(state: GameState, horizon: int, cfg: GameConfig, absent: int | None = None) -> list[TickInfo]:
    """Stany planszy w kolejnych tickach, gdy nikt nic nie robi."""
    sim = state.clone()
    if absent is not None:
        sim.players[absent].alive = False
    timeline = [_snapshot(sim, {})]
    knockback = cfg.physics.knockback
    unshield = bool(sim.obstacles)
    w = sim.width
    lingering: list[tuple[int, set[Cell]]] = []
    for t in range(1, horizon + 1):
        if not sim.bombs and not sim.flames:
            break
        grid_before = sim.grid[:] if unshield else sim.grid
        events = step(sim, _STAY2, cfg, record=knockback or unshield)
        explosions = [e for e in events if e["type"] == "explosion"]
        knocks: dict[Cell, tuple[int, int, float]] = {}
        if knockback and explosions:
            blasts = [(e["x"], e["y"], e["radius"], [tuple(d) for d in e["open"]]) for e in explosions]
            for cell, dx, dy, impulse in physics.knock_targets(sim, cfg, blasts):
                if cell not in knocks or impulse > knocks[cell][2]:
                    knocks[cell] = (dx, dy, impulse)
        extra: set[Cell] = set()
        if unshield:
            for e in explosions:
                cross = blast_cross(grid_before, w, e["y"] * w + e["x"], e["radius"])
                lingering.append((t + cfg.flame_duration - 1, cross))
            lingering = [(until, cells) for until, cells in lingering if until >= t]
            for _, cells in lingering:
                extra |= cells
        timeline.append(_snapshot(sim, knocks, extra))
    return timeline


def with_kick_threats(state: GameState, me: int, timeline: list[TickInfo], cfg: GameConfig,
                      reach: dict[Cell, int]) -> list[TickInfo]:
    """Oś czasu uzupełniona o bomby, które przeciwnik może kopnąć."""
    if not cfg.physics.kick or not state.bombs or not reach:
        return timeline
    w = state.width
    horizon = len(timeline) - 1
    fire: list[set[Cell]] = [set() for _ in timeline]
    taken: list[set[Cell]] = [set() for _ in timeline]
    for b in state.bombs:
        if b.vx or b.vy:
            continue
        cell = int(b.y + 0.5) * w + int(b.x + 0.5)
        for dx, dy in DIR4:
            d = reach.get(cell - dy * w - dx)
            if d is None or d >= b.timer or d >= horizon:
                continue
            base = state.clone()
            for _ in range(d):
                step(base, _STAY2, cfg, record=False)
            for absent in (False, True):
                sim = base.clone()
                target = next((x for x in sim.bombs if x.id == b.id), None)
                if target is None or target.vx or target.vy:
                    break
                if absent:
                    sim.players[me].alive = False
                physics.kick(target, dx, dy, cfg)
                sub = predict(sim, horizon - d, cfg)
                for i in range(1, len(sub)):
                    fire[d + i] |= sub[i].flames
                    taken[d + i] |= sub[i].occupied
    if not any(fire) and not any(taken):
        return timeline
    return [replace(info, flames=info.flames | fire[t], occupied=info.occupied | taken[t])
            if fire[t] or taken[t] else info for t, info in enumerate(timeline)]


def opponent_reach(state: GameState, me: int, horizon: int,
                   start: Cell | None = None) -> dict[Cell, int]:
    """Najwcześniejszy tick, w którym przeciwnik może stanąć na danym polu."""
    opp = state.players[1 - me]
    if start is None:
        if not opp.alive:
            return {}
        start = state.player_cell(opp.id)
    w = state.width
    grid = state.grid
    blocked = {int(b.y + 0.5) * w + int(b.x + 0.5) for b in state.bombs}
    for o in state.obstacles:
        blocked.update(physics.obstacle_cells(o, w))
    blocked.add(state.player_cell(me))
    dist = {start: 0}
    queue = deque([start])
    while queue:
        c = queue.popleft()
        d = dist[c] + 1
        if d > horizon:
            continue
        for n in (c - w, c + w, c - 1, c + 1):
            if n in dist or grid[n] != EMPTY or n in blocked:
                continue
            dist[n] = d
            queue.append(n)
    return dist


def danger_ticks(timeline: list[TickInfo]) -> dict[Cell, int]:
    """Pole -> pierwszy tick (od teraz), w którym pojawi się w nim ogień."""
    first: dict[Cell, int] = {}
    for t in range(1, len(timeline)):
        for c in timeline[t].flames:
            if c not in first:
                first[c] = t
    return first


def in_danger(timeline: list[TickInfo], cell: Cell) -> bool:
    return any(cell in info.flames for info in timeline[1:])


def escape_path(state: GameState, me: int, timeline: list[TickInfo], cfg: GameConfig | None = None,
                start: Cell | None = None, start_t: int = 0,
                best_effort: bool = False, contested: dict[Cell, int] | None = None,
                collect: set[Cell] | None = None,
                stats: dict | None = None) -> list[Cell] | None:
    """Najkrótsza droga do bezpiecznego pola (pole na tick) albo None."""
    if not state.players[me].alive:
        if stats is not None:
            stats["nodes"] = 0
        return None
    w = state.width
    last = len(timeline) - 1
    src = state.player_cell(me) if start is None else start
    other = 1 - me

    flames_at = [info.flames for info in timeline]

    last_danger: dict[Cell, int] = {}
    for t in range(1, last + 1):
        for c in flames_at[t]:
            last_danger[c] = t
        for c in timeline[t].knocks:
            if last_danger.get(c, 0) < t:
                last_danger[c] = t

    first_goal = None
    if start_t >= last or start_t >= last_danger.get(src, 0):
        if collect is None or start_t >= last:
            if collect is not None:
                collect.add(src)
            if stats is not None:
                stats["nodes"] = 1
            return [src]
        collect.add(src)
        first_goal = (src, start_t)

    knock_cfg = cfg if cfg is not None and cfg.physics.knockback else None
    parent: dict[tuple[Cell, int], tuple[tuple[Cell, int], list[Cell]] | None] = {(src, start_t): None}
    queue = deque([(src, start_t)])
    deepest = (src, start_t)

    def _finish(path: list[Cell] | None) -> list[Cell] | None:
        if stats is not None:
            stats["nodes"] = len(parent)
        return path

    while queue:
        c, t = queue.popleft()
        if t >= last:
            continue
        cur = timeline[t]
        nxt = timeline[t + 1]
        fire = flames_at[t + 1]
        blocked_player = cur.players[other]
        for n in (c, c - w, c + w, c - 1, c + 1):
            if n != c:
                if cur.grid[n] != EMPTY or n in cur.occupied or n == blocked_player:
                    continue
                if contested is not None and contested.get(n, last + 1) <= t + 1:
                    continue
            if n in fire:
                continue
            segment = [n]
            node = (n, t + 1)
            if knock_cfg is not None and n in nxt.knocks:
                slide = physics.slide_cells(n, nxt.knocks[n], knock_cfg, nxt, w)
                tt = t + 1
                burned = False
                for cell in slide:
                    tt += 1
                    if tt <= last and cell in flames_at[tt]:
                        burned = True
                        break
                if burned:
                    continue
                if slide:
                    segment += slide
                    node = (slide[-1], min(tt, last))
            if node in parent:
                continue
            parent[node] = ((c, t), segment)
            if node[1] >= last or node[1] >= last_danger.get(node[0], 0):
                if collect is None:
                    return _finish(_reconstruct(parent, node, src))
                collect.add(node[0])
                if first_goal is None:
                    first_goal = node
            if node[1] > deepest[1]:
                deepest = node
            queue.append(node)
    if first_goal is not None:
        return _finish(_reconstruct(parent, first_goal, src))
    if best_effort:
        return _finish(_reconstruct(parent, deepest, src))
    return _finish(None)


def _reconstruct(parent: dict, node: tuple[Cell, int], src: Cell) -> list[Cell]:
    segments = []
    while parent[node] is not None:
        prev, segment = parent[node]
        segments.append(segment)
        node = prev
    path = [src]
    for segment in reversed(segments):
        path.extend(segment)
    return path


def has_escape(state: GameState, me: int, cfg: GameConfig, horizon: int | None = None,
               timeline: list[TickInfo] | None = None) -> bool:
    """Czy gracz `me` może przeżyć wszystkie przewidywane wybuchy (używane przez metryki)."""
    if not state.players[me].alive:
        return False
    if timeline is None:
        if not state.bombs and not state.flames:
            return True
        timeline = predict(state, horizon or default_horizon(cfg), cfg)
    return escape_path(state, me, timeline, cfg) is not None


def default_horizon(cfg: GameConfig) -> int:
    return cfg.bomb_timer + cfg.flame_duration + 4
