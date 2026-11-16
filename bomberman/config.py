"""Konfiguracja gry i fizyki (wczytywana z plików JSON w configs/)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.json"


@dataclass(frozen=True)
class PhysicsConfig:
    kick: bool = False
    knockback: bool = False
    moving_obstacles: bool = False
    kick_speed: float = 1.5
    friction: float = 0.15
    restitution_wall: float = 0.5
    restitution_body: float = 1.0
    mass_bomb: float = 1.0
    mass_player: float = 2.0
    knock_impulse: float = 4.0
    knock_range: int = 4
    obstacle_speed: float = 0.5

    @property
    def enabled(self) -> bool:
        return self.kick or self.knockback or self.moving_obstacles


@dataclass(frozen=True)
class GameConfig:
    width: int = 9
    height: int = 9
    box_density: float = 0.4
    bomb_timer: int = 5
    bomb_radius: int = 2
    flame_duration: int = 1
    max_bombs: int = 1
    max_ticks: int = 200
    physics: PhysicsConfig = field(default_factory=PhysicsConfig)

    def __post_init__(self) -> None:
        if self.width < 7 or self.height < 7 or self.width % 2 == 0 or self.height % 2 == 0:
            raise ValueError("Plansza musi mieć nieparzyste wymiary, co najmniej 7x7.")
        if self.bomb_timer < 1 or self.bomb_radius < 1 or self.flame_duration < 1:
            raise ValueError("Zapalnik, promień i czas ognia muszą być dodatnie.")
        if self.physics.knock_range <= self.bomb_radius and self.physics.knockback:
            raise ValueError("Zasięg odrzutu musi być większy niż promień wybuchu.")

    def with_physics(self, flags: bool | dict[str, bool]) -> GameConfig:
        """Kopia konfiguracji z włączonymi/wyłączonymi elementami fizyki."""
        if isinstance(flags, bool):
            flags = {"kick": flags, "knockback": flags, "moving_obstacles": flags}
        return replace(self, physics=replace(self.physics, **flags))

    def without_physics(self) -> GameConfig:
        return self.with_physics(False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameConfig:
        data = dict(data)
        physics_data = data.pop("physics", {}) or {}
        _reject_unknown(cls, data)
        _reject_unknown(PhysicsConfig, physics_data)
        return cls(physics=PhysicsConfig(**physics_data), **data)


def _reject_unknown(cls: type, data: dict[str, Any]) -> None:
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Nieznane pola konfiguracji {cls.__name__}: {sorted(unknown)}")


def load_config(path: str | Path | None = None) -> GameConfig:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        return GameConfig.from_dict(json.load(f))
