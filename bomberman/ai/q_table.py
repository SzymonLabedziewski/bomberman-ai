"""Tablica Q: zapis/odczyt JSON, domyślne Q=0, zliczanie odwiedzin do scalania."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bomberman.engine.state import Action

MODELS_DIR = Path(__file__).resolve().parent / "models"
DEFAULT_TABLE_PATH = MODELS_DIR / "q_pure.json"
DEFAULT_PHYSICS_TABLE_PATH = MODELS_DIR / "q_pure_physics.json"


class QTable:
    """Słownik state_key -> {action_name -> float}; osobno visits[state][action]."""

    def __init__(self, data: dict[str, dict[str, float]] | None = None,
                 visits: dict[str, dict[str, int]] | None = None) -> None:
        self.data: dict[str, dict[str, float]] = data or {}
        self.visits: dict[str, dict[str, int]] = visits or {}

    def get(self, state_key: str, action: str) -> float:
        row = self.data.get(state_key)
        if not row:
            return 0.0
        return float(row.get(action, 0.0))

    def set(self, state_key: str, action: str, value: float) -> None:
        self.data.setdefault(state_key, {})[action] = float(value)

    def touch(self, state_key: str, action: str) -> None:
        row = self.visits.setdefault(state_key, {})
        row[action] = row.get(action, 0) + 1

    def best_action(self, state_key: str, legal: list[Action]) -> Action:
        """Pierwsza akcja z `legal` o najwyższym Q (prawie równe wartości traktuje jak remis)."""
        best, best_v = Action.STAY, None
        for a in legal:
            v = self.get(state_key, a.name)
            if best_v is None or v > best_v + 1e-12:
                best, best_v = a, v
        return best

    def max_value(self, state_key: str, legal: list[Action]) -> float:
        if not legal:
            return 0.0
        return max(self.get(state_key, a.name) for a in legal)

    def values_for(self, state_key: str, legal: list[Action]) -> dict[str, float]:
        return {a.name: round(self.get(state_key, a.name), 4) for a in legal}

    def update(self, state_key: str, action: str, reward: float, next_key: str,
               next_legal: list[Action], alpha: float, gamma: float, done: bool) -> float:
        """Jedna aktualizacja TD. Zwraca nową wartość Q."""
        old = self.get(state_key, action)
        future = 0.0 if done else self.max_value(next_key, next_legal)
        new = old + alpha * (reward + gamma * future - old)
        self.set(state_key, action, new)
        self.touch(state_key, action)
        return new

    @property
    def n_states(self) -> int:
        return len(self.data)

    def merge_from(self, other: QTable) -> None:
        """Scala inną tablicę: średnia ważona liczbą odwiedzin."""
        for sk, row in other.data.items():
            for action, q in row.items():
                v_other = int(other.visits.get(sk, {}).get(action, 1))
                v_self = int(self.visits.get(sk, {}).get(action, 0))
                if v_self <= 0:
                    self.set(sk, action, q)
                    self.visits.setdefault(sk, {})[action] = v_other
                else:
                    total = v_self + v_other
                    mixed = (self.get(sk, action) * v_self + q * v_other) / total
                    self.set(sk, action, mixed)
                    self.visits.setdefault(sk, {})[action] = total

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "q": self.data, "visits": self.visits}, f,
                      ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def load(cls, path: Path | str) -> QTable:
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)
        data = raw.get("q", raw)
        visits = raw.get("visits") or {}
        q = {k: {a: float(v) for a, v in row.items()} for k, row in data.items()}
        vis = {k: {a: int(v) for a, v in row.items()} for k, row in visits.items()}
        return cls(q, vis)
