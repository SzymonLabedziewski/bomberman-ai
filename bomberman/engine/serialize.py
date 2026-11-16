"""Zapis stanu do JSON: wiadomości dla Godota i powtórki (docs/protokol.md)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bomberman.engine import physics
from bomberman.engine.state import BOX, EMPTY, WALL, Bomb, Event, GameState, Obstacle, Player

_CHARS = {EMPTY: ".", WALL: "#", BOX: "+"}
_CODES = {v: k for k, v in _CHARS.items()}


def _r(v: float) -> float:
    return round(v, 3)


def state_to_dict(state: GameState, events: list[Event] | None = None,
                  debug: dict[str, Any] | None = None, names: list[str] | None = None) -> dict[str, Any]:
    w, h = state.width, state.height
    grid = state.grid
    return {
        "type": "state",
        "tick": state.tick,
        "width": w,
        "height": h,
        "grid": ["".join(_CHARS[grid[y * w + x]] for x in range(w)) for y in range(h)],
        "players": [
            {"id": p.id, "x": _r(p.x), "y": _r(p.y), "vx": _r(p.vx), "vy": _r(p.vy),
             "alive": p.alive, "stunned": p.stunned,
             "name": names[p.id] if names else f"Gracz {p.id + 1}"}
            for p in state.players
        ],
        "bombs": [
            {"id": b.id, "x": _r(b.x), "y": _r(b.y), "vx": _r(b.vx), "vy": _r(b.vy),
             "timer": b.timer, "owner": b.owner, "radius": b.radius}
            for b in state.bombs
        ],
        "obstacles": [
            {"id": o.id, "x": _r(o.x), "y": _r(o.y), "vx": _r(o.vx), "vy": _r(o.vy),
             "cells": [[c % w, c // w] for c in physics.obstacle_cells(o, w)]}
            for o in state.obstacles
        ],
        "flames": [[c % w, c // w] for c in sorted(state.flames)],
        "events": events or [],
        "done": state.done,
        "winner": state.winner,
        "debug": debug or {},
    }


def state_from_dict(d: dict[str, Any]) -> GameState:
    """Odtwarza stan z wiadomości `state` (bez historii przyczyn ognia)."""
    w, h = d["width"], d["height"]
    grid = [_CODES[ch] for row in d["grid"] for ch in row]
    players = [Player(p["id"], p["x"], p["y"], p["vx"], p["vy"], p["alive"]) for p in d["players"]]
    bombs = [Bomb(b["id"], b["owner"], b["x"], b["y"], b["timer"], b["radius"], b["vx"], b["vy"])
             for b in d["bombs"]]
    for b in bombs:
        players[b.owner].bombs_used += 1
    obstacles = [Obstacle(o["id"], o["x"], o["y"], o["vx"], o["vy"]) for o in d["obstacles"]]
    flames = {y * w + x: 1 for x, y in d["flames"]}
    next_id = max((b.id for b in bombs), default=-1) + 1
    return GameState(w, h, grid, players, bombs, obstacles, flames, {}, d["tick"], next_id,
                     d["done"], d["winner"])


def save_replay(path: str | Path, frames: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "replay", "meta": meta, "frames": frames}, f, ensure_ascii=False,
                  separators=(",", ":"))
