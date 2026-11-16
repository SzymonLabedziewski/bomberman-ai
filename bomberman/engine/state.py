"""Stan gry i podstawowe typy. To jest kontrakt między silnikiem, botami i serwerem."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

EMPTY, WALL, BOX = 0, 1, 2

# flame_info: bity 0-1 właściciele bomb, bit 2 bomba ruszona przez fizykę
PHYSICS_BIT = 4

Cell = int  # indeks pola w spłaszczonej siatce: y * width + x
Event = dict[str, Any]


class Action(IntEnum):
    STAY = 0
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4
    BOMB = 5


DIRECTIONS: dict[Action, tuple[int, int]] = {
    Action.UP: (0, -1),
    Action.DOWN: (0, 1),
    Action.LEFT: (-1, 0),
    Action.RIGHT: (1, 0),
}
MOVES = (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT)
DIR4 = ((0, -1), (0, 1), (-1, 0), (1, 0))


def move_between(src: Cell, dst: Cell, width: int) -> Action:
    """Ruch z pola `src` na sąsiednie pole `dst`; STAY, gdy pola nie sąsiadują."""
    d = dst - src
    if d == -width:
        return Action.UP
    if d == width:
        return Action.DOWN
    if d == -1:
        return Action.LEFT
    if d == 1:
        return Action.RIGHT
    return Action.STAY


@dataclass(slots=True)
class Player:
    id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    alive: bool = True
    bombs_used: int = 0
    knocked_tick: int = -1000

    @property
    def cell(self) -> tuple[int, int]:
        return int(self.x + 0.5), int(self.y + 0.5)

    @property
    def stunned(self) -> bool:
        return self.vx != 0.0 or self.vy != 0.0

    def copy(self) -> Player:
        return Player(self.id, self.x, self.y, self.vx, self.vy, self.alive,
                      self.bombs_used, self.knocked_tick)


@dataclass(slots=True)
class Bomb:
    id: int
    owner: int
    x: float
    y: float
    timer: int
    radius: int
    vx: float = 0.0
    vy: float = 0.0
    moved: bool = False

    @property
    def cell(self) -> tuple[int, int]:
        return int(self.x + 0.5), int(self.y + 0.5)

    @property
    def moving(self) -> bool:
        return self.vx != 0.0 or self.vy != 0.0

    def copy(self) -> Bomb:
        return Bomb(self.id, self.owner, self.x, self.y, self.timer, self.radius,
                    self.vx, self.vy, self.moved)


@dataclass(slots=True)
class Obstacle:
    id: int
    x: float
    y: float
    vx: float
    vy: float

    def copy(self) -> Obstacle:
        return Obstacle(self.id, self.x, self.y, self.vx, self.vy)


@dataclass(slots=True)
class GameState:
    width: int
    height: int
    grid: list[int]
    players: list[Player]
    bombs: list[Bomb]
    obstacles: list[Obstacle]
    flames: dict[Cell, int]
    flame_info: dict[Cell, int]
    tick: int = 0
    next_bomb_id: int = 0
    done: bool = False
    winner: int | None = None  # 0 lub 1, -1 oznacza remis, None trwającą grę

    def idx(self, x: int, y: int) -> Cell:
        return y * self.width + x

    def xy(self, cell: Cell) -> tuple[int, int]:
        return cell % self.width, cell // self.width

    def player_cell(self, pid: int) -> Cell:
        p = self.players[pid]
        return int(p.y + 0.5) * self.width + int(p.x + 0.5)

    def clone(self) -> GameState:
        return GameState(
            self.width, self.height, self.grid[:],
            [p.copy() for p in self.players],
            [b.copy() for b in self.bombs],
            [o.copy() for o in self.obstacles],
            dict(self.flames), dict(self.flame_info),
            self.tick, self.next_bomb_id, self.done, self.winner,
        )
