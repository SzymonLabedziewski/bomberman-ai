from bomberman.ai.danger import danger_ticks, escape_path, has_escape, in_danger, predict
from bomberman.engine import Action, Bomb, from_layout, step
from bomberman.engine.state import BOX
from tests.conftest import OPEN_9, put


def cells(state, path):
    return [(c % state.width, c // state.width) for c in path]


def test_predict_marks_blast_at_the_right_tick(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    s.bombs.append(Bomb(0, 1, 3.0, 3.0, 3, 2))
    s.players[1].bombs_used = 1
    timeline = predict(s, 10, cfg)
    w = s.width
    assert not timeline[1].flames and not timeline[2].flames
    assert {3 * w + 3, 3 * w + 5, 1 * w + 3, 5 * w + 3, 3 * w + 1} <= timeline[3].flames
    assert len(timeline) == 5, "symulacja kończy się, gdy nie ma bomb ani ognia"
    assert danger_ticks(timeline)[3 * w + 4] == 3


def test_predict_includes_chain_reaction(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    s.bombs += [Bomb(0, 0, 3.0, 3.0, 2, 2), Bomb(1, 1, 5.0, 3.0, 5, 2)]
    timeline = predict(s, 10, cfg)
    w = s.width
    assert 3 * w + 7 in timeline[2].flames, "druga bomba wybucha razem z pierwszą"


def test_escape_found_and_shortest(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    step(s, [Action.BOMB, Action.STAY], cfg)
    path = escape_path(s, 0, predict(s, 10, cfg), cfg)
    assert path is not None
    assert len(path) - 1 == 3, "z rogu trzeba zrobić trzy ruchy (np. dwa wzdłuż korytarza i jeden w bok)"
    assert cells(s, path)[0] == (1, 1)
    x, y = cells(s, path)[-1]
    outside_cross = x != 1 and y != 1
    beyond_radius = abs(x - 1) + abs(y - 1) > cfg.bomb_radius
    assert outside_cross or beyond_radius


def test_no_escape_when_trapped(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7), **{"+": (1, 2)}))
    s.bombs.append(Bomb(0, 1, 2.0, 1.0, 1, 2))
    s.players[1].bombs_used = 1
    timeline = predict(s, 10, cfg)
    assert in_danger(timeline, s.player_cell(0))
    assert escape_path(s, 0, timeline, cfg) is None
    assert not has_escape(s, 0, cfg)
    survive = escape_path(s, 0, timeline, cfg, best_effort=True)
    assert survive is not None and survive[0] == s.player_cell(0)


def test_safe_cell_needs_no_escape(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    s.bombs.append(Bomb(0, 1, 7.0, 5.0, 3, 2))
    timeline = predict(s, 10, cfg)
    assert escape_path(s, 0, timeline, cfg) == [s.player_cell(0)]


CORRIDOR = [
    "#########",
    "#.......#",
    "#.#.#.#+#",
    "#A.B....#",
    "#.#.#.#.#",
    "#.......#",
    "#+#.#.#.#",
    "#.+.....#",
    "#########",
]


def test_contested_escape_is_avoided(cfg):
    s = from_layout(CORRIDOR)
    step(s, [Action.BOMB, Action.BOMB], cfg)
    timeline = predict(s, 10, cfg)
    assert escape_path(s, 0, timeline, cfg) is not None
    contested = {s.idx(2, 1): 3, s.idx(2, 5): 3}
    assert escape_path(s, 0, timeline, cfg, contested=contested) is None, \
        "oba bezpieczne pola przeciwnik osiąga w tym samym ticku"


def test_planner_does_not_bomb_with_contested_escape(cfg):
    from bomberman.ai.planner_bot import PlannerBot

    s = from_layout(CORRIDOR)
    assert PlannerBot(cfg).act(s, 0) != Action.BOMB


def test_escape_respects_box_destruction_timing(cfg):
    s = from_layout(put(OPEN_9, A=(3, 1), B=(7, 7)))
    s.grid[1 * 9 + 4] = BOX
    s.bombs.append(Bomb(0, 1, 3.0, 3.0, 2, 2))
    timeline = predict(s, 10, cfg)
    assert timeline[2].grid[1 * 9 + 4] == BOX
    path = escape_path(s, 0, timeline, cfg)
    assert path is not None
    assert all(c not in timeline[t].flames for t, c in enumerate(path) if t < len(timeline))
