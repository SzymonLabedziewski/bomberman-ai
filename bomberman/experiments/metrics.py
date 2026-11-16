"""Rozgrywka z pomiarem metryk."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from bomberman.ai.base import Bot
from bomberman.ai.danger import default_horizon, escape_path, has_escape, in_danger, predict
from bomberman.ai.telemetry import compute_totals, enrich_wall_ms
from bomberman.config import GameConfig
from bomberman.engine.board import new_game
from bomberman.engine.rules import after_action, step
from bomberman.engine.state import Action, GameState


@dataclass
class PlayerStats:
    suicides: int = 0
    died: bool = False
    self_kill: bool = False
    death_physics: bool = False
    escape_episodes: int = 0
    escape_success: int = 0
    escapable_episodes: int = 0
    escapable_success: int = 0
    escape_ticks_sum: int = 0
    kicks: int = 0
    bombs_placed: int = 0
    decision_ms: list[float] = field(default_factory=list)
    cpu_ms: list[float] = field(default_factory=list)
    ops: list[int] = field(default_factory=list)
    rss_kb: list[float] = field(default_factory=list)
    family: str = ""
    compute_traces: list[dict[str, Any]] = field(default_factory=list)
    _episode_start: int | None = None
    _episode_escapable: bool = False

    def open_episode(self, tick: int, escapable: bool) -> None:
        self._episode_start = tick
        self._episode_escapable = escapable

    def close_episode(self, tick: int, success: bool) -> None:
        if self._episode_start is None:
            return
        self.escape_episodes += 1
        self.escapable_episodes += self._episode_escapable
        if success:
            self.escape_success += 1
            self.escapable_success += self._episode_escapable
            self.escape_ticks_sum += tick - self._episode_start
        self._episode_start = None

    @property
    def in_episode(self) -> bool:
        return self._episode_start is not None

    def row(self) -> dict[str, Any]:
        times = self.decision_ms or [0.0]
        cpus = self.cpu_ms or times
        ops = self.ops or [0]
        rss = self.rss_kb or [0.0]
        return {
            "suicides": self.suicides, "self_kill": int(self.self_kill), "died": int(self.died),
            "death_physics": int(self.death_physics),
            "escape_episodes": self.escape_episodes, "escape_success": self.escape_success,
            "escapable_episodes": self.escapable_episodes, "escapable_success": self.escapable_success,
            "escape_ticks_sum": self.escape_ticks_sum,
            "decision_ms_mean": round(sum(times) / len(times), 4),
            "decision_ms_max": round(max(times), 4),
            "decision_ms_sum": round(sum(times), 4),
            "cpu_ms_mean": round(sum(cpus) / len(cpus), 4),
            "cpu_ms_sum": round(sum(cpus), 4),
            "ops_mean": round(sum(ops) / len(ops), 2), "ops_sum": sum(ops),
            "rss_kb_mean": round(sum(rss) / len(rss), 1),
            "rss_kb_max": round(max(rss), 1),
            "family": self.family,
            "kicks": self.kicks, "bombs_placed": self.bombs_placed,
        }

    def totals(self) -> dict[str, Any]:
        out = compute_totals(self.compute_traces)
        out["family"] = self.family
        return out


def _is_suicide(state: GameState, pid: int, action: Action, cfg: GameConfig) -> bool:
    return not has_escape(after_action(state, pid, action, cfg), pid, cfg)


def play_measured(cfg: GameConfig, bots: Sequence[Bot], seed: int,
                  state: GameState | None = None) -> tuple[GameState, list[PlayerStats]]:
    """Rozgrywa jedną grę i zwraca stan końcowy oraz metryki."""
    state = state if state is not None else new_game(cfg, seed)
    horizon = default_horizon(cfg)
    stats = [PlayerStats(), PlayerStats()]
    while not state.done:
        actions = []
        for pid, bot in enumerate(bots):
            t0 = time.perf_counter()
            c0 = time.process_time()
            actions.append(bot.act(state, pid))
            wall_ms = (time.perf_counter() - t0) * 1000
            cpu_ms = (time.process_time() - c0) * 1000
            enrich_wall_ms(bot, wall_ms, cpu_ms=cpu_ms)
            info = bot.debug or {}
            compute = info.get("compute") or {}
            if state.players[pid].alive:
                stats[pid].decision_ms.append(wall_ms)
                stats[pid].cpu_ms.append(cpu_ms)
                stats[pid].ops.append(int(compute.get("ops", 0)))
                stats[pid].rss_kb.append(float(compute.get("rss_kb", 0.0)))
                stats[pid].compute_traces.append(dict(compute))
                if not stats[pid].family:
                    stats[pid].family = str(info.get("family", ""))

        timeline = predict(state, horizon, cfg) if (state.bombs or state.flames) else None
        for pid in (0, 1):
            if not state.players[pid].alive:
                continue
            st = stats[pid]
            danger = timeline is not None and in_danger(timeline, state.player_cell(pid))
            escapable = not danger or escape_path(state, pid, timeline, cfg) is not None
            if danger and not st.in_episode:
                st.open_episode(state.tick, escapable)
            elif not danger and st.in_episode:
                st.close_episode(state.tick, True)
            if escapable and _is_suicide(state, pid, actions[pid], cfg):
                st.suicides += 1

        for e in step(state, actions, cfg):
            kind = e["type"]
            if kind == "bomb":
                stats[e["player"]].bombs_placed += 1
            elif kind == "kick":
                stats[e["player"]].kicks += 1
            elif kind == "death":
                st = stats[e["player"]]
                st.died = True
                st.self_kill = st.self_kill or e["by_self"]
                st.death_physics = st.death_physics or e["physics"]
                st.close_episode(state.tick, False)
    return state, stats


def result_for(state: GameState, pid: int) -> str:
    if state.winner == -1 or state.winner is None:
        return "draw"
    return "win" if state.winner == pid else "loss"
