"""Zasady gry: legalne akcje i step(), czyli jeden tick (docs/zasady.md)."""

from __future__ import annotations

from collections.abc import Sequence

from bomberman.config import GameConfig
from bomberman.engine import physics
from bomberman.engine.state import (
    BOX,
    DIR4,
    DIRECTIONS,
    EMPTY,
    MOVES,
    PHYSICS_BIT,
    WALL,
    Action,
    Bomb,
    Cell,
    Event,
    GameState,
)

# ile ticków po odrzucie śmierć liczy się jako fizyczna
KNOCK_MEMORY = 6


def bomb_at(state: GameState, cell: Cell) -> Bomb | None:
    w = state.width
    for b in state.bombs:
        if int(b.y + 0.5) * w + int(b.x + 0.5) == cell:
            return b
    return None


def obstacle_at(state: GameState, cell: Cell) -> bool:
    w = state.width
    return any(cell in physics.obstacle_cells(o, w) for o in state.obstacles)


def legal_actions(state: GameState, pid: int, cfg: GameConfig) -> list[Action]:
    p = state.players[pid]
    if not p.alive or p.vx or p.vy:
        return [Action.STAY]
    w = state.width
    grid = state.grid
    here = int(p.y + 0.5) * w + int(p.x + 0.5)
    other = state.players[1 - pid]
    other_cell = state.player_cell(other.id) if other.alive else -1
    bombs: dict[Cell, Bomb] = {}
    for b in state.bombs:
        bombs.setdefault(int(b.y + 0.5) * w + int(b.x + 0.5), b)
    blocked: set[Cell] = set()
    for o in state.obstacles:
        blocked.update(physics.obstacle_cells(o, w))
    kick = cfg.physics.kick
    result = [Action.STAY]
    for a in MOVES:
        dx, dy = DIRECTIONS[a]
        t = here + dy * w + dx
        if grid[t] != EMPTY or t == other_cell or t in blocked:
            continue
        b = bombs.get(t)
        if b is not None and (not kick or b.vx or b.vy):
            continue
        result.append(a)
    if p.bombs_used < cfg.max_bombs and here not in bombs:
        result.append(Action.BOMB)
    return result


def step(state: GameState, actions: Sequence[Action], cfg: GameConfig, record: bool = True) -> list[Event]:
    """Przesuwa stan o jeden tick (modyfikuje `state`). Zwraca zdarzenia, gdy `record=True`."""
    events: list[Event] | None = [] if record else None
    w = state.width
    grid = state.grid
    players = state.players
    phys = cfg.physics

    flames = state.flames
    if flames:
        info = state.flame_info
        for cell in list(flames):
            left = flames[cell] - 1
            if left <= 0:
                del flames[cell]
                info.pop(cell, None)
            else:
                flames[cell] = left

    intents = [Action.STAY, Action.STAY]
    for p in players:
        if p.alive and not (p.vx or p.vy):
            intents[p.id] = actions[p.id]

    placed: set[int] = set()
    for p in players:
        if intents[p.id] != Action.BOMB:
            continue
        cx, cy = int(p.x + 0.5), int(p.y + 0.5)
        if p.bombs_used < cfg.max_bombs and bomb_at(state, cy * w + cx) is None:
            b = Bomb(state.next_bomb_id, p.id, float(cx), float(cy), cfg.bomb_timer, cfg.bomb_radius)
            state.next_bomb_id += 1
            state.bombs.append(b)
            p.bombs_used += 1
            placed.add(b.id)
            if events is not None:
                events.append({"type": "bomb", "x": cx, "y": cy, "player": p.id, "bomb": b.id})

    targets: list[tuple[int, int] | None] = [None, None]
    for p in players:
        a = intents[p.id]
        if a == Action.STAY or a == Action.BOMB:
            continue
        dx, dy = DIRECTIONS[a]
        tx, ty = int(p.x + 0.5) + dx, int(p.y + 0.5) + dy
        t = ty * w + tx
        if grid[t] != EMPTY:
            continue
        if state.obstacles and obstacle_at(state, t):
            continue
        other = players[1 - p.id]
        if other.alive and state.player_cell(other.id) == t:
            continue
        b = bomb_at(state, t)
        if b is not None:
            if phys.kick and not b.moving:
                physics.kick(b, dx, dy, cfg)
                if events is not None:
                    events.append({"type": "kick", "x": tx, "y": ty, "player": p.id, "bomb": b.id})
            continue
        targets[p.id] = (tx, ty)
    if targets[0] is not None and targets[0] == targets[1]:
        targets = [None, None]
    for p in players:
        t2 = targets[p.id]
        if t2 is not None:
            p.x, p.y = float(t2[0]), float(t2[1])

    if phys.enabled and (state.obstacles or any(b.vx or b.vy for b in state.bombs)
                         or any(p.alive and (p.vx or p.vy) for p in players)):
        physics.update(state, cfg, events)

    boxes: set[Cell] = set()
    if state.bombs:
        for b in state.bombs:
            if b.id not in placed:
                b.timer -= 1
        boxes = _explode(state, cfg, events)

    if flames:
        for p in players:
            if not p.alive:
                continue
            c = state.player_cell(p.id)
            if c in flames:
                p.alive = False
                if events is not None:
                    bits = state.flame_info.get(c, 0)
                    events.append({
                        "type": "death", "player": p.id, "x": c % w, "y": c // w,
                        "by_self": bool(bits & (1 << p.id)),
                        "by_enemy": bool(bits & (1 << (1 - p.id))),
                        "physics": bool(bits & PHYSICS_BIT) or state.tick - p.knocked_tick <= KNOCK_MEMORY,
                    })

    for c in boxes:
        grid[c] = EMPTY
        if events is not None:
            events.append({"type": "box", "x": c % w, "y": c // w})

    state.tick += 1
    if not state.done:
        a0, a1 = players[0].alive, players[1].alive
        if not (a0 and a1):
            state.done = True
            state.winner = 0 if a0 else (1 if a1 else -1)
        elif state.tick >= cfg.max_ticks:
            state.done = True
            state.winner = -1
    return events if events is not None else []


def after_action(state: GameState, pid: int, action: Action, cfg: GameConfig,
                 other: Action = Action.STAY) -> GameState:
    """Kopia stanu po jednym ticku z akcjami obu graczy."""
    sim = state.clone()
    actions = [other, other]
    actions[pid] = action
    step(sim, actions, cfg, record=False)
    return sim


def _explode(state: GameState, cfg: GameConfig, events: list[Event] | None) -> set[Cell]:
    """Wybuchy bomb z reakcjami łańcuchowymi. Zwraca trafione skrzynie."""
    w = state.width
    grid = state.grid
    flames = state.flames
    by_cell: dict[Cell, list[Bomb]] = {}
    for b in state.bombs:
        by_cell.setdefault(int(b.y + 0.5) * w + int(b.x + 0.5), []).append(b)
    queue = [b for b in state.bombs
             if b.timer <= 0 or (flames and int(b.y + 0.5) * w + int(b.x + 0.5) in flames)]
    if not queue:
        return set()

    blocking: set[Cell] = set()
    for o in state.obstacles:
        blocking.update(physics.obstacle_cells(o, w))

    exploded: set[int] = set()
    new_flames: dict[Cell, int] = {}
    boxes: set[Cell] = set()
    blasts: list[tuple[int, int, int, list[tuple[int, int]]]] = []
    while queue:
        b = queue.pop()
        if b.id in exploded:
            continue
        exploded.add(b.id)
        cx, cy = int(b.x + 0.5), int(b.y + 0.5)
        center = cy * w + cx
        bits = (1 << b.owner) | (PHYSICS_BIT if b.moved else 0)
        new_flames[center] = new_flames.get(center, 0) | bits
        for other in by_cell.get(center, ()):
            if other.id not in exploded:
                queue.append(other)
        open_dirs: list[tuple[int, int]] = []
        for dx, dy in DIR4:
            delta = dy * w + dx
            cell = center
            full = True
            for _ in range(b.radius):
                cell += delta
                v = grid[cell]
                if v == WALL or cell in blocking:
                    full = False
                    break
                new_flames[cell] = new_flames.get(cell, 0) | bits
                if v == BOX:
                    boxes.add(cell)
                    full = False
                    break
                hit = by_cell.get(cell)
                if hit:
                    for other in hit:
                        if other.id not in exploded:
                            queue.append(other)
                    full = False
                    break
            if full:
                open_dirs.append((dx, dy))
        blasts.append((cx, cy, b.radius, open_dirs))
        if events is not None:
            events.append({"type": "explosion", "x": cx, "y": cy, "player": b.owner, "bomb": b.id,
                           "radius": b.radius, "open": [list(d) for d in open_dirs], "moved": b.moved})

    players = state.players
    remaining = []
    for b in state.bombs:
        if b.id in exploded:
            players[b.owner].bombs_used -= 1
        else:
            remaining.append(b)
    state.bombs = remaining

    duration = cfg.flame_duration
    info = state.flame_info
    for cell, bits in new_flames.items():
        if flames.get(cell, 0) < duration:
            flames[cell] = duration
        info[cell] = info.get(cell, 0) | bits

    if cfg.physics.knockback:
        physics.apply_knockback(state, cfg, blasts, events)
    return boxes
