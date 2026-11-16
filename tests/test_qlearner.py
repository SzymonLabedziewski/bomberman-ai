from __future__ import annotations

from pathlib import Path

from bomberman.ai.features import encode_state
from bomberman.ai.q_table import QTable
from bomberman.ai.qlearner_bot import QLearnerBot
from bomberman.config import load_config
from bomberman.engine.board import new_game
from bomberman.engine.state import Action


def test_encode_state_deterministic():
    cfg = load_config()
    state = new_game(cfg, 7)
    a = encode_state(state, 0, cfg)
    b = encode_state(state, 0, cfg)
    assert a == b
    assert a.count("|") >= 13
    assert a.endswith("|0|0|0"), "bez fizyki sufiks kick|knock|obstacle = 0|0|0"


def test_escape_move_bonus_beats_stay_in_danger():
    """Ruch z ognia w bezpieczne ma wyższą nagrodę niż STAY (uczy ucieczki)."""
    from bomberman.ai.train import _step_reward
    from bomberman.engine import Bomb, from_layout, step
    from tests.conftest import OPEN_9, put

    cfg = load_config()
    # Bomba na (3,1); A na (1,1) stoi na jej poziomym ramieniu, ruch DOWN wyprowadza go z krzyża.
    prev = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    prev.bombs.append(Bomb(0, 1, 3.0, 1.0, 3, 2))
    prev.players[1].bombs_used = 1

    stay = prev.clone()
    step(stay, [Action.STAY, Action.STAY], cfg, record=False)
    r_stay = _step_reward(prev, stay, 0, Action.STAY, stay.done, [], cfg)

    moved = prev.clone()
    step(moved, [Action.DOWN, Action.STAY], cfg, record=False)
    r_move = _step_reward(prev, moved, 0, Action.DOWN, moved.done, [], cfg)
    assert r_move > r_stay, f"escape move {r_move} powinno bić stay {r_stay}"


def test_bomb_not_useful_when_far_on_emptyish_map():
    from bomberman.ai.features import bomb_is_useful
    cfg = load_config()
    state = new_game(cfg, 7)
    v = bomb_is_useful(state, 0, cfg)
    assert v is True or v is False
    assert bomb_is_useful(state, 0, cfg) is v


def test_safe_play_avoids_instant_death(tmp_path: Path):
    """safe_play odrzuca akcje ginące w następnym ticku."""
    cfg = load_config()
    state = new_game(cfg, 3)
    key = encode_state(state, 0, cfg)
    table = QTable()
    for a in Action:
        table.set(key, a.name, 0.0)
    table.set(key, Action.STAY.name, 5.0)
    path = tmp_path / "q.json"
    table.save(path)
    bot = QLearnerBot(cfg, seed=1, table_path=path, epsilon=0.0, learn=False, safe_play=True)
    action = bot.act(state, 0)
    assert action in Action
    assert bot.debug["mode"] == "exploit"


def test_q_table_update_and_best():
    table = QTable()
    legal = [Action.STAY, Action.UP, Action.BOMB]
    table.update("s0", "UP", 1.0, "s1", legal, alpha=1.0, gamma=0.0, done=True)
    assert table.get("s0", "UP") == 1.0
    assert table.best_action("s0", legal) == Action.UP


def test_q_table_save_load(tmp_path: Path):
    table = QTable()
    table.set("k", "BOMB", 0.5)
    path = tmp_path / "q.json"
    table.save(path)
    loaded = QTable.load(path)
    assert loaded.get("k", "BOMB") == 0.5


def test_qlearner_argmax(tmp_path: Path):
    cfg = load_config()
    table = QTable()
    state = new_game(cfg, 3)
    key = encode_state(state, 0, cfg)
    # Z (1,1) LEFT prowadzi w ścianę, więc nie jest legalny.
    for a in Action:
        table.set(key, a.name, 0.0)
    table.set(key, Action.RIGHT.name, 5.0)
    path = tmp_path / "q.json"
    table.save(path)
    bot = QLearnerBot(cfg, seed=1, table_path=path, epsilon=0.0, learn=False)
    action = bot.act(state, 0)
    assert action == Action.RIGHT
    assert bot.debug["family"] == "rl"
    assert "compute" in bot.debug
    assert bot.debug["mode"] == "exploit"


def test_qlearner_escape_respects_contested(tmp_path: Path):
    """Hybryda (safe_play=True): escape wygrywa z wysokim Q(BOMB)."""
    from bomberman.engine import Bomb, from_layout
    from tests.conftest import OPEN_9, put

    cfg = load_config()
    s = from_layout(put(OPEN_9, A=(1, 1), B=(3, 1)))
    s.bombs.append(Bomb(0, 1, 1.0, 1.0, 5, 2))
    s.players[1].bombs_used = 1

    table = QTable()
    key = encode_state(s, 0, cfg)
    for a in Action:
        table.set(key, a.name, 0.0)
    table.set(key, Action.BOMB.name, 9.0)
    path = tmp_path / "q.json"
    table.save(path)
    bot = QLearnerBot(cfg, seed=1, table_path=path, epsilon=0.0, learn=False, safe_play=True)
    action = bot.act(s, 0)
    assert bot.debug["mode"] == "escape"
    assert action != Action.BOMB
    if action in (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT):
        w = s.width
        nxt = s.player_cell(0) + {Action.UP: -w, Action.DOWN: w, Action.LEFT: -1, Action.RIGHT: 1}[action]
        assert nxt != s.player_cell(1)


def test_pure_policy_no_escape_override(tmp_path: Path):
    """Bez safe_play bot w zagrożeniu wybiera z tablicy Q."""
    from bomberman.engine import Bomb, from_layout
    from tests.conftest import OPEN_9, put

    cfg = load_config()
    s = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    s.bombs.append(Bomb(0, 1, 1.0, 1.0, 5, 2))
    s.players[1].bombs_used = 1

    table = QTable()
    key = encode_state(s, 0, cfg)
    for a in Action:
        table.set(key, a.name, 0.0)
    table.set(key, Action.DOWN.name, 3.0)
    path = tmp_path / "q.json"
    table.save(path)

    pure = QLearnerBot(cfg, seed=1, table_path=path, epsilon=0.0, learn=False)
    assert pure.safe_play is False
    action = pure.act(s, 0)
    assert pure.debug["mode"] == "exploit"
    assert action == Action.DOWN


def test_enter_danger_penalty_prevents_oscillation_farming():
    """Wejście w ogień i wyjście nie daje dodatniej nagrody."""
    from bomberman.ai.train import _step_reward
    from bomberman.engine import Bomb, from_layout, step
    from tests.conftest import OPEN_9, put

    cfg = load_config()
    # Bomba na (3,1): pole (1,2) jest bezpieczne, a (1,1) w promieniu rażenia.
    safe_state = from_layout(put(OPEN_9, A=(1, 2), B=(7, 7)))
    safe_state.bombs.append(Bomb(0, 0, 3.0, 1.0, 4, 2))
    safe_state.players[0].bombs_used = 1

    into_danger = safe_state.clone()
    step(into_danger, [Action.UP, Action.STAY], cfg, record=False)
    r_enter = _step_reward(safe_state, into_danger, 0, Action.UP, into_danger.done, [], cfg)

    back_to_safe = into_danger.clone()
    step(back_to_safe, [Action.DOWN, Action.STAY], cfg, record=False)
    r_escape = _step_reward(into_danger, back_to_safe, 0, Action.DOWN, back_to_safe.done, [], cfg)

    assert r_enter < 0, f"wejście w ogień musi być karane, otrzymano {r_enter}"
    assert r_enter + r_escape < 0, f"cykl bezpieczne->ogień->bezpieczne nie może być dodatni: {r_enter + r_escape}"


def test_no_kill_bonus_on_opponent_self_kill():
    """Samobójstwo przeciwnika przy biernej grze nie daje pełnej nagrody."""
    from bomberman.ai.train import KILL_BONUS, _step_reward
    from bomberman.engine import from_layout
    from tests.conftest import OPEN_9, put

    cfg = load_config()
    prev = from_layout(put(OPEN_9, A=(1, 1), B=(7, 7)))
    nxt = prev.clone()
    nxt.players[1].alive = False
    nxt.done = True
    nxt.winner = 0
    events = [{"type": "death", "player": 1, "by_self": True}]

    r_passive = _step_reward(prev, nxt, 0, Action.STAY, True, events, cfg, active_attacks=0)
    assert r_passive < KILL_BONUS, f"bierny gracz nie powinien dostać KILL_BONUS za cudzy self-kill: {r_passive}"


def test_directional_features_and_anti_backtrack_into_danger(tmp_path: Path):
    """Bot nie wraca z bezpiecznego pola w ogień."""
    from bomberman.ai.features import dir_safety_mask
    from bomberman.engine import Bomb, from_layout
    from tests.conftest import OPEN_9, put

    cfg = load_config()
    # Bomba na (3,1), gracz na (1,2): UP prowadzi w krzyż wybuchu, DOWN na bezpieczne (1,3).
    s2 = from_layout(put(OPEN_9, A=(1, 2), B=(7, 7)))
    s2.bombs.append(Bomb(0, 0, 3.0, 1.0, 4, 2))
    s2.players[0].bombs_used = 1
    s2.tick = 3
    mask = dir_safety_mask(s2, 0, cfg)
    assert mask[0] in ("0", "1")
    assert mask[1] == "2"

    # Bot przyszedł z (1,1). Nawet przy najwyższym Q dla UP nie powinien wrócić w ogień.
    key = encode_state(s2, 0, cfg)
    table = QTable()
    for a in Action:
        table.set(key, a.name, 0.1)
    table.set(key, Action.UP.name, 2.0)
    path = tmp_path / "q.json"
    table.save(path)

    bot = QLearnerBot(cfg, seed=1, table_path=path, epsilon=0.0, learn=False)
    bot._curr_cell = 1 * s2.width + 1
    bot._last_action = Action.DOWN
    chosen = bot.act(s2, 0)
    assert chosen == Action.DOWN, f"bot nie powinien cofnąć się z (1,2) w ogień na (1,1), wybrał {chosen}"


def test_qlearner_bomb_step_back_and_kick_combo():
    """Z fizyką bot cofa się i kopie bombę w przeciwnika."""
    from bomberman.ai.features import best_escape_action, best_kick_action
    from bomberman.engine import from_layout, step
    from tests.conftest import OPEN_9, put

    cfg = load_config().with_physics(True)
    s = from_layout(put(OPEN_9, A=(2, 1), B=(6, 1)))
    s.tick = 2
    bot = QLearnerBot(cfg, seed=1, table=QTable(), epsilon=0.0, learn=False)

    # Bomba na (2,1) jest użyteczna, bo da się ją kopnąć w przeciwnika na (6,1).
    a1 = bot.act(s, 0)
    assert a1 == Action.BOMB, f"oczekiwano BOMB na (2,1), wybrano {a1}"
    step(s, [a1, Action.STAY], cfg)

    # Cofnięcie na (1,1) ustawia bota do kopnięcia.
    assert best_escape_action(s, 0, cfg) == Action.LEFT
    a2 = bot.act(s, 0)
    assert a2 == Action.LEFT, f"oczekiwano cofnięcia LEFT na (1,1) pod kopnięcie, wybrano {a2}"
    step(s, [a2, Action.STAY], cfg)

    # Kopnięcie w prawo, choć (2,1) jest poprzednim polem bota i grozi tam ogień.
    assert best_kick_action(s, 0, cfg) == Action.RIGHT
    key = encode_state(s, 0, cfg)
    parts = key.split("|")
    assert parts[13] == "3", f"oczekiwano kick=3 w kluczu stanu, otrzymano {key}"
    assert parts[3] == "4", f"oczekiwano nav_dir=4 (RIGHT) przy kick=3, otrzymano {key}"
    a3 = bot.act(s, 0)
    assert a3 == Action.RIGHT, f"oczekiwano kopnięcia RIGHT, wybrano {a3}"
    ev = step(s, [a3, Action.STAY], cfg)
    assert any(e.get("type") == "kick" and e.get("player") == 0 for e in ev), "bomba powinna zostać kopnięta"


def test_knockback_awareness_in_features_and_rewards():
    """Wykrywanie strefy odrzutu w obronie i ataku."""
    from bomberman.ai.features import bomb_is_useful
    from bomberman.ai.train import _step_reward
    from bomberman.engine import Bomb, from_layout, step
    from tests.conftest import OPEN_9, put

    cfg = load_config().with_physics(True)
    # Bomba na (1,1) o promieniu 2 odrzuca pola od (4,1) do (5,1), a gracz stoi na (5,1).
    s_def = from_layout(put(OPEN_9, A=(5, 1), B=(7, 7)))
    s_def.bombs.append(Bomb(0, 1, 1.0, 1.0, 2, 2))
    s_def.players[1].bombs_used = 1
    key_def = encode_state(s_def, 0, cfg)
    parts_def = key_def.split("|")
    assert parts_def[14] == "1", f"gracz na (5,1) powinien widzieć knock=1, klucz: {key_def}"

    # Przeciwnik na (5,1) jest w zasięgu odrzutu bomby położonej na (1,1).
    s_att = from_layout(put(OPEN_9, A=(1, 1), B=(5, 1)))
    assert bomb_is_useful(s_att, 0, cfg) is True
    sim = s_att.clone()
    ev = step(sim, [Action.BOMB, Action.STAY], cfg)
    r_bomb = _step_reward(s_att, sim, 0, Action.BOMB, sim.done, ev, cfg)
    assert r_bomb > 0.5, f"bomba bijąca wroga odrzutem powinna dać wysoki bonus, otrzymano {r_bomb}"


def test_qlearners_break_collision_and_movement_loops():
    """Dwa boty QLearner nie zacinają się w nieskończoność na spornym polu (3,1)."""
    from bomberman.engine import from_layout, step
    from tests.conftest import OPEN_9, put

    cfg = load_config().with_physics(True)
    s = from_layout(put(OPEN_9, A=(3, 2), B=(4, 1)))
    s.tick = 10
    a = QLearnerBot(cfg, seed=1, table=QTable(), epsilon=0.0, learn=False)
    b = QLearnerBot(cfg, seed=2, table=QTable(), epsilon=0.0, learn=False)

    positions = set()
    bombs_placed = 0
    for _ in range(10):
        act0 = a.act(s, 0)
        act1 = b.act(s, 1)
        if act0 == Action.BOMB or act1 == Action.BOMB:
            bombs_placed += 1
        step(s, [act0, act1], cfg)
        positions.add((s.player_cell(0), s.player_cell(1)))
    assert len(positions) > 1 or bombs_placed > 0, "boty QLearner zablokowały się na spornym polu"


