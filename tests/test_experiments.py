import csv
import json

import pytest

from bomberman.ai.base import BaseBot
from bomberman.ai.danger import default_horizon, in_danger, predict
from bomberman.ai.planner_bot import PlannerBot
from bomberman.config import GameConfig
from bomberman.engine import Action, from_layout
from bomberman.experiments.analyze import analyze, wilson
from bomberman.experiments.metrics import play_measured
from bomberman.experiments.runner import MATCH_COLUMNS, _match_task, build_tasks
from bomberman.experiments.scenarios import make_scenario
from tests.conftest import OPEN_9, put


class ScriptBot(BaseBot):
    def __init__(self, cfg, actions):
        super().__init__(cfg)
        self.actions = list(actions)

    def act(self, state, me):
        return self.actions.pop(0) if self.actions else Action.STAY


def test_wilson_interval():
    p, lo, hi = wilson(5, 10)
    assert p == 0.5 and lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert wilson(0, 10)[1] == 0.0 and wilson(10, 10)[2] == 1.0
    assert wilson(0, 0) == (0.0, 0.0, 0.0)


def test_tasks_share_seeds_and_swap_sides():
    config = {"name": "T", "games": 4, "seed": 100, "round_robin": ["random", "randomsafe", "planner"],
              "games_for": {"Random vs Planner": 2}}
    tasks = build_tasks(config)
    by_pair = {}
    for t in tasks:
        by_pair.setdefault(t["matchup"], []).append(t)
    assert len(by_pair) == 3 and len(by_pair["Random vs Planner"]) == 2
    first = by_pair["Random vs RandomSafe"]
    assert [t["seed"] for t in first] == [100, 101, 102, 103]
    assert first[0]["seats"][0]["name"] == "random" and first[1]["seats"][0]["name"] == "randomsafe"


def test_random_seeds_and_max_ticks_in_tasks():
    config = {
        "name": "E1", "games": 6, "max_ticks": 1000, "random_seeds": True, "seed": 10000,
        "physics": {"kick": True, "knockback": True, "moving_obstacles": False},
        "round_robin": ["random", "randomsafe", "planner"],
    }
    tasks = build_tasks(config)
    by_pair = {}
    for t in tasks:
        by_pair.setdefault(t["matchup"], []).append(t)
    seeds_a = [t["seed"] for t in by_pair["Random vs RandomSafe"]]
    seeds_b = [t["seed"] for t in by_pair["Random vs Planner"]]
    assert len(set(seeds_a)) == 6
    assert seeds_a == seeds_b, "każda para w turnieju musi rozgrywać te same wylosowane ziarna map"
    assert all(t["max_ticks"] == 1000 for t in tasks)
    assert all(t["physics"] == {"kick": True, "knockback": True, "moving_obstacles": False} for t in tasks)


def test_suicide_and_self_kill_are_counted(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7), **{"+": [(2, 1), (1, 2)]}))
    state, stats = play_measured(cfg, [ScriptBot(cfg, [Action.BOMB]), ScriptBot(cfg, [])], 0, state=s)
    assert state.winner == 1
    assert stats[0].suicides == 1 and stats[0].self_kill and stats[0].died
    assert stats[0].escape_episodes == 1 and stats[0].escape_success == 0
    assert stats[0].escapable_episodes == 0, "po położeniu bomby w zamknięciu nie było już ucieczki"
    assert stats[1].suicides == 0 and not stats[1].died


def test_staying_on_own_bomb_is_a_failed_escapable_episode(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    state, stats = play_measured(cfg, [ScriptBot(cfg, [Action.BOMB]), ScriptBot(cfg, [])], 0, state=s)
    st = stats[0]
    assert st.died and st.self_kill
    assert st.escape_episodes == 1 and st.escapable_episodes == 1 and st.escape_success == 0
    assert st.suicides == 1, "samobójcze jest ostatnie STAY, po którym nie da się już uciec"


def test_planner_escapes_are_measured():
    cfg = GameConfig(max_ticks=40)
    _, stats = play_measured(cfg, [PlannerBot(cfg), ScriptBot(cfg, [])], 0)
    st = stats[0]
    assert st.bombs_placed >= 1 and st.escape_episodes >= 1
    assert st.escape_success == st.escape_episodes and st.suicides == 0
    assert st.escape_ticks_sum >= st.escape_success


def test_match_task_rows(cfg):
    task = {"kind": "match", "experiment": "T", "variant": "", "matchup": "Random vs RandomSafe", "game_id": 0,
            "seed": 5, "physics": False,
            "seats": [{"name": "random", "params": {}, "label": "Random"},
                      {"name": "randomsafe", "params": {}, "label": "RandomSafe"}]}
    rows = _match_task(task)
    assert len(rows) == 2 and set(rows[0]) == set(MATCH_COLUMNS)
    assert {rows[0]["result"], rows[1]["result"]} in ({"win", "loss"}, {"draw"})
    def without_time(rs):
        return [
            {k: v for k, v in r.items()
             if not k.startswith("decision_ms") and not k.startswith("cpu_ms") and not k.startswith("rss_kb")}
            for r in rs
        ]

    assert without_time(rows) == without_time(_match_task(task)), "gra musi być powtarzalna dla tego samego ziarna"


def test_scenario_puts_player_in_danger(cfg):
    for seed in range(10):
        s = make_scenario(cfg, seed)
        assert in_danger(predict(s, default_horizon(cfg), cfg), s.player_cell(0))
        assert make_scenario(cfg, seed).bombs == s.bombs


def test_analyze_writes_summary(tmp_path, cfg):
    rows = []
    for i in range(6):
        seats = [{"name": "random", "params": {}, "label": "Random"},
                 {"name": "randomsafe", "params": {}, "label": "RandomSafe"}]
        rows += _match_task({"kind": "match", "experiment": "E1", "variant": "", "game_id": i, "seed": i,
                             "matchup": "Random vs RandomSafe", "physics": False,
                             "seats": seats if i % 2 == 0 else seats[::-1]})
    with open(tmp_path / "E1.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MATCH_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    analyze(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert {c["id"] for c in summary["charts"]} >= {"E1_matchups", "E1_E2_winrate"}
    assert (tmp_path / "plots" / "E1_matchups.png").exists()
    assert "Random" in (tmp_path / "tables.md").read_text(encoding="utf-8")
