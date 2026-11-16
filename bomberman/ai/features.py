"""Dyskretyzacja stanu gry do klucza tablicy Q i cechy taktyczne używane przy treningu."""

from __future__ import annotations

from collections import deque

from bomberman.ai.danger import (
    TickInfo,
    blast_cross,
    danger_ticks,
    default_horizon,
    escape_path,
    has_escape,
    in_danger,
    opponent_reach,
    predict,
    with_kick_threats,
)
from bomberman.config import GameConfig
from bomberman.engine import physics
from bomberman.engine.rules import after_action, bomb_at, legal_actions, obstacle_at
from bomberman.engine.state import (
    BOX,
    DIR4,
    DIRECTIONS,
    EMPTY,
    MOVES,
    WALL,
    Action,
    Cell,
    GameState,
    move_between,
)

_ACTION_CODE = {
    Action.UP: 1,
    Action.DOWN: 2,
    Action.LEFT: 3,
    Action.RIGHT: 4,
    Action.STAY: 5,
}

_OPPOSITE_MOVE = {
    Action.UP: Action.DOWN,
    Action.DOWN: Action.UP,
    Action.LEFT: Action.RIGHT,
    Action.RIGHT: Action.LEFT,
}


def _bucket_eta(eta: int | None) -> int:
    """0 = brak ognia, 1 = za 1-2 ticki, 2 = za 3-5, 3 = później."""
    if eta is None:
        return 0
    if eta <= 2:
        return 1
    if eta <= 5:
        return 2
    return 3


def _free(state: GameState, cell: Cell) -> bool:
    if state.grid[cell] != EMPTY or bomb_at(state, cell) is not None:
        return False
    return not (state.obstacles and obstacle_at(state, cell))


def bomb_has_escape(state: GameState, me: int, cfg: GameConfig) -> bool:
    """Czy po położeniu bomby teraz (przeciwnik stoi) istnieje ucieczka."""
    if Action.BOMB not in legal_actions(state, me, cfg):
        return False
    sim = after_action(state, me, Action.BOMB, cfg)
    if not sim.players[me].alive:
        return False
    horizon = default_horizon(cfg)
    tl = predict(sim, horizon, cfg, absent=me)
    opp = 1 - me
    if sim.players[opp].alive:
        reach = opponent_reach(sim, me, horizon, start=state.player_cell(opp))
        contested = {c: max(0, t - 1) for c, t in reach.items()}
        cautious = with_kick_threats(sim, me, tl, cfg, contested)
        if escape_path(sim, me, cautious, cfg, contested=contested) is not None:
            return True
    return escape_path(sim, me, tl, cfg) is not None


def bomb_is_useful(state: GameState, me: int, cfg: GameConfig) -> bool:
    """Czy bomba ma sens: jest ucieczka, a bomba niszczy skrzynie albo grozi przeciwnikowi."""
    return bomb_has_escape(state, me, cfg) and _bomb_threatens(state, me, cfg)


def _bomb_threatens(state: GameState, me: int, cfg: GameConfig) -> bool:
    here = state.player_cell(me)
    blast = blast_cross(state.grid, state.width, here, cfg.bomb_radius)
    if any(state.grid[c] == BOX for c in blast):
        return True
    if cfg.physics.kick and _can_setup_kick_attack(state, me, cfg):
        return True

    opp = 1 - me
    if not state.players[opp].alive:
        return False
    opp_cell = state.player_cell(opp)
    if opp_cell in blast:
        return True

    ax, ay = state.players[me].cell
    bx, by = state.players[opp].cell
    manh = abs(ax - bx) + abs(ay - by)
    limit = cfg.bomb_radius + 3
    if cfg.physics.knockback:
        limit = max(limit, cfg.physics.knock_range + 1)
    if manh > limit:
        return False

    sim = after_action(state, me, Action.BOMB, cfg)
    if not sim.players[opp].alive:
        return True
    tl = predict(sim, default_horizon(cfg), cfg, absent=me)
    if opp_cell in danger_ticks(tl) or not has_escape(sim, opp, cfg, timeline=tl):
        return True
    if cfg.physics.knockback and any(opp_cell in info.knocks for info in tl[1:]):
        return True
    return (ax == bx or ay == by) and manh <= cfg.bomb_radius + 2


def _can_setup_kick_attack(state: GameState, me: int, cfg: GameConfig) -> bool:
    """Czy bombę położoną teraz da się kopnąć (po cofnięciu o jedno pole) w przeciwnika albo skrzynię."""
    w = state.width
    grid = state.grid
    here = state.player_cell(me)
    opp = 1 - me
    opp_alive = state.players[opp].alive
    opp_cell = state.player_cell(opp) if opp_alive else -1

    for dx, dy in DIR4:
        d = dy * w + dx
        back, front = here - d, here + d
        if not _free(state, back) or back == opp_cell or not _free(state, front):
            continue
        c = here
        for k in range(1, 8):
            n = c + d
            if grid[n] == WALL or (state.obstacles and obstacle_at(state, n)):
                break
            if grid[n] == BOX:
                if k >= cfg.bomb_radius:
                    return True
                break
            c = n
            if opp_alive and k >= 2 and opp_cell in blast_cross(grid, w, c, cfg.bomb_radius):
                return True
    return False


def kick_score(state: GameState, me: int, action: Action, cfg: GameConfig) -> float:
    """Ocena kopnięcia sąsiedniej bomby ruchem `action`; > 0 oznacza kopnięcie bezpieczne i celowe."""
    if not cfg.physics.kick or action not in MOVES:
        return 0.0
    if action not in legal_actions(state, me, cfg):
        return 0.0
    w = state.width
    here = state.player_cell(me)
    dx, dy = DIRECTIONS[action]
    b = bomb_at(state, here + dy * w + dx)
    if b is None or b.vx or b.vy:
        return 0.0

    sim = after_action(state, me, action, cfg)
    if not sim.players[me].alive:
        return 0.0
    horizon = default_horizon(cfg)
    tl = predict(sim, horizon, cfg, absent=me)
    if escape_path(sim, me, tl, cfg) is None:
        return 0.0

    kb = next((x for x in sim.bombs if x.id == b.id), None)
    bx, by = int(b.x + 0.5), int(b.y + 0.5)
    if kb is not None and not (kb.vx or kb.vy) and (int(kb.x + 0.5), int(kb.y + 0.5)) == (bx, by):
        return 0.0

    passive_tl = predict(state, horizon, cfg, absent=me)

    score = 0.0
    opp = 1 - me
    if state.players[opp].alive:
        if not sim.players[opp].alive:
            return 100.0
        opp_cell = sim.player_cell(opp)
        if not has_escape(sim, opp, cfg, timeline=tl):
            score += 80.0
        elif in_danger(tl, opp_cell) and not in_danger(passive_tl, opp_cell):
            score += 45.0
        if cfg.physics.knockback and any(opp_cell in info.knocks for info in tl[1:]):
            score += 30.0
        ox, oy = state.players[opp].cell
        before_dist = abs(bx - ox) + abs(by - oy)
        if kb is not None:
            end_x, end_y = int(kb.x + 0.5), int(kb.y + 0.5)
        else:
            end_x, end_y = bx + dx, by + dy
        after_dist = abs(end_x - ox) + abs(end_y - oy)
        if after_dist < before_dist and (after_dist <= cfg.bomb_radius + 1 or end_x == ox or end_y == oy):
            score += 18.0

    if not in_danger(tl, sim.player_cell(me)):
        if b.owner != me or b.moved or escape_path(state, me, passive_tl, cfg) is None:
            score += 35.0

    boxes_passive = passive_tl[-1].grid.count(BOX)
    boxes_kicked = tl[-1].grid.count(BOX)
    if boxes_kicked < boxes_passive:
        score += 15.0 * (boxes_passive - boxes_kicked)
    return score


def kick_is_useful(state: GameState, me: int, action: Action, cfg: GameConfig) -> bool:
    return kick_score(state, me, action, cfg) > 0.0


def best_kick_action(state: GameState, me: int, cfg: GameConfig) -> Action | None:
    """Ruch kopiący sąsiednią bombę z najwyższą oceną albo None, gdy żadne kopnięcie się nie opłaca."""
    if not cfg.physics.kick or not state.bombs or not state.players[me].alive:
        return None
    best_a: Action | None = None
    best_s = 0.0
    for a in MOVES:
        s = kick_score(state, me, a, cfg)
        if s > best_s:
            best_s, best_a = s, a
    return best_a


def best_escape_action(state: GameState, me: int, cfg: GameConfig,
                       timeline: list[TickInfo] | None = None) -> Action | None:
    """Pierwszy ruch ucieczki albo None, gdy pole jest bezpieczne."""
    if not state.players[me].alive:
        return None
    horizon = default_horizon(cfg)
    if timeline is None:
        if not state.bombs and not state.flames:
            return None
        timeline = predict(state, horizon, cfg, absent=me)
    here = state.player_cell(me)
    reach = opponent_reach(state, me, horizon)
    cautious = with_kick_threats(state, me, timeline, cfg, reach)

    if cfg.physics.kick and bomb_at(state, here) is not None:
        legal = legal_actions(state, me, cfg)
        best_act: Action | None = None
        best_score = 0.0
        for a in MOVES:
            if a not in legal:
                continue
            sim = after_action(state, me, a, cfg)
            if not sim.players[me].alive:
                continue
            score = kick_score(sim, me, _OPPOSITE_MOVE[a], cfg)
            if score > best_score:
                best_score, best_act = score, a
        if best_act is not None:
            return best_act

    in_knock = cfg.physics.knockback and any(here in info.knocks for info in cautious[1:])
    if not in_danger(cautious, here) and not in_danger(timeline, here) and not in_knock:
        return None

    attempts = [(cautious, reach), (cautious, None)] if cautious is not timeline else []
    attempts += [(timeline, reach), (timeline, None)]
    path = None
    for tl, contested in attempts:
        path = escape_path(state, me, tl, cfg, contested=contested)
        if path is not None:
            break
    if path is None:
        path = escape_path(state, me, timeline, cfg, best_effort=True)
    if not path or len(path) < 2:
        return Action.STAY
    return move_between(path[0], path[1], state.width)


def dir_safety_mask(state: GameState, me: int, cfg: GameConfig,
                    timeline: list[TickInfo] | None = None) -> str:
    """Dla każdego kierunku: '0' zły ruch, '1' zagrożony z ucieczką, '2' bezpieczny."""
    if not state.players[me].alive:
        return "0000"
    legal = set(legal_actions(state, me, cfg))
    w = state.width
    here = state.player_cell(me)
    horizon = default_horizon(cfg)
    bombs_out = bool(state.bombs or state.flames or (
        cfg.physics.enabled and (state.obstacles or cfg.physics.knockback)))
    if bombs_out and timeline is None:
        timeline = predict(state, horizon, cfg, absent=me)
    cautious = timeline
    if timeline is not None and cfg.physics.kick and state.bombs:
        reach = opponent_reach(state, me, horizon)
        cautious = with_kick_threats(state, me, timeline, cfg, reach)

    fire_next = cautious[1].flames if (cautious and len(cautious) > 1) else set()
    chars: list[str] = []
    for a in MOVES:
        if a not in legal:
            chars.append("0")
            continue
        dx, dy = DIRECTIONS[a]
        n = here + dy * w + dx
        if bomb_at(state, n) is not None:
            if not cfg.physics.kick:
                chars.append("0")
            elif kick_score(state, me, a, cfg) > 0.0:
                chars.append("2")
            else:
                sim = after_action(state, me, a, cfg)
                if not sim.players[me].alive:
                    chars.append("0")
                    continue
                sim_tl = predict(sim, horizon, cfg, absent=me)
                if escape_path(sim, me, sim_tl, cfg) is None:
                    chars.append("0")
                elif in_danger(sim_tl, sim.player_cell(me)):
                    chars.append("1")
                else:
                    chars.append("2")
            continue

        if not bombs_out or cautious is None:
            chars.append("2")
            continue
        if n in fire_next:
            chars.append("0")
            continue
        esc = escape_path(state, me, cautious, cfg, start=n, start_t=1)
        if esc is None and cautious is not timeline and timeline is not None:
            esc = escape_path(state, me, timeline, cfg, start=n, start_t=1)
        if esc is None:
            chars.append("0")
        elif in_danger(cautious, n) or (cfg.physics.knockback and any(n in info.knocks for info in cautious[1:])):
            chars.append("1")
        else:
            chars.append("2")
    return "".join(chars)


def attack_cells(state: GameState, target: Cell, radius: int) -> set[Cell]:
    """Pola, z których bomba dosięgnie celu (ta sama linia, zasięg, brak przeszkód po drodze)."""
    w = state.width
    cells: set[Cell] = set()
    for delta in (-w, w, -1, 1):
        c = target
        for _ in range(radius):
            c += delta
            if state.grid[c] != EMPTY:
                break
            cells.add(c)
    return cells


def box_neighbours(state: GameState) -> set[Cell]:
    w = state.width
    grid = state.grid
    result: set[Cell] = set()
    for c, v in enumerate(grid):
        if v == BOX:
            for n in (c - w, c + w, c - 1, c + 1):
                if grid[n] == EMPTY:
                    result.add(n)
    return result


def best_nav_info(state: GameState, me: int, cfg: GameConfig, timeline: list[TickInfo] | None,
                  kick_act: Action | None, can_bomb_now: bool) -> tuple[Action | None, int]:
    """Pierwszy krok i długość drogi do pozycji ataku, skrzyni albo kopnięcia."""
    if not state.players[me].alive:
        return None, 99
    if kick_act is not None:
        return kick_act, 1

    w = state.width
    grid = state.grid
    here = state.player_cell(me)
    opp = 1 - me
    opp_alive = state.players[opp].alive
    opp_cell = state.player_cell(opp) if opp_alive else -1

    if (state.bombs or state.flames) and timeline is None:
        timeline = predict(state, default_horizon(cfg), cfg, absent=me)

    attack_ring = cfg.physics.knock_range if cfg.physics.knockback else cfg.bomb_radius
    attack_targets = attack_cells(state, opp_cell, attack_ring) if opp_alive else set()
    if cfg.physics.kick and opp_alive:
        # Pola w korytarzach prowadzących do przeciwnika, z których można postawić bombę i ją kopnąć.
        for delta in (-w, w, -1, 1):
            c = opp_cell
            for k in range(1, 7):
                c += delta
                if grid[c] != EMPTY:
                    break
                if k > attack_ring and grid[c + delta] == EMPTY and grid[c - delta] == EMPTY:
                    attack_targets.add(c)
        # Pola, z których można od razu kopnąć leżącą bombę w stronę przeciwnika.
        ox, oy = state.players[opp].cell
        for b in state.bombs:
            if b.vx or b.vy:
                continue
            bx, by = int(b.x + 0.5), int(b.y + 0.5)
            b_cell = by * w + bx
            for dx, dy in DIR4:
                if (ox - bx) * dx + (oy - by) * dy > 0:
                    launch = b_cell - dy * w - dx
                    if grid[launch] == EMPTY and grid[b_cell + dy * w + dx] == EMPTY:
                        attack_targets.add(launch)
    box_targets = box_neighbours(state)
    opp_adj = {opp_cell - w, opp_cell + w, opp_cell - 1, opp_cell + 1} if opp_alive else set()

    blocked = set(danger_ticks(timeline)) if timeline is not None else set()
    blocked.update(int(b.y + 0.5) * w + int(b.x + 0.5) for b in state.bombs)
    for o in state.obstacles:
        blocked.update(physics.obstacle_cells(o, w))
    if opp_alive:
        blocked.add(opp_cell)

    dist: dict[Cell, int] = {here: 0}
    first_step: dict[Cell, Action] = {}
    queue = deque([here])
    while queue:
        c = queue.popleft()
        d = dist[c]
        for a in MOVES:
            dx, dy = DIRECTIONS[a]
            n = c + dy * w + dx
            if n in dist or grid[n] != EMPTY or n in blocked:
                continue
            dist[n] = d + 1
            first_step[n] = first_step[c] if c != here else a
            queue.append(n)

    tx, ty = (opp_cell % w, opp_cell // w) if opp_alive else (4, 4)
    for targets in (attack_targets, box_targets, opp_adj):
        reachable = [c for c in targets if c in dist and (c != here or can_bomb_now)]
        if reachable:
            best = min(reachable, key=lambda c: (dist[c], abs(c % w - tx) + abs(c // w - ty)))
            if dist[best] == 0:
                return None, 0
            return first_step[best], dist[best]
    return None, 99


def boxes_bucket(state: GameState) -> int:
    """0 = mało skrzyń (otwarta mapa), 1 = średnio, 2 = dużo."""
    n = state.grid.count(BOX)
    if n <= 4:
        return 0
    if n <= 12:
        return 1
    return 2


def _dist_bucket(d: int) -> int:
    if d <= 0:
        return 0
    if d <= 2:
        return 1
    if d <= 5:
        return 2
    return 3


def _kick_threat(state: GameState, me: int, cfg: GameConfig, kick_act: Action | None) -> int:
    """0 brak, 1 bomba obok (do kopnięcia), 2 bomba leci po mojej linii, 3 gotowe kopnięcie ofensywne."""
    if not cfg.physics.kick or not state.bombs:
        return 0
    if kick_act is not None:
        return 3
    mx, my = state.players[me].cell
    level = 0
    for b in state.bombs:
        bx, by = int(b.x + 0.5), int(b.y + 0.5)
        if b.vx or b.vy:
            if bx == mx or by == my:
                return 2
        elif abs(bx - mx) + abs(by - my) == 1:
            level = 1
    return level


def _knock_near(state: GameState, me: int, cfg: GameConfig, timeline: list[TickInfo] | None) -> int:
    """0 brak, 1 moje pole w strefie odrzutu, 2 pole przeciwnika w strefie odrzutu."""
    if not cfg.physics.knockback or not timeline:
        return 0
    here = state.player_cell(me)
    if any(here in info.knocks for info in timeline[1:]):
        return 1
    opp = 1 - me
    if state.players[opp].alive:
        opp_cell = state.player_cell(opp)
        if any(opp_cell in info.knocks for info in timeline[1:]):
            return 2
    return 0


def _obstacle_adj(state: GameState, me: int, cfg: GameConfig, timeline: list[TickInfo] | None) -> int:
    """0 brak, 1 przeszkoda obok, 2 przeszkoda wjedzie na moje pole w następnym ticku."""
    if not cfg.physics.moving_obstacles or not state.obstacles:
        return 0
    w = state.width
    here = state.player_cell(me)
    occupied: set[Cell] = set()
    moving = False
    for o in state.obstacles:
        occupied.update(physics.obstacle_cells(o, w))
        moving = moving or bool(o.vx or o.vy)
    if moving and timeline and len(timeline) > 1 and here in timeline[1].occupied:
        return 2
    if here in occupied or occupied & {here - w, here + w, here - 1, here + 1}:
        return 1
    return 0


def encode_state(state: GameState, me: int, cfg: GameConfig) -> str:
    """Klucz tablicy Q: 16 pól oddzielonych `|`."""
    if not state.players[me].alive:
        return "dead"
    opp = 1 - me
    here = state.player_cell(me)
    horizon = default_horizon(cfg)

    eta = None
    can_escape = 1
    timeline = None
    cautious = None
    if state.bombs or state.flames or (cfg.physics.enabled and (state.obstacles or cfg.physics.knockback)):
        timeline = predict(state, horizon, cfg, absent=me)
        cautious = timeline
        if cfg.physics.kick and state.bombs:
            cautious = with_kick_threats(state, me, timeline, cfg, opponent_reach(state, me, horizon))
        eta = danger_ticks(cautious).get(here)
        if state.bombs or state.flames:
            can_escape = int(escape_path(state, me, cautious, cfg) is not None)
    fire = _bucket_eta(eta)

    dir_mask = dir_safety_mask(state, me, cfg, timeline=timeline)
    kick_act = best_kick_action(state, me, cfg)
    knock = _knock_near(state, me, cfg, cautious) if cfg.physics.enabled else 0

    bomb_ready = int(state.players[me].bombs_used < cfg.max_bombs)
    safe_bomb = int(fire == 0 and bomb_ready and bomb_has_escape(state, me, cfg))
    useful = int(safe_bomb and _bomb_threatens(state, me, cfg))

    if fire > 0 or knock == 1:
        esc_dir = _ACTION_CODE.get(best_escape_action(state, me, cfg, timeline=timeline), 5)
        nav_dir = _ACTION_CODE.get(kick_act, 0)
        dist_b = 1 if kick_act is not None else 0
        open_map = 0
    else:
        esc_dir = 0
        nav_act, nav_dist = best_nav_info(state, me, cfg, cautious, kick_act, bool(useful))
        nav_dir = _ACTION_CODE.get(nav_act, 0)
        dist_b = _dist_bucket(nav_dist)
        open_map = boxes_bucket(state)

    opp_alive = int(state.players[opp].alive)
    phys_on = int(cfg.physics.kick or cfg.physics.knockback)
    own_bomb = 0
    for b in state.bombs:
        if b.owner == me:
            own_bomb = 1 if b.timer <= 2 else 2
            break

    if cfg.physics.enabled:
        kick = _kick_threat(state, me, cfg, kick_act)
        obst = _obstacle_adj(state, me, cfg, timeline)
    else:
        kick = knock = obst = 0

    return (
        f"{fire}|{can_escape}|{esc_dir}|{nav_dir}|{dir_mask}|"
        f"{opp_alive}|{bomb_ready}|{phys_on}|{own_bomb}|{safe_bomb}|"
        f"{dist_b}|{useful}|{open_map}|{kick}|{knock}|{obst}"
    )
