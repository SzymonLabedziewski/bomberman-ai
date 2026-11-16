import json
import random

from bomberman.config import GameConfig
from bomberman.engine import Action, Bomb, from_layout, legal_actions, new_game, step
from bomberman.engine.ascii_view import render
from bomberman.engine.serialize import state_from_dict, state_to_dict
from bomberman.engine.state import BOX, EMPTY, WALL
from tests.conftest import OPEN_9, put

S, U, D, L, R, B = Action.STAY, Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT, Action.BOMB


def flame_cells(state):
    return {(c % state.width, c // state.width) for c in state.flames}


def test_board_layout_and_symmetry(cfg):
    s = new_game(cfg, seed=3)
    w, h = s.width, s.height
    for x in range(w):
        assert s.grid[x] == WALL and s.grid[(h - 1) * w + x] == WALL
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            assert s.grid[y * w + x] == WALL
    for y in range(h):
        for x in range(w):
            assert s.grid[y * w + x] == s.grid[(h - 1 - y) * w + (w - 1 - x)]
    for x, y in [(1, 1), (2, 1), (1, 2), (7, 7), (6, 7), (7, 6)]:
        assert s.grid[y * w + x] == EMPTY
    assert any(v == BOX for v in s.grid)


def test_board_is_deterministic(cfg):
    assert new_game(cfg, 5).grid == new_game(cfg, 5).grid
    assert new_game(cfg, 5).grid != new_game(cfg, 6).grid


def test_bomb_explodes_after_timer_in_cross_shape(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    plan = [B, R, R, D, S, S]
    for a in plan[:5]:
        step(s, [a, S], cfg)
        assert s.bombs, "bomba nie może wybuchnąć przed czasem"
    events = step(s, [plan[5], S], cfg)
    assert not s.bombs
    assert any(e["type"] == "explosion" for e in events)
    assert flame_cells(s) == {(1, 1), (2, 1), (3, 1), (1, 2), (1, 3)}
    assert s.players[0].alive and s.players[0].cell == (3, 2)
    step(s, [S, S], cfg)
    assert not s.flames, "ogień trwa jeden tick"


def test_box_stops_flame_and_is_destroyed(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7), **{"+": (2, 1)}))
    s.bombs.append(Bomb(0, 1, 1.0, 3.0, 1, 2))
    s.players[1].bombs_used = 1
    s.grid[3 * 9 + 2] = BOX
    s.grid[3 * 9 + 3] = EMPTY
    step(s, [S, S], cfg)
    cells = flame_cells(s)
    assert (2, 3) in cells and (3, 3) not in cells
    assert s.grid[3 * 9 + 2] == EMPTY
    assert (1, 1) in cells and not s.players[0].alive


def test_chain_reaction_in_same_tick(cfg):
    s = from_layout(put(OPEN_9, A=(7, 1), B=(7, 7)))
    s.bombs += [Bomb(0, 0, 1.0, 3.0, 1, 2), Bomb(1, 1, 3.0, 3.0, 9, 2)]
    s.players[0].bombs_used = s.players[1].bombs_used = 1
    events = step(s, [S, S], cfg)
    assert not s.bombs
    assert sum(e["type"] == "explosion" for e in events) == 2
    assert (5, 3) in flame_cells(s)
    assert s.players[0].bombs_used == 0 and s.players[1].bombs_used == 0


def test_death_gives_win_and_double_death_is_draw(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    s.bombs.append(Bomb(0, 0, 3.0, 1.0, 1, 2))
    s.players[0].bombs_used = 1
    events = step(s, [S, S], cfg)
    assert s.done and s.winner == 1
    death = next(e for e in events if e["type"] == "death")
    assert death["player"] == 0 and death["by_self"] and not death["by_enemy"]

    s = from_layout(put(OPEN_9, A=(1, 3), B=(5, 3)))
    s.bombs.append(Bomb(0, 0, 3.0, 3.0, 1, 2))
    s.players[0].bombs_used = 1
    step(s, [S, S], cfg)
    assert s.done and s.winner == -1


def test_max_ticks_is_draw():
    cfg = GameConfig(max_ticks=3)
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    for _ in range(3):
        step(s, [S, S], cfg)
    assert s.done and s.winner == -1


def test_bomb_limit_and_bomb_blocks_return(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    step(s, [B, S], cfg)
    step(s, [R, S], cfg)
    assert Action.BOMB not in legal_actions(s, 0, cfg)
    step(s, [B, S], cfg)
    assert len(s.bombs) == 1
    assert Action.LEFT not in legal_actions(s, 0, cfg)
    step(s, [L, S], cfg)
    assert s.players[0].cell == (2, 1)


def test_simultaneous_moves_conflicts(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(3, 1)))
    step(s, [R, L], cfg)
    assert s.players[0].cell == (1, 1) and s.players[1].cell == (3, 1)
    s = from_layout(put(OPEN_9, A=(1, 1), B=(2, 1)))
    step(s, [R, L], cfg)
    assert s.players[0].cell == (1, 1) and s.players[1].cell == (2, 1)


def test_walls_block_moves(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    assert set(legal_actions(s, 0, cfg)) == {S, R, D, B}
    step(s, [U, S], cfg)
    assert s.players[0].cell == (1, 1)


def test_flame_duration_two_kills_late_walker():
    cfg = GameConfig(flame_duration=2)
    s = from_layout(put(OPEN_9, A=(4, 1), B=(7, 7)))
    s.bombs.append(Bomb(0, 1, 1.0, 1.0, 1, 2))
    s.players[1].bombs_used = 1
    step(s, [S, S], cfg)
    assert (3, 1) in flame_cells(s) and s.players[0].alive
    step(s, [L, S], cfg)
    assert not s.players[0].alive


def play_random(cfg, seed, ticks=80):
    s = new_game(cfg, seed)
    rng = random.Random(seed)
    for _ in range(ticks):
        if s.done:
            break
        step(s, [rng.choice(legal_actions(s, 0, cfg)), rng.choice(legal_actions(s, 1, cfg))], cfg)
    return s


def test_step_is_deterministic(cfg):
    a, b = play_random(cfg, 11), play_random(cfg, 11)
    assert state_to_dict(a) == state_to_dict(b)


def test_serialize_round_trip(cfg):
    s = play_random(cfg, 4, ticks=12)
    d = json.loads(json.dumps(state_to_dict(s)))
    assert state_to_dict(state_from_dict(d))["grid"] == d["grid"]
    assert state_from_dict(d).players[1].cell == s.players[1].cell


def test_ascii_render_shows_players(cfg):
    text = render(new_game(cfg, 1))
    assert "A" in text and "B" in text and "tick 0" in text
