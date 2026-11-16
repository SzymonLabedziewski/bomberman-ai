"""Losowe sytuacje zagrożenia do eksperymentu E5."""

from __future__ import annotations

import random

from bomberman.ai.base import Bot
from bomberman.ai.danger import default_horizon, escape_path, in_danger, predict
from bomberman.config import GameConfig
from bomberman.engine.board import new_game
from bomberman.engine.rules import bomb_at, obstacle_at, step
from bomberman.engine.state import DIR4, EMPTY, Action, Bomb, GameState

MAX_TICKS = 15
KEEP_HOPELESS = 0.25


def make_scenario(cfg: GameConfig, seed: int) -> GameState:
    """Losowa sytuacja zagrożenia (część sytuacji bez wyjścia jest odrzucana)."""
    rng = random.Random(seed)
    while True:
        state = _try_scenario(cfg, rng)
        if state is not None and (is_escapable(state, cfg) or rng.random() < KEEP_HOPELESS):
            return state


def _try_scenario(cfg: GameConfig, rng: random.Random) -> GameState | None:
    state = new_game(cfg, rng.randrange(1 << 30))
    w = state.width
    opp_cell = state.player_cell(1)
    free = [c for c, v in enumerate(state.grid)
            if v == EMPTY and c != opp_cell and not obstacle_at(state, c)]
    me = rng.choice(free)
    p = state.players[0]
    p.x, p.y = float(me % w), float(me // w)

    in_line = [me]
    for dx, dy in DIR4:
        c = me
        for _ in range(cfg.bomb_radius):
            c += dy * w + dx
            if state.grid[c] != EMPTY or obstacle_at(state, c):
                break
            in_line.append(c)
    for c in rng.sample(in_line, min(len(in_line), rng.randint(1, 3))):
        if c == opp_cell:
            continue
        _add_bomb(state, c, rng.randint(2, cfg.bomb_timer), cfg)

    if cfg.physics.kick:
        runs = []
        for dx, dy in DIR4:
            cells = []
            c = me
            for _ in range(5):
                c += dy * w + dx
                if state.grid[c] != EMPTY or obstacle_at(state, c) or c == opp_cell or bomb_at(state, c):
                    break
                cells.append(c)
            if len(cells) >= 3:
                runs.append((dx, dy, cells))
        if not runs:
            return None
        dx, dy, cells = rng.choice(runs)
        start = rng.choice(cells[2:])
        b = _add_bomb(state, start, rng.randint(3, cfg.bomb_timer), cfg)
        b.vx, b.vy = -dx * cfg.physics.kick_speed, -dy * cfg.physics.kick_speed
        b.moved = True

    if not state.bombs or not in_danger(predict(state, default_horizon(cfg), cfg), me):
        return None
    return state


def _add_bomb(state: GameState, cell: int, timer: int, cfg: GameConfig) -> Bomb:
    w = state.width
    b = Bomb(state.next_bomb_id, 1, float(cell % w), float(cell // w), timer, cfg.bomb_radius)
    state.next_bomb_id += 1
    state.bombs.append(b)
    state.players[1].bombs_used += 1
    return b


def is_escapable(state: GameState, cfg: GameConfig) -> bool:
    return escape_path(state, 0, predict(state, default_horizon(cfg), cfg), cfg) is not None


def run_escape(state: GameState, bot: Bot, cfg: GameConfig) -> tuple[bool, int]:
    """Prowadzi bota, aż wyjdzie z zagrożenia albo zginie (bez kładzenia bomb)."""
    s = state.clone()
    horizon = default_horizon(cfg)
    for t in range(MAX_TICKS):
        if not s.players[0].alive:
            return False, t
        if not (s.bombs or s.flames) or not in_danger(predict(s, horizon, cfg), s.player_cell(0)):
            return True, t
        action = bot.act(s, 0)
        if action == Action.BOMB:
            action = Action.STAY
        step(s, [action, Action.STAY], cfg, record=False)
    return s.players[0].alive, MAX_TICKS
