from __future__ import annotations

from bomberman.ai.baselines import RandomBot, RandomSafeBot
from bomberman.ai.montecarlo_bot import MonteCarloBot
from bomberman.ai.planner_bot import PlannerBot
from bomberman.ai.q_table import QTable
from bomberman.ai.qlearner_bot import QLearnerBot
from bomberman.ai.telemetry import compute_totals, make_compute, rss_kb
from bomberman.config import load_config
from bomberman.engine.board import new_game
from bomberman.experiments.metrics import play_measured


def test_rss_and_make_compute():
    c = make_compute(12, "detail=x", wall_ms=1.5)
    assert c["ops"] == 12
    assert c["wall_ms"] == 1.5
    assert "rss_kb" in c
    assert rss_kb() >= 0


def test_bots_emit_compute():
    cfg = load_config()
    state = new_game(cfg, 5)
    bots = [
        RandomBot(cfg, 1),
        RandomSafeBot(cfg, 2),
        PlannerBot(cfg, 3),
        MonteCarloBot(cfg, 4, rollouts=5, depth=3),
    ]
    for bot in bots:
        bot.act(state, 0)
        assert "compute" in bot.debug
        assert "ops" in bot.debug["compute"]
        assert bot.debug["family"] in ("random", "search", "rl")


def test_qlearner_compute(tmp_path):
    cfg = load_config()
    table = QTable()
    path = tmp_path / "q.json"
    table.save(path)
    bot = QLearnerBot(cfg, seed=1, table_path=path)
    bot.act(new_game(cfg, 2), 0)
    assert bot.debug["family"] == "rl"
    assert bot.debug["compute"]["ops"] >= 1


def test_play_measured_telemetry_columns():
    cfg = load_config()
    bots = [RandomSafeBot(cfg, 1), PlannerBot(cfg, 2)]
    state, stats = play_measured(cfg, bots, seed=9)
    assert state.done
    for st in stats:
        row = st.row()
        assert "ops_mean" in row
        assert "rss_kb_mean" in row
        assert "family" in row
        assert row["family"] in ("random", "search")
        tot = st.totals()
        assert tot["ticks"] >= 1


def test_compute_totals():
    tot = compute_totals([
        {"wall_ms": 1.0, "ops": 10, "rss_kb": 100},
        {"wall_ms": 3.0, "ops": 30, "rss_kb": 200},
    ])
    assert tot["wall_ms_mean"] == 2.0
    assert tot["ops_sum"] == 40
    assert tot["rss_kb_mean"] == 150.0
