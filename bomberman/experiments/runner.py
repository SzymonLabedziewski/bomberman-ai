"""Uruchamianie eksperymentów z configs/experiments/*.json."""

from __future__ import annotations

import csv
import itertools
import json
import multiprocessing
import os
import random
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from bomberman.ai.registry import LABELS, make_bot
from bomberman.config import PROJECT_ROOT, GameConfig, load_config
from bomberman.experiments.metrics import play_measured, result_for
from bomberman.experiments.scenarios import is_escapable, make_scenario, run_escape

RESULTS_DIR = PROJECT_ROOT / "results"
EXPERIMENTS_DIR = PROJECT_ROOT / "configs" / "experiments"

MATCH_COLUMNS = [
    "experiment", "variant", "matchup", "game_id", "seed", "seat", "bot", "opponent", "result", "ticks",
    "suicides", "self_kill", "died", "death_physics", "escape_episodes", "escape_success",
    "escapable_episodes", "escapable_success", "escape_ticks_sum",
    "decision_ms_mean", "decision_ms_max", "decision_ms_sum",
    "cpu_ms_mean", "cpu_ms_sum",
    "ops_mean", "ops_sum", "rss_kb_mean", "rss_kb_max", "family",
    "kicks", "bombs_placed",
]
ESCAPE_COLUMNS = ["experiment", "variant", "scenario", "seed", "bot", "escapable", "success", "ticks"]


def _spec(bot: str | dict[str, Any]) -> dict[str, Any]:
    spec = {"name": bot} if isinstance(bot, str) else dict(bot)
    spec.setdefault("params", {})
    spec.setdefault("label", LABELS.get(spec["name"], spec["name"]))
    return spec


def _game_config(physics: bool | dict[str, bool], max_ticks: int | None = None) -> GameConfig:
    cfg = load_config().with_physics(physics)
    if max_ticks is not None:
        cfg = replace(cfg, max_ticks=int(max_ticks))
    return cfg


def _bot(spec: dict[str, Any], cfg: GameConfig, seed: int):
    return make_bot(spec["name"], cfg, seed, **spec["params"])


def _match_task(task: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = _game_config(task["physics"], task.get("max_ticks"))
    seed = task["seed"]
    specs = task["seats"]
    bots = [_bot(s, cfg, seed * 2 + seat + 1) for seat, s in enumerate(specs)]
    state, stats = play_measured(cfg, bots, seed)
    rows = []
    for seat in (0, 1):
        row = {
            "experiment": task["experiment"], "variant": task["variant"], "matchup": task["matchup"],
            "game_id": task["game_id"], "seed": seed, "seat": seat,
            "bot": specs[seat]["label"], "opponent": specs[1 - seat]["label"],
            "result": result_for(state, seat), "ticks": state.tick,
        }
        row.update(stats[seat].row())
        rows.append(row)
    return rows


def _escape_task(task: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = _game_config(task["physics"])
    state = make_scenario(cfg, task["seed"])
    escapable = is_escapable(state, cfg)
    rows = []
    for i, spec in enumerate(task["bots"]):
        success, ticks = run_escape(state, _bot(spec, cfg, task["seed"] * 10 + i), cfg)
        rows.append({
            "experiment": task["experiment"], "variant": task["variant"], "scenario": task["scenario"],
            "seed": task["seed"], "bot": spec["label"], "escapable": int(escapable),
            "success": int(success), "ticks": ticks,
        })
    return rows


def _run_task(task: dict[str, Any]) -> list[dict[str, Any]]:
    return _escape_task(task) if task["kind"] == "escape" else _match_task(task)


def build_tasks(config: dict[str, Any], scale: float = 1.0) -> list[dict[str, Any]]:
    name = config["name"]
    base_seed = int(config.get("seed", 0))
    if config.get("kind", "matches") == "escape":
        n = max(1, round(config["scenarios"] * scale))
        bots = [_spec(b) for b in config["bots"]]
        tasks = []
        for v, variant in enumerate(config["variants"]):
            for i in range(n):
                tasks.append({"kind": "escape", "experiment": name, "variant": variant["variant"],
                              "physics": variant["physics"], "scenario": i, "seed": base_seed + v * 100000 + i,
                              "bots": bots})
        return tasks

    def n_games(label: str) -> int:
        return max(2, 2 * round(config.get("games_for", {}).get(label, config["games"]) * scale / 2))

    matchups = []
    if "round_robin" in config:
        specs = [_spec(b) for b in config["round_robin"]]
        for a, b in itertools.combinations(specs, 2):
            matchups.append({"variant": config.get("variant", ""), "p1": a, "p2": b})
    for m in config.get("matchups", []):
        matchups.append({"variant": m.get("variant", ""), "p1": _spec(m["p1"]), "p2": _spec(m["p2"]),
                         "physics": m.get("physics"), "max_ticks": m.get("max_ticks")})

    use_random_seeds = bool(config.get("random_seeds", False))
    max_n = max((n_games(f"{m['p1']['label']} vs {m['p2']['label']}") for m in matchups), default=0)
    if use_random_seeds:
        rng = random.Random(base_seed)
        seed_pool: list[int] = []
        seen: set[int] = set()
        while len(seed_pool) < max_n:
            s = rng.randint(1, 10_000_000)
            if s not in seen:
                seen.add(s)
                seed_pool.append(s)
    else:
        seed_pool = [base_seed + i for i in range(max_n)]

    tasks = []
    for m in matchups:
        physics = m.get("physics")
        if physics is None:
            physics = config.get("physics", False)
        max_ticks = m.get("max_ticks")
        if max_ticks is None:
            max_ticks = config.get("max_ticks")
        label = f"{m['p1']['label']} vs {m['p2']['label']}"
        for i in range(n_games(label)):
            seats = [m["p1"], m["p2"]] if i % 2 == 0 else [m["p2"], m["p1"]]
            task_dict: dict[str, Any] = {
                "kind": "match", "experiment": name, "variant": m["variant"], "matchup": label,
                "game_id": i, "seed": seed_pool[i], "seats": seats, "physics": physics,
            }
            if max_ticks is not None:
                task_dict["max_ticks"] = int(max_ticks)
            tasks.append(task_dict)
    return tasks


def load_experiment(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_experiment(path: str | Path, workers: int | None = None, scale: float = 1.0,
                   out_dir: Path = RESULTS_DIR) -> Path:
    config = load_experiment(path)
    tasks = build_tasks(config, scale)
    workers = workers or max(1, (os.cpu_count() or 2))
    kind = config.get("kind", "matches")
    print(f"[{config['name']}] {config.get('title', '')}: {len(tasks)} zadań, procesy: {workers}", flush=True)
    t0 = time.perf_counter()
    rows: list[dict[str, Any]] = []
    step = max(1, len(tasks) // 10)
    # najdroższe zadania najpierw
    order = sorted(range(len(tasks)), key=lambda i: -_cost(tasks[i]))
    with multiprocessing.Pool(workers) as pool:
        for done, result in enumerate(pool.imap_unordered(_run_task, [tasks[i] for i in order]), 1):
            rows.extend(result)
            if done % step == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)}  ({time.perf_counter() - t0:.0f} s)", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{config['name']}.csv"
    if kind == "escape":
        rows.sort(key=lambda r: (r["variant"], r["scenario"], r["bot"]))
        columns = ESCAPE_COLUMNS
    else:
        rows.sort(key=lambda r: (r["matchup"], r["variant"], r["game_id"], r["seat"]))
        columns = MATCH_COLUMNS
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    elapsed = time.perf_counter() - t0
    meta = {"config": config, "scale": scale, "tasks": len(tasks), "workers": workers,
            "seconds": round(elapsed, 1), "python": sys.version.split()[0]}
    with open(out_dir / f"{config['name']}.meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[{config['name']}] zapisano {out} ({elapsed:.0f} s)", flush=True)
    return out


def _cost(task: dict[str, Any]) -> float:
    specs = task.get("seats") or task.get("bots") or []
    cost = 1.0
    for s in specs:
        if s["name"] == "montecarlo":
            p = s["params"]
            cost += p.get("rollouts", 30) * p.get("depth", 8)
        elif s["name"] in ("planner", "qlearner"):
            cost += 15.0
    if task.get("physics"):
        cost *= 1.8
    return cost


def experiment_paths() -> list[Path]:
    return sorted(EXPERIMENTS_DIR.glob("*.json"))
