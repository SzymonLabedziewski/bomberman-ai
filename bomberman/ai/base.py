"""Wspólny interfejs botów."""

from __future__ import annotations

import random
from typing import Any, Protocol

from bomberman.config import GameConfig
from bomberman.engine.state import Action, GameState


class Bot(Protocol):
    name: str
    debug: dict[str, Any]

    def act(self, state: GameState, me: int) -> Action: ...


class BaseBot:
    """Bot z własnym generatorem liczb losowych. `debug` trafia do nakładki w Godocie."""

    name = "base"

    def __init__(self, cfg: GameConfig, seed: int = 0) -> None:
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.debug: dict[str, Any] = {}

    def act(self, state: GameState, me: int) -> Action:
        raise NotImplementedError
