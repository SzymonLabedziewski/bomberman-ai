import asyncio
import json

from websockets.asyncio.client import connect

from bomberman.server import HumanInput, serve_forever
from bomberman.engine.state import Action


async def _session(results_dir, script):
    ready = asyncio.get_running_loop().create_future()
    server = asyncio.create_task(serve_forever("127.0.0.1", 0, results_dir, ready))
    port = await ready
    try:
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            return await script(ws)
    finally:
        server.cancel()
        try:
            await server
        except asyncio.CancelledError:
            pass


async def _recv(ws, kind, limit=2000):
    for _ in range(limit):
        msg = json.loads(await asyncio.wait_for(ws.recv(), 10))
        if msg["type"] == kind:
            return msg
    raise AssertionError(f"brak wiadomości {kind}")


def test_bot_game_runs_to_game_over_and_saves_replay(tmp_path):
    async def script(ws):
        hello = await _recv(ws, "hello")
        assert "planner" in hello["bots"]
        await ws.send(json.dumps({"type": "start", "p1": "planner", "p2": "random", "seed": 3, "tps": 60}))
        first = await _recv(ws, "state")
        assert first["tick"] == 0 and "danger" in first["debug"]
        over = await _recv(ws, "game_over")
        await ws.send(json.dumps({"type": "list_replays"}))
        return over, await _recv(ws, "replays")

    over, replays = asyncio.run(_session(tmp_path, script))
    assert over["winner"] in (-1, 0, 1)
    assert len(replays["items"]) == 1 and replays["items"][0].startswith("live_")


def test_human_input_moves_player(tmp_path):
    async def script(ws):
        await _recv(ws, "hello")
        await ws.send(json.dumps({"type": "start", "p1": "human", "p2": "random", "seed": 1, "tps": 20}))
        await _recv(ws, "state")
        await ws.send(json.dumps({"type": "input", "action": "RIGHT"}))
        for _ in range(50):
            s = await _recv(ws, "state")
            if s["players"][0]["x"] > 1.0 or s["done"]:
                return s
        return s

    s = asyncio.run(_session(tmp_path, script))
    assert s["players"][0]["x"] > 1.0, "gracz po naciśnięciu RIGHT przesuwa się w prawo"


def test_errors_and_results(tmp_path):
    (tmp_path / "summary.json").write_text('{"charts": []}', encoding="utf-8")

    async def script(ws):
        await _recv(ws, "hello")
        await ws.send(json.dumps({"type": "start", "p1": "nobody"}))
        err = await _recv(ws, "error")
        await ws.send(json.dumps({"type": "get_results"}))
        return err, await _recv(ws, "results")

    err, results = asyncio.run(_session(tmp_path, script))
    assert "nobody" in err["message"]
    assert results["summary"] == {"charts": []}


def test_tournament_progress(tmp_path):
    async def script(ws):
        await _recv(ws, "hello")
        await ws.send(json.dumps({"type": "tournament", "p1": "randomsafe", "p2": "random", "games": 4}))
        msg = None
        while msg is None or msg["done"] < 4:
            msg = await _recv(ws, "tournament_progress")
        return msg

    msg = asyncio.run(_session(tmp_path, script))
    stats = msg["stats"]
    assert sum(stats["wins"]) + stats["draws"] == 4


def test_human_input_semantics():
    h = HumanInput()
    h.press("LEFT")
    h.press("STAY")
    assert h.take() == Action.LEFT, "krótkie wciśnięcie między tickami też się liczy"
    assert h.take() == Action.STAY
    h.press("UP")
    assert h.take() == Action.UP and h.take() == Action.UP, "trzymany ruch trwa"
    h.press("BOMB")
    assert h.take() == Action.BOMB and h.take() == Action.UP
