"""Bot Planner: bezpieczne ścieżki z uwzględnieniem czasu wybuchów."""

from __future__ import annotations

from collections import deque

from bomberman.ai.base import BaseBot
from bomberman.ai.danger import (
    TickInfo,
    blast_cross,
    default_horizon,
    escape_path,
    in_danger,
    opponent_reach,
    predict,
    with_kick_threats,
)
from bomberman.ai.features import attack_cells, box_neighbours
from bomberman.ai.telemetry import set_debug
from bomberman.config import GameConfig
from bomberman.engine import physics
from bomberman.engine.rules import after_action, bomb_at, legal_actions
from bomberman.engine.state import BOX, DIRECTIONS, EMPTY, MOVES, Action, Cell, GameState, move_between

TRAP_SCORE = 100.0
THREAT_SCORE = 10.0
AREA_SCORE = 20.0
AREA_NORM = 20
MIN_ATTACK_SCORE = 1.0


class PlannerBot(BaseBot):
    name = "planner"

    def __init__(self, cfg: GameConfig, seed: int = 0, horizon: int | None = None) -> None:
        super().__init__(cfg, seed)
        self.horizon = horizon or default_horizon(cfg)

    def act(self, state: GameState, me: int) -> Action:
        self._ops = 0
        p = state.players[me]
        if not p.alive or p.stunned:
            set_debug(self, family="search", ops=0, detail="stunned", mode="stunned",
                      rationale="ogłuszony / martwy")
            return Action.STAY
        legal = legal_actions(state, me, self.cfg)
        timeline = predict(state, self.horizon, self.cfg, absent=me)
        here = state.player_cell(me)
        reach = opponent_reach(state, me, self.horizon)
        cautious = with_kick_threats(state, me, timeline, self.cfg, reach)

        if in_danger(timeline, here):
            attempts = [(cautious, reach), (cautious, None)] if cautious is not timeline else []
            attempts += [(timeline, reach), (timeline, None)]
            for tl, contested in attempts:
                path = self._escape(state, me, tl, contested=contested)
                if path is not None:
                    return self._follow(state, path, "escape", legal)
            path = self._escape(state, me, timeline, best_effort=True)
            return self._follow(state, path or [here], "survive", legal)

        attack = self._best_attack(state, me, legal)
        if attack is not None:
            return attack
        if cautious is not timeline:
            action = self._approach(state, me, cautious, legal)
            if self.debug.get("mode") != "wait":
                return action
        return self._approach(state, me, timeline, legal)

    def _escape(self, state: GameState, me: int, timeline: list[TickInfo], start: Cell | None = None,
                start_t: int = 0, contested: dict[Cell, int] | None = None,
                best_effort: bool = False) -> list[Cell] | None:
        bfs_stats: dict = {}
        path = escape_path(state, me, timeline, self.cfg, start=start, start_t=start_t,
                           contested=contested, best_effort=best_effort, stats=bfs_stats)
        self._ops += int(bfs_stats.get("nodes", 0))
        return path

    def _follow(self, state: GameState, path: list[Cell], mode: str, legal: list[Action]) -> Action:
        w = state.width
        plan = [[c % w, c // w] for c in path]
        set_debug(self, family="search", ops=self._ops, detail=f"bfs_nodes={self._ops}",
                  mode=mode, plan=plan, rationale=f"Planner: {mode}, ścieżka {len(path)} pól")
        if len(path) < 2 or path[1] == path[0]:
            return Action.STAY
        action = move_between(path[0], path[1], w)
        return action if action in legal else Action.STAY

    def _best_attack(self, state: GameState, me: int, legal: list[Action]) -> Action | None:
        cfg = self.cfg
        w = state.width
        opp = 1 - me
        here = state.player_cell(me)
        candidates = [Action.BOMB] if Action.BOMB in legal else []
        if cfg.physics.kick:
            for a in MOVES:
                if a in legal:
                    dx, dy = DIRECTIONS[a]
                    if bomb_at(state, here + dy * w + dx) is not None:
                        candidates.append(a)
        if not candidates:
            return None

        opp_alive = state.players[opp].alive
        opp_can_bomb = opp_alive and Action.BOMB in legal_actions(state, opp, cfg)
        opp_cell = state.player_cell(opp) if opp_alive else -1
        opp_reachable = opp_alive and self._reachable(state, me, opp_cell)
        best_score, best_action, best_path = 0.0, None, None
        for a in candidates:
            sim = after_action(state, me, a, cfg)
            if not sim.players[me].alive:
                continue
            timeline = predict(sim, self.horizon, self.cfg, absent=me)
            contested = None
            cautious = timeline
            if opp_alive:
                # Stan hipotetyczny jest o tick dalej, a przeciwnik wcale nie musi stać w miejscu.
                reach = opponent_reach(sim, me, self.horizon, start=opp_cell)
                contested = {c: max(0, t - 1) for c, t in reach.items()}
                cautious = with_kick_threats(sim, me, timeline, self.cfg, contested)
            mine = self._escape(sim, me, cautious, contested=contested)
            if mine is None:
                continue
            if opp_can_bomb and not self._survives_counter_bomb(state, me, a):
                continue
            score = 0.0
            if not sim.players[opp].alive:
                score = TRAP_SCORE * 2
            elif in_danger(timeline, sim.player_cell(opp)):
                area: set[Cell] = set()
                escape_path(sim, opp, timeline, self.cfg, collect=area)
                if not area:
                    score = TRAP_SCORE
                else:
                    score = THREAT_SCORE + AREA_SCORE * max(0.0, 1.0 - len(area) / AREA_NORM)
            elif a == Action.BOMB:
                boxes = sum(1 for c in blast_cross(sim.grid, w, here, cfg.bomb_radius) if sim.grid[c] == BOX)
                score = boxes * (0.5 if opp_reachable else 1.0)
            if score > best_score:
                best_score, best_action, best_path = score, a, mine
        if best_action is None or best_score < MIN_ATTACK_SCORE:
            return None
        plan = [[c % w, c // w] for c in best_path]
        set_debug(self, family="search", ops=self._ops, detail=f"bfs_nodes={self._ops}",
                  mode="attack", plan=plan,
                  rationale=f"atak score={best_score:.1f}")
        self.debug["score"] = round(best_score, 1)
        return best_action

    def _survives_counter_bomb(self, state: GameState, me: int, mine: Action) -> bool:
        """Czy bot nadal ma ucieczkę, jeśli przeciwnik w tym samym ticku położy bombę."""
        sim = after_action(state, me, mine, self.cfg, other=Action.BOMB)
        if not sim.players[me].alive:
            return False
        timeline = predict(sim, self.horizon, self.cfg, absent=me)
        return self._escape(sim, me, timeline) is not None

    def _approach(self, state: GameState, me: int, timeline: list[TickInfo], legal: list[Action]) -> Action:
        cfg = self.cfg
        w = state.width
        here = state.player_cell(me)
        opp = 1 - me
        opp_alive = state.players[opp].alive
        opp_reach = opponent_reach(state, me, self.horizon)
        targets: set[Cell] = set()
        if opp_alive:
            targets = attack_cells(state, state.player_cell(opp), cfg.bomb_radius)
        dist = self._distances_to(state, me, targets) if targets else {}
        if here not in dist:
            dist = self._distances_to(state, me, box_neighbours(state))
        if here not in dist and opp_alive:
            ox, oy = state.xy(state.player_cell(opp))
            reach = self._distances_to(state, me, {here})
            closest = min(reach, key=lambda c: abs(c % w - ox) + abs(c // w - oy))
            dist = self._distances_to(state, me, {closest})
        inf = float("inf")
        here_dist = dist.get(here, inf)

        opp_can_bomb = opp_alive and Action.BOMB in legal_actions(state, opp, cfg)
        ox, oy = state.xy(state.player_cell(opp)) if opp_alive else (-99, -99)
        options: list[tuple[float, float, Action, Cell]] = []
        for a in legal:
            if a == Action.BOMB:
                continue
            n = here
            if a != Action.STAY:
                dx, dy = DIRECTIONS[a]
                n = here + dy * w + dx
                if bomb_at(state, n) is not None:
                    continue
            options.append((dist.get(n, inf), self.rng.random(), a, n))
        options.sort()
        fire_next = timeline[1].flames if len(timeline) > 1 else set()
        free_moves: list[tuple[float, Action, Cell, list[Cell]]] = []
        free_stay: list[tuple[float, Action, Cell, list[Cell]]] = []
        contested: list[tuple[float, Action, Cell, list[Cell]]] = []
        for d, _, a, n in options:
            if a != Action.STAY and d >= here_dist and d != inf:
                continue
            if n in fire_next:
                continue
            path = self._escape(state, me, timeline, start=n, start_t=1, contested=opp_reach)
            if path is None:
                continue
            near = abs(n % w - ox) + abs(n // w - oy) <= cfg.bomb_radius + 2
            if opp_can_bomb and near and not self._survives_counter_bomb(state, me, a):
                continue
            entry = (d, a, n, path)
            # Gdy przeciwnik wejdzie na to samo pole w tym samym ticku, oba ruchy się anulują.
            if a != Action.STAY and opp_reach.get(n, inf) <= 1:
                contested.append(entry)
            elif a == Action.STAY:
                free_stay.append(entry)
            else:
                free_moves.append(entry)

        # STAY nie może wygrywać ze spornym polem, bo obaj gracze utknęliby w miejscu.
        chosen: tuple[float, Action, Cell, list[Cell]] | None = None
        mode = "approach"
        rationale = "podejście z bezpieczną ucieczką"
        if free_moves:
            chosen = free_moves[0]
        elif contested:
            if (state.tick + me) % 2 == 0:
                set_debug(self, family="search", ops=self._ops, detail=f"bfs_nodes={self._ops}",
                          mode="yield", rationale="ustępuję spornego pola (tick parzysty/nieparzysty)")
                return Action.STAY
            chosen = contested[0]
            rationale = "podejście na sporne pole"
        elif free_stay:
            chosen = free_stay[0]
            mode = "wait"
            rationale = "brak lepszego ruchu, czekam"

        if chosen is not None:
            _, a, n, path = chosen
            plan = [[c % w, c // w] for c in [here] + path]
            set_debug(self, family="search", ops=self._ops, detail=f"bfs_nodes={self._ops}",
                      mode=mode, plan=plan, rationale=rationale)
            return a
        set_debug(self, family="search", ops=self._ops, detail=f"bfs_nodes={self._ops}",
                  mode="wait", rationale="brak bezpiecznego ruchu, czekam")
        return Action.STAY

    def _distances_to(self, state: GameState, me: int, sources: set[Cell]) -> dict[Cell, int]:
        """Odległości (w ruchach) od zbioru pól docelowych, liczone po polach przechodnich."""
        w = state.width
        grid = state.grid
        here = state.player_cell(me)
        blocked = {int(b.y + 0.5) * w + int(b.x + 0.5) for b in state.bombs}
        for o in state.obstacles:
            blocked.update(physics.obstacle_cells(o, w))
        other = state.players[1 - me]
        if other.alive:
            blocked.add(state.player_cell(other.id))

        def passable(c: Cell) -> bool:
            return c == here or (grid[c] == EMPTY and c not in blocked)

        dist = {}
        queue = deque()
        for s in sources:
            if passable(s):
                dist[s] = 0
                queue.append(s)
        while queue:
            c = queue.popleft()
            for n in (c - w, c + w, c - 1, c + 1):
                if n not in dist and passable(n):
                    dist[n] = dist[c] + 1
                    queue.append(n)
        return dist

    def _reachable(self, state: GameState, me: int, target: Cell) -> bool:
        w = state.width
        neighbours = {target - w, target + w, target - 1, target + 1}
        return state.player_cell(me) in self._distances_to(state, me, neighbours)
