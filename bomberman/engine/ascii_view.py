"""Podgląd stanu w terminalu (do debugowania bez Godota)."""

from __future__ import annotations

from bomberman.engine import physics
from bomberman.engine.state import BOX, WALL, GameState


def render(state: GameState, names: list[str] | None = None) -> str:
    w, h = state.width, state.height
    canvas = [["#" if state.grid[y * w + x] == WALL else "+" if state.grid[y * w + x] == BOX else "."
               for x in range(w)] for y in range(h)]
    for c in state.flames:
        canvas[c // w][c % w] = "*"
    for o in state.obstacles:
        for c in physics.obstacle_cells(o, w):
            canvas[c // w][c % w] = "O"
    bomb_cells = set()
    for b in state.bombs:
        x, y = b.cell
        bomb_cells.add((x, y))
        canvas[y][x] = str(max(0, min(b.timer, 9)))
    for p in state.players:
        x, y = p.cell
        letter = "AB"[p.id]
        if not p.alive:
            canvas[y][x] = "x"
        elif (x, y) in bomb_cells:
            canvas[y][x] = letter.lower()
        else:
            canvas[y][x] = letter
    lines = ["".join(row) for row in canvas]
    labels = names or ["Gracz 1", "Gracz 2"]
    status = "  ".join(f"{'AB'[p.id]}={labels[p.id]}{'' if p.alive else ' (martwy)'}" for p in state.players)
    lines.append(f"tick {state.tick}  {status}")
    return "\n".join(lines)
