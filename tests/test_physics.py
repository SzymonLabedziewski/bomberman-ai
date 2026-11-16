import math
from dataclasses import replace

import pytest

from bomberman.ai.danger import _snapshot
from bomberman.config import GameConfig
from bomberman.engine import physics
from bomberman.engine.board import from_layout, new_game
from bomberman.engine.rules import legal_actions, step
from bomberman.engine.state import EMPTY, Action, Bomb, Obstacle
from bomberman.match import make_bots
from tests.conftest import OPEN_9, put

STAY2 = (Action.STAY, Action.STAY)


def no_friction(cfg: GameConfig) -> GameConfig:
    return replace(cfg, physics=replace(cfg.physics, friction=0.0))


def bomb(bid: int, x: int, y: int, vx: float = 0.0, vy: float = 0.0, timer: int = 99) -> Bomb:
    return Bomb(bid, 0, float(x), float(y), timer, 2, vx, vy, moved=bool(vx or vy))


def kinetic(state, cfg) -> float:
    ph = cfg.physics
    total = sum(0.5 * ph.mass_bomb * (b.vx ** 2 + b.vy ** 2) for b in state.bombs)
    return total + sum(0.5 * ph.mass_player * (p.vx ** 2 + p.vy ** 2) for p in state.players if p.alive)


@pytest.mark.parametrize("v0", [0.4, 1.5, 2.3])
def test_braking_distance_does_not_depend_on_tick_split(v0):
    mu = 0.15
    expected = v0 * v0 / (2 * mu)
    for dt in (1.0, 0.5, 0.3):
        speed, total = v0, 0.0
        while speed > 0:
            dist, speed = physics.travel(speed, dt, mu)
            total += dist
        assert total == pytest.approx(expected)


def test_kicked_bomb_slides_with_friction_and_snaps_to_cell(phys_cfg):
    cfg = replace(phys_cfg, physics=replace(phys_cfg.physics, kick_speed=1.2))
    rows = ["#" * 15, "#" + "." * 13 + "#", "#" * 15]
    state = from_layout(put(rows, A=(1, 1)))
    state.bombs.append(bomb(0, 2, 1))
    step(state, (Action.RIGHT, Action.STAY), cfg)
    b = state.bombs[0]
    assert state.players[0].cell == (1, 1)
    assert b.moved and b.vx == pytest.approx(1.2 - 0.15)
    assert b.x == pytest.approx(2 + 1.2 - 0.15 / 2)
    ticks = 1
    while b.vx:
        physics.update(state, cfg, None)
        ticks += 1
    assert ticks == 8
    assert b.x == 7.0  # droga hamowania 1.2^2 / (2 * 0.15) = 4.8, więc bomba staje nad polem 7


def test_kick_event_and_no_kick_without_flag(cfg, phys_cfg):
    state = from_layout(put(OPEN_9, A=(1, 1)))
    state.bombs.append(bomb(0, 2, 1))
    assert Action.RIGHT not in legal_actions(state, 0, cfg)
    assert Action.RIGHT in legal_actions(state, 0, phys_cfg)
    basic = state.clone()
    step(basic, (Action.RIGHT, Action.STAY), cfg)
    assert basic.bombs[0].x == 2.0 and basic.players[0].cell == (1, 1)
    events = step(state, (Action.RIGHT, Action.STAY), phys_cfg)
    assert any(e["type"] == "kick" and e["bomb"] == 0 for e in events)


def test_cannot_kick_bomb_under_other_player(phys_cfg):
    state = from_layout(put(OPEN_9, A=(1, 1), B=(2, 1)))
    state.bombs.append(bomb(0, 2, 1))
    step(state, (Action.RIGHT, Action.STAY), phys_cfg)
    assert state.bombs[0].vx == 0.0 and state.players[0].cell == (1, 1)


def test_wall_bounce_uses_exact_contact_time_and_restitution(phys_cfg):
    state = from_layout(OPEN_9)
    state.bombs.append(bomb(0, 6, 1, vx=1.5))
    physics.update(state, phys_cfg, None)
    mu, e = 0.15, 0.5
    tc = physics.time_to(1.0, 1.5, mu)
    v_contact = 1.5 - mu * tc
    dist, v_end = physics.travel(e * v_contact, 1.0 - tc, mu)
    b = state.bombs[0]
    assert v_contact == pytest.approx(math.sqrt(1.5 ** 2 - 2 * mu))
    assert b.x == pytest.approx(7.0 - dist)
    assert b.vx == pytest.approx(-v_end)


def test_equal_masses_exchange_velocity_like_newtons_cradle(phys_cfg):
    cfg = no_friction(phys_cfg)
    state = from_layout(OPEN_9)
    state.bombs += [bomb(0, 1, 1, vx=1.5), bomb(1, 3, 1)]
    p0 = sum(b.vx for b in state.bombs)
    e0 = kinetic(state, cfg)
    physics.update(state, cfg, None)
    first, second = state.bombs
    assert first.vx == 0.0 and first.x == 2.0
    assert second.vx == pytest.approx(1.5)
    assert second.x == pytest.approx(4.5)  # uderzona bomba ma wyższe id, więc rusza w tym samym ticku
    assert sum(b.vx for b in state.bombs) == pytest.approx(p0)
    assert kinetic(state, cfg) == pytest.approx(e0)


def test_sliding_player_hits_bomb_with_momentum_and_energy_conserved(phys_cfg):
    cfg = no_friction(phys_cfg)
    state = from_layout(put(OPEN_9, A=(1, 1)))
    state.players[0].vx = 1.2
    state.bombs.append(bomb(0, 3, 1))
    ph = cfg.physics
    p0 = ph.mass_player * 1.2
    e0 = kinetic(state, cfg)
    physics.update(state, cfg, None)
    player, b = state.players[0], state.bombs[0]
    assert player.vx == pytest.approx(1.2 / 3)
    assert b.vx == pytest.approx(1.2 * 4 / 3)
    assert ph.mass_player * player.vx + ph.mass_bomb * b.vx == pytest.approx(p0)
    assert kinetic(state, cfg) == pytest.approx(e0)
    assert b.moved


def test_standing_player_stops_bomb(phys_cfg):
    state = from_layout(put(OPEN_9, B=(5, 1)))
    state.bombs.append(bomb(0, 1, 1, vx=1.5))
    for _ in range(5):
        physics.update(state, phys_cfg, None)
    b = state.bombs[0]
    assert (b.x, b.vx) == (4.0, 0.0)
    assert state.players[1].cell == (5, 1) and not state.players[1].stunned


def test_at_most_four_collisions_per_tick(phys_cfg):
    cfg = replace(phys_cfg, physics=replace(phys_cfg.physics, friction=0.0, restitution_wall=1.0))
    rows = ["#####", "#...#", "#####"]
    state = from_layout(rows)
    state.bombs.append(bomb(0, 2, 1, vx=30.0))
    events = []
    physics.update(state, cfg, events)
    assert len([e for e in events if e["type"] == "collision"]) == physics.MAX_HITS


def test_knockback_impulse_mass_and_stun(phys_cfg):
    rows = put(OPEN_9, A=(4, 1), B=(7, 7))
    state = from_layout(rows)
    state.bombs += [Bomb(0, 1, 1.0, 1.0, 1, 2), bomb(1, 1, 5)]
    events = step(state, STAY2, phys_cfg)
    j3 = 4.0 * (1 - 3 / 5)
    j4 = 4.0 * (1 - 4 / 5)
    a = state.players[0]
    assert a.alive and a.vx == pytest.approx(j3 / 2.0) and a.stunned
    assert a.knocked_tick == 0
    assert legal_actions(state, 0, phys_cfg) == [Action.STAY]
    other = state.bombs[0]
    assert other.vy == pytest.approx(j4 / 1.0) and other.moved
    assert {e.get("player", e.get("bomb")) for e in events if e["type"] == "knock"} == {0, 1}


def test_knockback_only_along_open_directions(phys_cfg):
    rows = put(OPEN_9, A=(4, 1), B=(7, 7), **{"+": (3, 1)})
    state = from_layout(rows)
    state.bombs.append(Bomb(0, 1, 1.0, 1.0, 1, 2))
    step(state, STAY2, phys_cfg)
    assert not state.players[0].stunned


def test_knockback_wave_blocked_by_box_beyond_radius(phys_cfg):
    rows = put(OPEN_9, A=(5, 1), B=(7, 7), **{"+": (4, 1)})
    state = from_layout(rows)
    state.bombs.append(Bomb(0, 1, 1.0, 1.0, 1, 2))
    step(state, STAY2, phys_cfg)
    assert not state.players[0].stunned


@pytest.mark.parametrize("bomb_x,player_x", [(1, 4), (11, 8), (11, 7)])
def test_predicted_slide_matches_engine(phys_cfg, bomb_x, player_x):
    rows = ["#" * 13, "#" + "." * 11 + "#", "#" * 13]
    state = from_layout(put(rows, A=(player_x, 1)))
    state.bombs.append(Bomb(0, 1, float(bomb_x), 1.0, 1, 2))
    step(state, STAY2, phys_cfg)
    start = state.player_cell(0)
    direction = (1, 0) if player_x > bomb_x else (-1, 0)
    blast = [(bomb_x, 1, 2, [direction])]
    knocks = {c: (dx, dy, j) for c, dx, dy, j in physics.knock_targets(state, phys_cfg, blast)}
    predicted = physics.slide_cells(start, knocks[start], phys_cfg, _snapshot(state, {}), state.width)
    actual = []
    while state.players[0].stunned:
        step(state, STAY2, phys_cfg)
        actual.append(state.player_cell(0))
    assert predicted == actual
    assert state.players[0].x == float(state.players[0].cell[0])


def test_knocked_player_can_be_pushed_into_fire(phys_cfg):
    rows = put(OPEN_9, A=(4, 1), B=(7, 7))
    state = from_layout(rows)
    state.bombs += [Bomb(0, 1, 1.0, 1.0, 1, 2), Bomb(1, 1, 5.0, 3.0, 2, 2)]
    step(state, STAY2, phys_cfg)
    events = step(state, STAY2, phys_cfg)
    assert not state.players[0].alive
    death = next(e for e in events if e["type"] == "death")
    assert death["player"] == 0 and death["physics"]


def obstacle_state(x: float, *bombs: Bomb) -> tuple:
    state = from_layout(OPEN_9)
    state.obstacles.append(Obstacle(0, x, 3.0, 0.5, 0.0))
    state.bombs += list(bombs)
    return state, state.obstacles[0]


def test_obstacle_moves_and_reverses_before_wall(phys_cfg):
    state, o = obstacle_state(6.0)
    xs = []
    for _ in range(4):
        physics.update(state, phys_cfg, None)
        xs.append((o.x, o.vx))
    assert xs == [(6.5, 0.5), (7.0, 0.5), (7.0, -0.5), (6.5, -0.5)]
    assert physics.obstacle_cells(Obstacle(0, 6.5, 3.0, 0.5, 0.0), 9) == (3 * 9 + 6, 3 * 9 + 7)


def test_obstacle_pushes_bomb(phys_cfg):
    state, o = obstacle_state(5.0, bomb(0, 6, 3))
    events = []
    physics.update(state, phys_cfg, events)
    b = state.bombs[0]
    assert any(e["type"] == "push" for e in events)
    e = phys_cfg.physics.restitution_wall
    v = (1 + e) * 0.5
    assert b.moved and b.x == pytest.approx(6 + physics.travel(v, 1.0, 0.15)[0])
    assert o.x == 5.5


def test_obstacle_reverses_when_bomb_cannot_move(phys_cfg):
    state, o = obstacle_state(6.0, bomb(0, 7, 3))
    physics.update(state, phys_cfg, None)
    assert (o.x, o.vx) == (6.0, -0.5)
    assert state.bombs[0].vx == 0.0


def test_obstacle_blocks_players(phys_cfg):
    state, o = obstacle_state(3.0)
    state.players[0].alive = True
    state.players[0].x, state.players[0].y = 1.0, 3.0
    assert Action.RIGHT in legal_actions(state, 0, phys_cfg)
    o.x = 2.0
    assert Action.RIGHT not in legal_actions(state, 0, phys_cfg)


@pytest.mark.parametrize("seed", range(12))
def test_random_physics_games_keep_invariants_and_are_deterministic(phys_cfg, seed):
    def run():
        state = new_game(phys_cfg, seed)
        bots = make_bots(["random", "random"], phys_cfg, seed)
        w = state.width
        while not state.done:
            actions = [b.act(state, pid) for pid, b in enumerate(bots)]
            step(state, actions, phys_cfg)
            blocked = set()
            for ob in state.obstacles:
                cells = physics.obstacle_cells(ob, w)
                assert all(state.grid[c] == EMPTY for c in cells)
                blocked.update(cells)
            for body in [*state.bombs, *(p for p in state.players if p.alive)]:
                assert not (body.vx and body.vy)
                cell = int(body.y + 0.5) * w + int(body.x + 0.5)
                assert state.grid[cell] == EMPTY
                if not (body.vx or body.vy):
                    assert body.x == int(body.x) and body.y == int(body.y)
            for p in state.players:
                if p.alive:
                    assert state.player_cell(p.id) not in blocked
        return state

    a, b = run(), run()
    assert (a.tick, a.winner) == (b.tick, b.winner)
    assert [(p.x, p.y, p.alive) for p in a.players] == [(p.x, p.y, p.alive) for p in b.players]
