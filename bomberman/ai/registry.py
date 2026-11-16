"""Tworzenie botów po nazwie (CLI, serwer, eksperymenty)."""

from __future__ import annotations

from typing import Any

from bomberman.ai.base import Bot
from bomberman.config import GameConfig

BOT_NAMES = [
    "random", "randomsafe", "planner", "montecarlo", "qlearner",
]

LABELS = {
    "random": "Random",
    "randomsafe": "RandomSafe",
    "planner": "Planner",
    "montecarlo": "MonteCarlo",
    "qlearner": "Q-Learning (AI)",
    "human": "Człowiek",
}

FAMILIES = {
    "random": "random",
    "randomsafe": "random",
    "planner": "search",
    "montecarlo": "search",
    "qlearner": "rl",
}


def make_bot(name: str, cfg: GameConfig, seed: int = 0, **params: Any) -> Bot:
    from bomberman.ai.baselines import RandomBot, RandomSafeBot
    from bomberman.ai.planner_bot import PlannerBot

    if name == "random":
        return RandomBot(cfg, seed)
    if name == "randomsafe":
        return RandomSafeBot(cfg, seed)
    if name == "planner":
        return PlannerBot(cfg, seed, **params)
    if name == "montecarlo":
        from bomberman.ai.montecarlo_bot import MonteCarloBot
        return MonteCarloBot(cfg, seed, **params)
    if name == "qlearner":
        from bomberman.ai.q_table import DEFAULT_PHYSICS_TABLE_PATH, DEFAULT_TABLE_PATH, QTable
        from bomberman.ai.qlearner_bot import QLearnerBot
        if "table" not in params and "table_path" not in params:
            use_phys_table = cfg.physics.kick or cfg.physics.knockback
            path = DEFAULT_PHYSICS_TABLE_PATH if use_phys_table else DEFAULT_TABLE_PATH
            if path.exists():
                return QLearnerBot(cfg, seed, table_path=path, **params)
            return QLearnerBot(cfg, seed, table=QTable(), **params)
        return QLearnerBot(cfg, seed, **params)
    raise ValueError(f"Nieznany bot {name!r}. Dostępne: {', '.join(BOT_NAMES)}")
