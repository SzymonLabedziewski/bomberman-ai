"""Serwer WebSocket dla Godota (docs/protokol.md)."""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from bomberman import __version__
from bomberman.ai.registry import BOT_NAMES, FAMILIES, LABELS
from bomberman.ai.telemetry import compute_totals, enrich_wall_ms
from bomberman.config import PROJECT_ROOT, load_config
from bomberman.engine.board import new_game
from bomberman.engine.rules import step
from bomberman.engine.serialize import save_replay, state_to_dict
from bomberman.engine.state import Action
from bomberman.experiments.metrics import play_measured
from bomberman.match import debug_payload, labels_for, make_bots

RESULTS_DIR = PROJECT_ROOT / "results"
MOVES = {"UP", "DOWN", "LEFT", "RIGHT"}
MAX_TPS = 60.0


class HumanInput:
    """Wejście człowieka: ruch trwa do STAY, BOMB działa raz."""

    def __init__(self) -> None:
        self.held: Action | None = None
        self.tap: Action | None = None
        self.bomb = False

    def press(self, name: str) -> None:
        if name == "BOMB":
            self.bomb = True
        elif name == "STAY":
            self.held = None
        elif name in MOVES:
            self.held = self.tap = Action[name]

    def take(self) -> Action:
        if self.bomb:
            self.bomb = False
            return Action.BOMB
        if self.tap is not None:
            action, self.tap = self.tap, None
            return action
        return self.held or Action.STAY


class Session:
    def __init__(self, ws: ServerConnection, results_dir: Path) -> None:
        self.ws = ws
        self.results_dir = results_dir
        self.game: asyncio.Task | None = None
        self.tournament: asyncio.Task | None = None
        self.inputs = [HumanInput(), HumanInput()]
        self.humans: list[int] = []
        self.paused = False
        self.step_once = False
        self.tps = 6.0
        self.wake = asyncio.Event()

    async def send(self, msg: dict[str, Any]) -> None:
        await self.ws.send(json.dumps(msg, ensure_ascii=False, separators=(",", ":")))

    async def run(self) -> None:
        await self.send({
            "type": "hello", "version": __version__, "bots": BOT_NAMES,
            "labels": {n: LABELS[n] for n in BOT_NAMES + ["human"]},
            "families": {n: FAMILIES[n] for n in BOT_NAMES},
        })
        try:
            async for raw in self.ws:
                try:
                    msg = json.loads(raw)
                    await self.handle(msg)
                except (ValueError, KeyError, TypeError) as e:
                    await self.send({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            for task in (self.game, self.tournament):
                if task is not None:
                    task.cancel()

    async def handle(self, msg: dict[str, Any]) -> None:
        kind = msg["type"]
        if kind in ("start", "tournament"):
            for key, default in (("p1", "human"), ("p2", "planner")):
                name = str(msg.get(key, default))
                if name not in BOT_NAMES and not (name == "human" and kind == "start"):
                    raise ValueError(f"nieznany bot {name!r}")
        if kind == "start":
            self._cancel(self.game)
            self.game = asyncio.create_task(self.play(msg))
        elif kind == "input":
            pid = msg.get("player")
            if pid is None:
                pid = self.humans[0] if self.humans else 0
            self.inputs[int(pid)].press(str(msg["action"]).upper())
        elif kind == "control":
            self.control(msg)
        elif kind == "get_results":
            path = self.results_dir / "summary.json"
            summary = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            await self.send({"type": "results", "summary": summary})
        elif kind == "list_replays":
            await self.send({"type": "replays", "items": self.replay_names()})
        elif kind == "get_replay":
            name = Path(str(msg["name"])).name
            path = self.results_dir / "replays" / name
            if not path.exists():
                raise ValueError(f"nie ma powtórki {name}")
            data = json.loads(path.read_text(encoding="utf-8"))
            await self.send({"type": "replay", "name": name, "data": data})
        elif kind == "tournament":
            self._cancel(self.tournament)
            self.tournament = asyncio.create_task(self.run_tournament(msg))
        else:
            raise ValueError(f"nieznany typ wiadomości {kind!r}")

    def control(self, msg: dict[str, Any]) -> None:
        cmd = msg["cmd"]
        if cmd == "pause":
            self.paused = True
        elif cmd == "resume":
            self.paused = False
        elif cmd == "step":
            self.paused = True
            self.step_once = True
        elif cmd == "speed":
            self.tps = min(MAX_TPS, max(0.5, float(msg["value"])))
        elif cmd == "stop":
            self._cancel(self.game)
            self._cancel(self.tournament)
        else:
            raise ValueError(f"nieznane polecenie {cmd!r}")
        self.wake.set()

    def replay_names(self) -> list[str]:
        directory = self.results_dir / "replays"
        if not directory.exists():
            return []
        files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [p.name for p in files]

    @staticmethod
    def _cancel(task: asyncio.Task | None) -> None:
        if task is not None and not task.done():
            task.cancel()

    async def play(self, msg: dict[str, Any]) -> None:
        names = [str(msg.get("p1", "human")), str(msg.get("p2", "planner"))]
        seed = int(msg.get("seed", 1))
        cfg = load_config().with_physics(msg.get("physics", False))
        self.tps = min(MAX_TPS, max(0.5, float(msg.get("tps", 6.0))))
        self.paused = False
        self.inputs = [HumanInput(), HumanInput()]
        self.humans = [pid for pid, n in enumerate(names) if n == "human"]
        bots = make_bots(names, cfg, seed)
        labels = labels_for(names)
        state = new_game(cfg, seed)
        frames: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        compute_traces: list[list[dict[str, Any]]] = [[], []]
        families = [FAMILIES.get(n, "") if n != "human" else "human" for n in names]

        def decide() -> tuple[list[Action | None], dict[str, Any]]:
            actions: list[Action | None] = []
            for pid, b in enumerate(bots):
                if b is None:
                    actions.append(None)
                    continue
                t_act = time.perf_counter()
                actions.append(b.act(state, pid))
                enrich_wall_ms(b, (time.perf_counter() - t_act) * 1000)
                info = b.debug or {}
                compute = dict(info.get("compute") or {})
                if state.players[pid].alive:
                    compute_traces[pid].append(compute)
            known = [a if a is not None else Action.STAY for a in actions]
            debug = debug_payload(state, cfg, bots, known)
            for pid in self.humans:
                debug["actions"].pop(str(pid), None)
            return actions, debug

        try:
            while not state.done:
                t0 = time.perf_counter()
                actions, debug = await asyncio.to_thread(decide)
                frame = state_to_dict(state, events, debug, labels)
                frames.append(frame)
                await self.send(frame)
                await self.wait_tick(t0)
                final = [a if a is not None else self.inputs[pid].take() for pid, a in enumerate(actions)]
                events = step(state, final, cfg)
            frame = state_to_dict(state, events, debug_payload(state, cfg, []), labels)
            frames.append(frame)
            await self.send(frame)
            totals = []
            for pid in (0, 1):
                tot = compute_totals(compute_traces[pid])
                tot["name"] = labels[pid]
                tot["family"] = families[pid]
                totals.append(tot)
            await self.send({"type": "game_over", "winner": state.winner, "ticks": state.tick,
                             "stats": {"names": labels, "seed": seed, "compute_totals": totals}})
            meta = {"p1": labels[0], "p2": labels[1], "bots": names, "seed": seed, "winner": state.winner,
                    "ticks": state.tick, "config": cfg.to_dict(), "live": True, "compute_totals": totals}
            stamp = time.strftime("%Y%m%d_%H%M%S")
            save_replay(self.results_dir / "replays" / f"live_{stamp}_{names[0]}_vs_{names[1]}.json", frames, meta)
        except (asyncio.CancelledError, ConnectionClosed):
            pass
        except Exception as e:
            await self.report(e)

    async def report(self, error: Exception) -> None:
        traceback.print_exc()
        try:
            await self.send({"type": "error", "message": f"{type(error).__name__}: {error}"})
        except ConnectionClosed:
            pass

    async def wait_tick(self, t0: float) -> None:
        """Czeka do następnego ticku; w pauzie czeka na `resume` albo `step`."""
        while True:
            if self.step_once:
                self.step_once = False
                return
            if not self.paused:
                left = 1.0 / self.tps - (time.perf_counter() - t0)
                if left <= 0:
                    return
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), left)
                except TimeoutError:
                    return
                continue
            self.wake.clear()
            await self.wake.wait()

    async def run_tournament(self, msg: dict[str, Any]) -> None:
        names = [str(msg.get("p1", "planner")), str(msg.get("p2", "montecarlo"))]
        games = max(1, min(1000, int(msg.get("games", 20))))
        seed = int(msg.get("seed", 1))
        cfg = load_config().with_physics(msg.get("physics", False))
        labels = labels_for(names)
        wins, draws, ticks = [0, 0], 0, 0
        try:
            for i in range(games):
                seats = [0, 1] if i % 2 == 0 else [1, 0]
                seat_names = [names[s] for s in seats]
                bots = make_bots(seat_names, cfg, seed + i)
                state, _ = await asyncio.to_thread(play_measured, cfg, bots, seed + i)
                ticks += state.tick
                if state.winner == -1:
                    draws += 1
                else:
                    wins[seats[state.winner]] += 1
                await self.send({"type": "tournament_progress", "done": i + 1, "total": games,
                                 "stats": {"names": labels, "wins": wins, "draws": draws,
                                           "avg_ticks": round(ticks / (i + 1), 1)}})
        except (asyncio.CancelledError, ConnectionClosed):
            pass
        except Exception as e:
            await self.report(e)


async def serve_forever(host: str, port: int, results_dir: Path = RESULTS_DIR,
                        ready: asyncio.Future | None = None) -> None:
    async def handler(ws: ServerConnection) -> None:
        try:
            await Session(ws, results_dir).run()
        except ConnectionClosed:
            pass

    async with serve(handler, host, port, max_size=2 ** 22) as server:
        if ready is not None:
            ready.set_result(server.sockets[0].getsockname()[1])
        await server.serve_forever()


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    print(f"Serwer Bomberman AI: ws://{host}:{port}  (Ctrl+C kończy)")
    print("Teraz uruchom projekt godot/ w Godocie (F5).")
    try:
        asyncio.run(serve_forever(host, port))
    except KeyboardInterrupt:
        print("Serwer zatrzymany.")
