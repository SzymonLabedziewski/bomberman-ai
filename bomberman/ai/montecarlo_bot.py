"""Bot Monte Carlo: ocena akcji krótkimi losowymi symulacjami."""

from __future__ import annotations

import random

from bomberman.ai.base import BaseBot
from bomberman.ai.telemetry import set_debug
from bomberman.config import GameConfig
from bomberman.engine.rules import bomb_at, legal_actions, step
from bomberman.engine.state import BOX, DIRECTIONS, EMPTY, WALL, Action, Cell, GameState

THREAT_WEIGHT = 0.2
MOBILITY_WEIGHT = 0.05
DISTANCE_WEIGHT = 0.05
POLICY_LOOKAHEAD = 2


class MonteCarloBot(BaseBot):
    name = "montecarlo"

    def __init__(self, cfg: GameConfig, seed: int = 0, rollouts: int = 30, depth: int = 8,
                 bomb_prob: float = 0.1) -> None:
        super().__init__(cfg, seed)
        if rollouts < 1 or depth < 1:
            raise ValueError("rollouts i depth muszą być dodatnie")
        self.rollouts = rollouts
        self.depth = depth
        self.bomb_prob = bomb_prob

    def act(self, state: GameState, me: int) -> Action:
        p = state.players[me]
        if not p.alive or p.stunned:
            set_debug(self, family="search", ops=0, detail="stunned", mode="stunned",
                      rationale="ogłuszony / martwy")
            return Action.STAY
        legal = legal_actions(state, me, self.cfg)
        seeds = [self.rng.getrandbits(32) for _ in range(self.rollouts)]
        values: dict[Action, float] = {}
        for a in legal:
            total = 0.0
            for s in seeds:
                total += self._rollout(state, me, a, random.Random(s))
            values[a] = total / self.rollouts
        best = max(values.values())
        choices = [a for a in legal if values[a] >= best - 1e-9]
        action = choices[0] if len(choices) == 1 else self.rng.choice(choices)
        ops = len(legal) * self.rollouts * self.depth
        set_debug(self, family="search", ops=ops,
                  detail=f"rollouts={self.rollouts} depth={self.depth} legal={len(legal)}",
                  mode="montecarlo",
                  values={a.name: round(v, 3) for a, v in values.items()},
                  rationale=f"MC best={action.name} ({best:+.3f})")
        return action

    def _rollout(self, state: GameState, me: int, first: Action, rng: random.Random) -> float:
        cfg = self.cfg
        sim = state.clone()
        opp = 1 - me
        actions = [Action.STAY, Action.STAY]
        actions[me] = first
        actions[opp] = self._policy(sim, opp, rng, _hot_cells(sim, cfg))
        step(sim, actions, cfg, record=False)
        for _ in range(self.depth - 1):
            if sim.done:
                break
            hot = _hot_cells(sim, cfg)
            actions[0] = self._policy(sim, 0, rng, hot)
            actions[1] = self._policy(sim, 1, rng, hot)
            step(sim, actions, cfg, record=False)
        return self._evaluate(sim, me)

    def _policy(self, sim: GameState, pid: int, rng: random.Random, hot: set[Cell]) -> Action:
        """Szybka polityka symulacji: losowy ruch poza pola bliskiego wybuchu, czasem bomba."""
        p = sim.players[pid]
        if not p.alive or p.vx or p.vy:
            return Action.STAY
        legal = legal_actions(sim, pid, self.cfg)
        if Action.BOMB in legal and rng.random() < self.bomb_prob:
            return Action.BOMB
        w = sim.width
        here = int(p.y + 0.5) * w + int(p.x + 0.5)
        safe = []
        for a in legal:
            if a == Action.BOMB:
                continue
            n = here
            if a != Action.STAY:
                dx, dy = DIRECTIONS[a]
                n = here + dy * w + dx
                if sim.bombs and bomb_at(sim, n) is not None:
                    n = here
            if n not in hot:
                safe.append(a)
        if safe:
            return rng.choice(safe)
        return rng.choice(legal)

    def _evaluate(self, sim: GameState, me: int) -> float:
        opp = 1 - me
        mine, theirs = sim.players[me].alive, sim.players[opp].alive
        if not mine:
            return 0.0 if not theirs else -1.0
        if not theirs:
            return 1.0
        w = sim.width
        my_cell, opp_cell = sim.player_cell(me), sim.player_cell(opp)
        threatened = _blast_cells(sim, None)
        score = 0.0
        if opp_cell in threatened:
            score += THREAT_WEIGHT
        if my_cell in threatened:
            score -= THREAT_WEIGHT
        score += MOBILITY_WEIGHT * (_mobility(sim, my_cell) - _mobility(sim, opp_cell)) / 4
        dist = abs(my_cell % w - opp_cell % w) + abs(my_cell // w - opp_cell // w)
        score -= DISTANCE_WEIGHT * dist / (sim.width + sim.height)
        return score


def _hot_cells(sim: GameState, cfg: GameConfig) -> set[Cell]:
    """Pola, w które polityka symulacji nie wchodzi: zasięg bomb bliskich wybuchu i trwający ogień."""
    cells = _blast_cells(sim, POLICY_LOOKAHEAD)
    if cfg.flame_duration > 1:
        cells.update(c for c, left in sim.flames.items() if left > 1)
    return cells


def _blast_cells(sim: GameState, max_timer: int | None) -> set[Cell]:
    """Krzyże wybuchów bomb (bez reakcji łańcuchowych)."""
    w = sim.width
    grid = sim.grid
    cells: set[Cell] = set()
    for b in sim.bombs:
        if max_timer is not None and b.timer > max_timer:
            continue
        center = int(b.y + 0.5) * w + int(b.x + 0.5)
        cells.add(center)
        for delta in (-w, w, -1, 1):
            c = center
            for _ in range(b.radius):
                c += delta
                v = grid[c]
                if v == WALL:
                    break
                cells.add(c)
                if v == BOX:
                    break
    return cells


def _mobility(sim: GameState, cell: Cell) -> int:
    w = sim.width
    return sum(1 for n in (cell - w, cell + w, cell - 1, cell + 1)
               if sim.grid[n] == EMPTY and (not sim.bombs or bomb_at(sim, n) is None))
