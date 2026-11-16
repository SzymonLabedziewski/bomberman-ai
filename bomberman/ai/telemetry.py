"""Wspólna telemetria decyzji botów: rodzina, ops, RSS, czas."""

from __future__ import annotations

from typing import Any

FAMILIES = ("random", "search", "rl")


def rss_kb() -> float:
    """RSS bieżącego procesu w KiB (0, gdy psutil niedostępny)."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024.0
    except Exception:
        return 0.0


def make_compute(ops: int, detail: str = "", wall_ms: float | None = None,
                 rss: float | None = None, cpu_ms: float | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ops": int(ops),
        "detail": detail,
        "rss_kb": round(rss if rss is not None else rss_kb(), 1),
    }
    if wall_ms is not None:
        out["wall_ms"] = round(wall_ms, 4)
    if cpu_ms is not None:
        out["cpu_ms"] = round(cpu_ms, 4)
    return out


def set_debug(bot: Any, *, family: str, ops: int, detail: str = "",
              mode: str | None = None, values: dict[str, float] | None = None,
              plan: list | None = None, rationale: str | None = None,
              wall_ms: float | None = None) -> None:
    """Ustawia `bot.debug` z polami dla Godota i metryk."""
    debug: dict[str, Any] = {
        "family": family,
        "compute": make_compute(ops, detail, wall_ms=wall_ms),
    }
    if mode is not None:
        debug["mode"] = mode
    if values is not None:
        debug["values"] = values
    if plan is not None:
        debug["plan"] = plan
    if rationale is not None:
        debug["rationale"] = rationale
    bot.debug = debug


def enrich_wall_ms(bot: Any, wall_ms: float, cpu_ms: float | None = None) -> None:
    """Dopina czas wall-clock (i opcjonalnie CPU) po zmierzeniu `act()` na zewnątrz."""
    info = getattr(bot, "debug", None) or {}
    compute = dict(info.get("compute") or {})
    compute["wall_ms"] = round(wall_ms, 4)
    if cpu_ms is not None:
        compute["cpu_ms"] = round(cpu_ms, 4)
    if "rss_kb" not in compute:
        compute["rss_kb"] = round(rss_kb(), 1)
    info = {**info, "compute": compute}
    bot.debug = info


def compute_totals(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Agregacja listy wpisów compute z kolejnych ticków jednego gracza."""
    if not traces:
        return {"ticks": 0, "wall_ms_sum": 0.0, "wall_ms_mean": 0.0, "wall_ms_max": 0.0,
                "cpu_ms_sum": 0.0, "cpu_ms_mean": 0.0,
                "ops_sum": 0, "ops_mean": 0.0, "rss_kb_mean": 0.0, "rss_kb_max": 0.0}
    wall = [float(t.get("wall_ms", 0.0)) for t in traces]
    cpu = [float(t.get("cpu_ms", t.get("wall_ms", 0.0))) for t in traces]
    ops = [int(t.get("ops", 0)) for t in traces]
    rss = [float(t.get("rss_kb", 0.0)) for t in traces]
    n = len(traces)
    return {
        "ticks": n,
        "wall_ms_sum": round(sum(wall), 4),
        "wall_ms_mean": round(sum(wall) / n, 4),
        "wall_ms_max": round(max(wall), 4),
        "cpu_ms_sum": round(sum(cpu), 4),
        "cpu_ms_mean": round(sum(cpu) / n, 4),
        "ops_sum": sum(ops),
        "ops_mean": round(sum(ops) / n, 2),
        "rss_kb_mean": round(sum(rss) / n, 1),
        "rss_kb_max": round(max(rss), 1),
    }
