import pytest

from bomberman.config import GameConfig

OPEN_9 = [
    "#########",
    "#.......#",
    "#.#.#.#.#",
    "#.......#",
    "#.#.#.#.#",
    "#.......#",
    "#.#.#.#.#",
    "#.......#",
    "#########",
]


def put(rows: list[str], **marks: tuple[int, int] | list[tuple[int, int]]) -> list[str]:
    """Kopia planszy z wstawionymi znakami, np. put(OPEN_9, A=(1, 1), **{"+": [(2, 1), (1, 2)]})."""
    grid = [list(r) for r in rows]
    for ch, where in marks.items():
        for x, y in [where] if isinstance(where, tuple) else where:
            grid[y][x] = ch[0]
    return ["".join(r) for r in grid]


@pytest.fixture
def cfg() -> GameConfig:
    return GameConfig()


@pytest.fixture
def phys_cfg() -> GameConfig:
    return GameConfig().with_physics(True)
