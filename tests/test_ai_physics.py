import pytest

from bomberman.ai.danger import default_horizon, in_danger, predict, with_kick_threats
from bomberman.ai.registry import BOT_NAMES, make_bot
from bomberman.engine import Action, Bomb, from_layout, step
from bomberman.engine.state import Obstacle
from tests.conftest import OPEN_9, put
from tests.test_bots import FAST_PARAMS, StayBot, play


def test_kick_threat_extends_danger_along_kick_line(phys_cfg):
    state = from_layout(put(OPEN_9, A=(1, 5), B=(1, 1)))
    state.bombs.append(Bomb(0, 1, 1.0, 2.0, 5, 2))
    me = state.player_cell(0)
    base = predict(state, default_horizon(phys_cfg), phys_cfg, absent=0)
    cautious = with_kick_threats(state, 0, base, phys_cfg, {state.player_cell(1): 0})
    assert not in_danger(base, me)
    assert in_danger(cautious, me)
    assert with_kick_threats(state, 0, base, phys_cfg.without_physics(), {state.player_cell(1): 0}) is base


def test_absent_player_does_not_stop_sliding_bomb(phys_cfg):
    state = from_layout(put(OPEN_9, A=(5, 1)))
    state.bombs.append(Bomb(0, 1, 1.0, 1.0, 9, 2, vx=1.5, moved=True))
    behind = state.idx(6, 1)
    present = predict(state, 8, phys_cfg)
    absent = predict(state, 8, phys_cfg, absent=0)
    assert not any(behind in info.occupied for info in present)
    assert any(behind in info.occupied for info in absent)


def test_prediction_ignores_obstacle_shield(phys_cfg):
    state = from_layout(OPEN_9)
    state.obstacles.append(Obstacle(0, 2.0, 3.0, 0.5, 0.0))
    state.bombs.append(Bomb(0, 0, 1.0, 3.0, 1, 2))
    timeline = predict(state, 3, phys_cfg)
    real = state.clone()
    step(real, (Action.STAY, Action.STAY), phys_cfg)
    behind = state.idx(3, 3)
    assert behind not in real.flames
    assert behind in timeline[1].flames


@pytest.mark.parametrize("name", BOT_NAMES)
def test_bots_return_legal_actions_with_physics(phys_cfg, name):
    for seed in range(2):
        bot = make_bot(name, phys_cfg, seed, **FAST_PARAMS.get(name, {}))
        play(phys_cfg, bot, make_bot("randomsafe", phys_cfg, seed + 100), seed, max_ticks=60)


def test_planner_survives_own_bombs_with_physics(phys_cfg):
    for seed in range(4):
        s, deaths = play(phys_cfg, make_bot("planner", phys_cfg, seed), StayBot(phys_cfg), seed)
        assert s.players[0].alive, f"Planner zginął (seed {seed}): {deaths}"
