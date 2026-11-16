"""Rozgrywanie i nagrywanie pojedynczych gier (CLI `play`, powtórki dla Godota, serwer)."""

from __future__ import annotations

import time
from typing import Any, Sequence

from bomberman.ai.base import Bot
from bomberman.ai.danger import danger_ticks, default_horizon, predict
from bomberman.ai.registry import LABELS, make_bot
from bomberman.ai.telemetry import enrich_wall_ms
from bomberman.config import GameConfig
from bomberman.engine.board import new_game
from bomberman.engine.rules import step
from bomberman.engine.serialize import state_to_dict
from bomberman.engine.state import Action, GameState


def labels_for(names: Sequence[str]) -> list[str]:
    return [LABELS.get(n, n) for n in names]


def make_bots(names: Sequence[str], cfg: GameConfig, seed: int) -> list[Bot | None]:
    """Boty dla obu graczy (None dla człowieka)."""
    return [None if n == "human" else make_bot(n, cfg, seed * 2 + pid + 1) for pid, n in enumerate(names)]


def debug_payload(state: GameState, cfg: GameConfig, bots: Sequence[Bot | None],
                  actions: Sequence[Action] | None = None) -> dict[str, Any]:
    """Dane dla nakładek AI w Godocie."""
    w = state.width
    timeline = predict(state, default_horizon(cfg), cfg)
    payload: dict[str, Any] = {
        "danger": {f"{c % w},{c // w}": t for c, t in sorted(danger_ticks(timeline).items())},
        "plans": {}, "values": {}, "modes": {},
        "families": {}, "compute": {}, "rationales": {},
    }
    for pid, bot in enumerate(bots):
        info = bot.debug if bot is not None else None
        if not info:
            continue
        key = str(pid)
        for src, target in (("plan", "plans"), ("values", "values"), ("mode", "modes"),
                            ("family", "families"), ("compute", "compute"), ("rationale", "rationales")):
            if src in info:
                payload[target][key] = info[src]
    if actions is not None:
        payload["actions"] = {str(pid): Action(a).name for pid, a in enumerate(actions)}
    return payload


def record_game(cfg: GameConfig, names: Sequence[str], seed: int) -> dict[str, Any]:
    """Rozgrywa grę botów i zwraca powtórkę."""
    bots = make_bots(names, cfg, seed)
    if any(b is None for b in bots):
        raise ValueError("powtórkę można nagrać tylko dla botów")
    labels = labels_for(names)
    state = new_game(cfg, seed)
    frames = []
    events: list[dict[str, Any]] = []
    while not state.done:
        actions = []
        for pid, bot in enumerate(bots):
            t0 = time.perf_counter()
            actions.append(bot.act(state, pid))
            enrich_wall_ms(bot, (time.perf_counter() - t0) * 1000)
        frames.append(state_to_dict(state, events, debug_payload(state, cfg, bots, actions), labels))
        events = step(state, actions, cfg)
    frames.append(state_to_dict(state, events, debug_payload(state, cfg, []), labels))
    meta = {"p1": labels[0], "p2": labels[1], "bots": list(names), "seed": seed,
            "winner": state.winner, "ticks": state.tick, "config": cfg.to_dict()}
    return {"type": "replay", "meta": meta, "frames": frames}
