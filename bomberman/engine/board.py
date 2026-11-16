"""Generowanie planszy i stanu początkowego z seeda."""

from __future__ import annotations

import random

from bomberman.config import GameConfig
from bomberman.engine.state import BOX, EMPTY, WALL, GameState, Obstacle, Player


def start_positions(cfg: GameConfig) -> list[tuple[int, int]]:
    return [(1, 1), (cfg.width - 2, cfg.height - 2)]


def obstacle_rows(cfg: GameConfig) -> tuple[int, int]:
    """Wiersze torów ruchomych przeszkód: nieparzyste (bez filarów), symetryczne względem środka."""
    y1 = cfg.height // 2 - 1
    if y1 % 2 == 0:
        y1 -= 1
    return y1, cfg.height - 1 - y1


def generate_grid(cfg: GameConfig, rng: random.Random) -> list[int]:
    w, h = cfg.width, cfg.height
    grid = [EMPTY] * (w * h)
    for y in range(h):
        for x in range(w):
            border = x in (0, w - 1) or y in (0, h - 1)
            if border or (x % 2 == 0 and y % 2 == 0):
                grid[y * w + x] = WALL

    keep_free: set[tuple[int, int]] = set()
    for sx, sy in start_positions(cfg):
        keep_free.add((sx, sy))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            keep_free.add((sx + dx, sy + dy))
    if cfg.physics.moving_obstacles:
        for row in obstacle_rows(cfg):
            keep_free.update((x, row) for x in range(w))

    for y in range(1, h - 1):
        for x in range(1, w - 1):
            i = y * w + x
            mx, my = w - 1 - x, h - 1 - y
            j = my * w + mx
            if i > j or grid[i] != EMPTY:
                continue
            if (x, y) in keep_free or (mx, my) in keep_free:
                continue
            if rng.random() < cfg.box_density:
                grid[i] = BOX
                grid[j] = BOX
    return grid


def from_layout(rows: list[str]) -> GameState:
    """Stan z rysunku: `#` ściana, `+` skrzynia, `.` wolne, `A`/`B` gracze 0/1 (do testów i scenariuszy)."""
    h, w = len(rows), len(rows[0])
    grid = [EMPTY] * (w * h)
    found: dict[str, tuple[int, int]] = {}
    for y, row in enumerate(rows):
        if len(row) != w:
            raise ValueError("Wszystkie wiersze muszą mieć tę samą długość.")
        for x, ch in enumerate(row):
            if ch == "#":
                grid[y * w + x] = WALL
            elif ch == "+":
                grid[y * w + x] = BOX
            elif ch in "AB":
                found[ch] = (x, y)
            elif ch != ".":
                raise ValueError(f"Nieznany znak {ch!r}")
    players = []
    for pid, ch in enumerate("AB"):
        x, y = found.get(ch, (0, 0))
        players.append(Player(pid, float(x), float(y), alive=ch in found))
    return GameState(w, h, grid, players, [], [], {}, {})


def new_game(cfg: GameConfig, seed: int) -> GameState:
    rng = random.Random(seed)
    grid = generate_grid(cfg, rng)
    players = [Player(pid, float(x), float(y)) for pid, (x, y) in enumerate(start_positions(cfg))]
    obstacles: list[Obstacle] = []
    if cfg.physics.moving_obstacles:
        y1, y2 = obstacle_rows(cfg)
        u = cfg.physics.obstacle_speed
        x1 = cfg.width // 2
        obstacles = [
            Obstacle(0, float(x1), float(y1), u, 0.0),
            Obstacle(1, float(cfg.width - 1 - x1), float(y2), -u, 0.0),
        ]
    return GameState(cfg.width, cfg.height, grid, players, [], obstacles, {}, {})
