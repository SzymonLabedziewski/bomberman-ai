import pytest

from bomberman.ai.base import BaseBot
from bomberman.ai.montecarlo_bot import MonteCarloBot
from bomberman.ai.registry import BOT_NAMES, make_bot
from bomberman.engine import Action, Bomb, from_layout, legal_actions, new_game, step
from tests.conftest import OPEN_9, put

FAST_PARAMS = {"montecarlo": {"rollouts": 6, "depth": 6}}


class StayBot(BaseBot):
    name = "stay"

    def act(self, state, me):
        return Action.STAY


def play(cfg, bot0, bot1, seed, max_ticks=200):
    s = new_game(cfg, seed)
    deaths = []
    while not s.done and s.tick < max_ticks:
        acts = [bot0.act(s, 0), bot1.act(s, 1)]
        for pid in (0, 1):
            assert acts[pid] in legal_actions(s, pid, cfg), f"{acts[pid]} nielegalna dla gracza {pid}"
        deaths += [e for e in step(s, acts, cfg) if e["type"] == "death"]
    return s, deaths


@pytest.mark.parametrize("name", BOT_NAMES)
def test_bots_return_legal_actions(cfg, name):
    for seed in range(3):
        bot = make_bot(name, cfg, seed, **FAST_PARAMS.get(name, {}))
        play(cfg, bot, make_bot("randomsafe", cfg, seed + 100), seed, max_ticks=60)


def test_planner_survives_own_bombs_and_kills_static_target(cfg):
    wins = 0
    for seed in range(6):
        s, deaths = play(cfg, make_bot("planner", cfg, seed), StayBot(cfg), seed)
        assert s.players[0].alive, f"Planner zginął (seed {seed}): {deaths}"
        wins += s.winner == 0
    assert wins >= 4


def test_planner_beats_random_safe(cfg):
    results = [play(cfg, make_bot("planner", cfg, seed), make_bot("randomsafe", cfg, seed), seed)[0].winner
               for seed in range(10)]
    assert results.count(0) >= 7


def test_montecarlo_avoids_certain_suicide(cfg):
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7), **{"+": [(2, 1), (1, 2)]}))
    bot = MonteCarloBot(cfg, seed=1, rollouts=10, depth=8)
    assert bot.act(s, 0) == Action.STAY
    values = bot.debug["values"]
    assert values["BOMB"] <= -0.5, "zamknięty gracz ginie od własnej bomby (0 tylko, gdy zginie też rywal)"
    assert values["BOMB"] < values["STAY"]


def test_montecarlo_escapes_from_bomb(cfg):
    for seed in range(5):
        s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
        s.bombs.append(Bomb(0, 1, 1.0, 2.0, 2, 2))
        s.players[1].bombs_used = 1
        bot = MonteCarloBot(cfg, seed=seed, rollouts=10, depth=6)
        for _ in range(3):
            step(s, [bot.act(s, 0), Action.STAY], cfg)
        assert s.players[0].alive, f"Monte Carlo nie uciekł (seed {seed})"


def test_montecarlo_is_deterministic_for_seed(cfg):
    s = new_game(cfg, 3)
    a = MonteCarloBot(cfg, seed=7, rollouts=5, depth=4)
    b = MonteCarloBot(cfg, seed=7, rollouts=5, depth=4)
    for _ in range(10):
        x, y = a.act(s, 0), b.act(s, 0)
        assert x == y and a.debug == b.debug
        step(s, [x, Action.STAY], cfg)


def test_randomsafe_refuses_corner_bomb_without_escape(cfg):
    """BOMB w narożniku bez drogi ucieczki jest odrzucany."""
    from bomberman.ai.baselines import RandomSafeBot

    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7), **{"+": [(2, 1), (1, 2)]}))
    bot = RandomSafeBot(cfg, seed=0)
    for seed in range(40):
        bot.rng.seed(seed)
        assert bot.act(s, 0) != Action.BOMB


def test_randomsafe_does_not_walk_back_into_own_bomb(cfg):
    """RandomSafe nie ginie od własnej bomby."""
    from bomberman.ai.baselines import RandomSafeBot

    for seed in range(25):
        s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
        s.bombs.append(Bomb(0, 0, 1.0, 1.0, 5, 2))
        s.players[0].bombs_used = 1
        bot = RandomSafeBot(cfg, seed=seed)
        for _ in range(7):
            a = bot.act(s, 0)
            step(s, [a, Action.STAY], cfg)
        assert s.players[0].alive, f"RandomSafe zabił się od własnej bomby (seed={seed})"


def test_planners_do_not_deadlock_on_same_tile(cfg):
    """Gracze nie blokują się w nieskończoność na wspólnym polu."""
    from bomberman.ai.planner_bot import PlannerBot

    # Między graczami jest jedno wolne pole (4,3), na które obaj chcą wejść.
    s = from_layout(put(OPEN_9, A=(3, 3), B=(5, 3)))
    a = PlannerBot(cfg, seed=1)
    b = PlannerBot(cfg, seed=2)
    start = (s.player_cell(0), s.player_cell(1))
    w = s.width
    delta = {Action.UP: -w, Action.DOWN: w, Action.LEFT: -1, Action.RIGHT: 1}
    progressed = False
    for _ in range(12):
        acts = [a.act(s, 0), b.act(s, 1)]
        if acts[0] in delta and acts[1] in delta:
            t0 = s.player_cell(0) + delta[acts[0]]
            t1 = s.player_cell(1) + delta[acts[1]]
            assert t0 != t1, f"oba Plannery celują w {t0}"
        before_bombs = len(s.bombs)
        step(s, acts, cfg)
        if (s.player_cell(0), s.player_cell(1)) != start or len(s.bombs) != before_bombs:
            progressed = True
            break
        if s.done:
            break
    assert progressed, "Plannery zablokowały się (brak postępu przez 12 ticków)"
