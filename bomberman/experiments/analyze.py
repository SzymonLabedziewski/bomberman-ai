"""Analiza wyników: przedziały Wilsona, wykresy, summary.json i tables.md."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from bomberman.config import PROJECT_ROOT  # noqa: E402
from bomberman.experiments.runner import RESULTS_DIR  # noqa: E402

BOT_ORDER = ["Random", "RandomSafe", "Planner", "MonteCarlo", "Q-Learning (AI)"]
VARIANT_ORDER = [
    "bez fizyki",
    "bez fizyki + przeszkody",
    "z fizyką",
    "z fizyką + przeszkody",
]
COLORS = {"win": "#4caf50", "draw": "#9e9e9e", "loss": "#e57373"}
ASSUMED_CPU_WATTS = 15.0

TOURNAMENT_SPECS = (
    ("E1", "bez fizyki (bez przeszkód)", "bez fizyki"),
    ("E1_obs", "bez fizyki + ruchome przeszkody", "bez fizyki + przeszkody"),
    ("E2", "z fizyką (kopanie + odrzut, bez przeszkód)", "z fizyką"),
    ("E2_obs", "z fizyką (kopanie + odrzut) + ruchome przeszkody", "z fizyką + przeszkody"),
)


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float, float]:
    """Odsetek k/n z 95% przedziałem ufności Wilsona."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0.0, (center - margin) / d), min(1.0, (center + margin) / d)


def _ordered(labels) -> list[str]:
    labels = list(labels)
    return sorted(labels, key=lambda b: (BOT_ORDER.index(b) if b in BOT_ORDER else len(BOT_ORDER), b))


def aggregate_matches(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Metryki dla grup wierszy (gra, gracz)."""
    rows = []
    for key, g in df.groupby(keys, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        n = len(g)
        wins, draws, losses = (g["result"] == "win").sum(), (g["result"] == "draw").sum(), (g["result"] == "loss").sum()
        win, win_lo, win_hi = wilson(wins, n)
        loss, loss_lo, loss_hi = wilson(losses, n)
        esc, esc_lo, esc_hi = wilson(g["escapable_success"].sum(), g["escapable_episodes"].sum())
        hopeless = g["escape_episodes"].sum() - g["escapable_episodes"].sum()
        hopeless_ok = g["escape_success"].sum() - g["escapable_success"].sum()
        deaths = g["died"].sum()
        dec_mean = g["decision_ms_mean"].mean()
        dec_sum = g["decision_ms_sum"].mean() if "decision_ms_sum" in g else (dec_mean * g["ticks"].mean())
        cpu_mean = g["cpu_ms_mean"].mean() if "cpu_ms_mean" in g else dec_mean
        cpu_sum = g["cpu_ms_sum"].mean() if "cpu_ms_sum" in g else dec_sum
        ops_mean = g["ops_mean"].mean() if "ops_mean" in g else 0.0
        ops_sum = g["ops_sum"].mean() if "ops_sum" in g else (ops_mean * g["ticks"].mean())
        rss_mean = g["rss_kb_mean"].mean() if "rss_kb_mean" in g else 0.0
        rss_max = g["rss_kb_max"].max() if "rss_kb_max" in g else rss_mean
        energy_mwh_game = (cpu_sum / 1000.0) / 3600.0 * ASSUMED_CPU_WATTS * 1000.0
        rows.append({
            **dict(zip(keys, key)),
            "games": n, "wins": int(wins), "draws": int(draws), "losses": int(losses),
            "win_rate": win, "win_lo": win_lo, "win_hi": win_hi,
            "draw_rate": draws / n, "loss_rate": loss, "loss_lo": loss_lo, "loss_hi": loss_hi,
            "suicides_per_100": 100 * g["suicides"].sum() / max(1, g["ticks"].sum()),
            "suicides_per_game": g["suicides"].mean(),
            "self_kill_rate": g["self_kill"].mean(),
            "escape_rate": esc, "escape_lo": esc_lo, "escape_hi": esc_hi,
            "escapable_episodes": int(g["escapable_episodes"].sum()),
            "hopeless_episodes": int(hopeless), "hopeless_survived": int(hopeless_ok),
            "escape_ticks": g["escape_ticks_sum"].sum() / max(1, g["escape_success"].sum()),
            "decision_ms": dec_mean,
            "decision_ms_max": g["decision_ms_max"].max(),
            "decision_ms_sum": dec_sum,
            "cpu_ms_mean": cpu_mean,
            "cpu_ms_sum": cpu_sum,
            "energy_mwh_game": energy_mwh_game,
            "ops_mean": ops_mean,
            "ops_sum": ops_sum,
            "rss_kb_mean": rss_mean,
            "rss_kb_max": rss_max,
            "family": g["family"].mode().iloc[0] if "family" in g and len(g["family"].dropna()) else "",
            "ticks": g["ticks"].mean(), "kicks_per_game": g["kicks"].mean(),
            "bombs_per_game": g["bombs_placed"].mean(),
            "deaths": int(deaths), "physics_death_share": g["death_physics"].sum() / deaths if deaths else 0.0,
        })
    return pd.DataFrame(rows)


def aggregate_escape(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, bot), g in df.groupby(["variant", "bot"], sort=False):
        rate, lo, hi = wilson(g["success"].sum(), len(g))
        e = g[g["escapable"] == 1]
        e_rate, e_lo, e_hi = wilson(e["success"].sum(), len(e))
        ok = g[g["success"] == 1]
        rows.append({"variant": variant, "bot": bot, "scenarios": len(g), "success_rate": rate,
                     "success_lo": lo, "success_hi": hi, "escapable": len(e), "escapable_rate": e_rate,
                     "escapable_lo": e_lo, "escapable_hi": e_hi,
                     "hopeless": len(g) - len(e), "hopeless_survived": int(g[g["escapable"] == 0]["success"].sum()),
                     "ticks_to_safety": ok["ticks"].mean() if len(ok) else 0.0})
    return pd.DataFrame(rows)


def _chart(cid: str, title: str, ylabel: str, labels: list[str], series: list[dict[str, Any]],
           percent: bool = True) -> dict[str, Any]:
    return {"id": cid, "title": title, "ylabel": ylabel, "labels": labels, "series": series, "percent": percent}


def _series(name: str, values, lo=None, hi=None) -> dict[str, Any]:
    s = {"name": name, "values": [round(float(v), 4) for v in values]}
    if lo is not None:
        s["ci_low"] = [round(float(v), 4) for v in lo]
        s["ci_high"] = [round(float(v), 4) for v in hi]
    return s


def _plot_grouped(chart: dict[str, Any], path: Path) -> None:
    labels, series = chart["labels"], chart["series"]
    fig, ax = plt.subplots(figsize=(max(6.8, 1.45 * len(labels) + 2.2), 4.5))
    width = 0.82 / max(1, len(series))
    scale = 100 if chart["percent"] else 1
    for i, s in enumerate(series):
        xs = [j + (i - (len(series) - 1) / 2) * width for j in range(len(labels))]
        vals = [v * scale for v in s["values"]]
        err = None
        if "ci_low" in s:
            err = [[max(0.0, (v - lo) * scale) for v, lo in zip(s["values"], s["ci_low"])],
                   [max(0.0, (hi - v) * scale) for v, hi in zip(s["values"], s["ci_high"])]]
        ax.bar(xs, vals, width, yerr=err, capsize=3, label=s["name"])
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=15 if len(labels) > 4 else 0, ha="right" if len(labels) > 4 else "center")
    ax.set_ylabel(chart["ylabel"])
    ax.set_title(chart["title"])
    if chart["percent"]:
        ax.set_ylim(0, 120 if len(series) > 1 else 105)
    if len(series) > 1:
        ax.legend(loc="upper center", ncol=min(len(series), 4), fontsize=8.5, framealpha=0.95)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_matchups(agg: pd.DataFrame, title: str, path: Path) -> dict[str, Any]:
    """Wygrane / remisy / porażki pierwszego bota z pary, para po parze (słupki skumulowane)."""
    pairs = []
    for matchup, g in agg.groupby("matchup", sort=False):
        first = matchup.split(" vs ")[0]
        r = g[g["bot"] == first].iloc[0]
        pairs.append((matchup, r["win_rate"], r["draw_rate"], r["loss_rate"]))
    fig, ax = plt.subplots(figsize=(8.6, 0.55 * len(pairs) + 1.6))
    for i, (label, w, d, l) in enumerate(pairs):
        ax.barh(i, w * 100, color=COLORS["win"])
        ax.barh(i, d * 100, left=w * 100, color=COLORS["draw"])
        ax.barh(i, l * 100, left=(w + d) * 100, color=COLORS["loss"])
    ax.set_yticks(range(len(pairs)))
    ax.set_yticklabels([p[0] for p in pairs])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% gier (zielony: wygrywa pierwszy bot, szary: remis, czerwony: wygrywa drugi)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return _chart(path.stem, title, "% gier", [p[0] for p in pairs],
                  [_series("wygrana pierwszego", [p[1] for p in pairs]), _series("remis", [p[2] for p in pairs]),
                   _series("wygrana drugiego", [p[3] for p in pairs])])


def _sort_kd(agg: pd.DataFrame) -> pd.DataFrame:
    """Warianty E4 w kolejności liczbowej (K, potem D), a nie alfabetycznej."""
    agg = agg.copy()
    agg["K"] = agg["variant"].str.extract(r"K=(\d+)", expand=False).astype(int)
    agg["D"] = agg["variant"].str.extract(r"D=(\d+)", expand=False).astype(int)
    return agg.sort_values(["K", "D"]).reset_index(drop=True)


def _plot_e4(agg: pd.DataFrame, path: Path) -> list[dict[str, Any]]:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for d, g in agg.sort_values("K").groupby("D"):
        axes[0].plot(g["K"], g["loss_rate"] * 100, marker="o", label=f"D={d}")
        axes[1].plot(g["K"], g["suicides_per_100"], marker="o", label=f"D={d}")
        axes[2].plot(g["K"], g["decision_ms"], marker="o", label=f"D={d}")
    titles = ["Porażki Monte Carlo [%]", "Ruchy samobójcze na 100 ticków", "Czas decyzji [ms]"]
    for ax, t in zip(axes, titles):
        ax.set_xscale("log")
        ax.set_xticks([10, 30, 100])
        ax.set_xticklabels(["10", "30", "100"])
        ax.set_xlabel("liczba symulacji K")
        ax.set_title(t)
        ax.grid(alpha=0.3)
        ax.legend()
    axes[2].set_yscale("log")
    fig.suptitle("E4: Monte Carlo przeciw Plannerowi, kompromis jakość / czas")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    labels = list(agg["variant"])
    return [
        _chart("E4_outcomes", "E4: wyniki Monte Carlo przeciw Plannerowi", "% gier", labels,
               [_series("wygrane MC", agg["win_rate"], agg["win_lo"], agg["win_hi"]),
                _series("porażki MC", agg["loss_rate"], agg["loss_lo"], agg["loss_hi"])]),
        _chart("E4_time", "E4: czas decyzji Monte Carlo", "ms", labels,
               [_series("czas decyzji [ms]", agg["decision_ms"])], percent=False),
    ]


def _load_training_costs(results_dir: Path) -> dict[str, Any]:
    """Koszty treningu modeli q_pure* i historyczny ledger."""
    models_dir = PROJECT_ROOT / "bomberman" / "ai" / "models"
    no_phys_meta_path = models_dir / "q_pure.train.meta.json"
    phys_meta_path = models_dir / "q_pure_physics.train.meta.json"
    ledger_path = results_dir / "ai_cost_ledger.json"
    if not ledger_path.exists():
        ledger_path = RESULTS_DIR / "ai_cost_ledger.json"

    out: dict[str, Any] = {
        "q_pure": {},
        "q_pure_physics": {},
        "active_models_energy_wh": 0.0,
        "active_models_wall_s": 0.0,
        "active_models_cpu_s": 0.0,
        "active_models_episodes": 0,
        "ledger_total_energy_wh": 0.0,
        "ledger_total_wall_s": 0.0,
        "ledger_total_cpu_s": 0.0,
        "ledger_total_episodes": 0,
        "model_files_kb": {},
    }
    for key, p in (("q_pure", no_phys_meta_path), ("q_pure_physics", phys_meta_path)):
        if p.exists():
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
                out[key] = m
                out["active_models_energy_wh"] += float(m.get("energy_wh_est", 0.0))
                out["active_models_wall_s"] += float(m.get("wall_seconds", 0.0))
                out["active_models_cpu_s"] += float(m.get("cpu_seconds_est", 0.0))
                out["active_models_episodes"] += int(m.get("episodes", 0))
            except Exception:
                pass
        json_file = models_dir / f"{key}.json"
        if json_file.exists():
            out["model_files_kb"][key] = round(json_file.stat().st_size / 1024.0, 1)

    if ledger_path.exists():
        try:
            led = json.loads(ledger_path.read_text(encoding="utf-8"))
            out["ledger_total_energy_wh"] = float(led.get("total_energy_wh_est", 0.0))
            out["ledger_total_wall_s"] = float(led.get("total_wall_seconds", 0.0))
            out["ledger_total_cpu_s"] = float(led.get("total_cpu_seconds_est", 0.0))
            out["ledger_total_episodes"] = int(led.get("total_episodes", 0))
        except Exception:
            pass
    return out


def _plot_efficiency_and_breakeven(both: pd.DataFrame, train_info: dict[str, Any], path: Path) -> dict[str, Any]:
    """Skuteczność vs czas ruchu, CPU na grę i próg opłacalności treningu."""
    overall = both.groupby("bot", as_index=False).agg({
        "games": "sum",
        "wins": "sum",
        "draws": "sum",
        "losses": "sum",
        "decision_ms": "mean",
        "decision_ms_max": "max",
        "decision_ms_sum": "mean",
        "cpu_ms_mean": "mean",
        "cpu_ms_sum": "mean",
        "energy_mwh_game": "mean",
        "ops_mean": "mean",
        "ops_sum": "mean",
        "rss_kb_mean": "mean",
    })
    overall["win_rate"] = overall["wins"] / overall["games"].clip(lower=1)
    labels = _ordered(overall["bot"].unique())
    overall = overall.set_index("bot").reindex(labels).reset_index()

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6))

    ax0 = axes[0]
    for _, r in overall.iterrows():
        x = max(0.005, float(r["decision_ms"]))
        y = float(r["win_rate"]) * 100.0
        ax0.scatter(x, y, s=95, zorder=3, label=r["bot"])
        ax0.annotate(r["bot"], (x, y), textcoords="offset points", xytext=(6, 5), fontsize=8.5)
    ax0.set_xscale("log")
    ax0.set_xlabel("Średni czas decyzji na ruch [ms, skala log]")
    ax0.set_ylabel("Odsetek zwycięstw ogółem [%]")
    ax0.set_title("Skuteczność vs czas ruchu")
    ax0.set_ylim(0, 100)
    ax0.grid(alpha=0.3)

    ax1 = axes[1]
    vals_cpu = [max(0.1, float(v)) for v in overall["cpu_ms_sum"]]
    bars = ax1.bar(range(len(labels)), vals_cpu, color="#42a5f5")
    ax1.set_yscale("log")
    ax1.set_xticks(range(len(labels)))
    ax1.set_xticklabels(labels, rotation=18, ha="right")
    ax1.set_ylabel("Czas CPU na 1 grę [ms, skala log]")
    ax1.set_title("Obciążenie procesora na 1 rozgrywkę")
    ax1.grid(axis="y", alpha=0.3)
    for b, v in zip(bars, vals_cpu):
        ax1.text(b.get_x() + b.get_width() / 2, v * 1.12, f"{v:.0f} ms",
                 ha="center", va="bottom", fontsize=8)

    ax2 = axes[2]
    mc_mwh = float(overall.loc[overall["bot"] == "MonteCarlo", "energy_mwh_game"].iloc[0]) \
        if "MonteCarlo" in overall["bot"].values else 0.04
    pl_mwh = float(overall.loc[overall["bot"] == "Planner", "energy_mwh_game"].iloc[0]) \
        if "Planner" in overall["bot"].values else 0.001
    ql_mwh = float(overall.loc[overall["bot"] == "Q-Learning (AI)", "energy_mwh_game"].iloc[0]) \
        if "Q-Learning (AI)" in overall["bot"].values else 0.0008

    active_wh = float(train_info.get("active_models_energy_wh") or 7.74)
    max_games = 300_000
    if mc_mwh > ql_mwh and active_wh > 0:
        be_games = int((active_wh * 1000.0) / (mc_mwh - ql_mwh))
        max_games = max(10_000, int(be_games * 1.6))
    xs = [0, max_games // 4, max_games // 2, (3 * max_games) // 4, max_games]
    ax2.plot(xs, [n * mc_mwh / 1000.0 for n in xs], label="MonteCarlo (0 Wh start + gra)", linewidth=2)
    ax2.plot(xs, [n * pl_mwh / 1000.0 for n in xs], label="Planner (0 Wh start + gra)", linewidth=2)
    ax2.plot(xs, [active_wh + n * ql_mwh / 1000.0 for n in xs],
             label=f"Q-Learning ({active_wh:.1f} Wh trening + gra)", linewidth=2, linestyle="--")
    if mc_mwh > ql_mwh and active_wh > 0:
        be_n = (active_wh * 1000.0) / (mc_mwh - ql_mwh)
        be_y = active_wh + be_n * ql_mwh / 1000.0
        ax2.scatter([be_n], [be_y], color="red", zorder=5)
        ax2.annotate(f"Break-even:\n~{int(round(be_n)):,} gier".replace(",", " "),
                     (be_n, be_y), textcoords="offset points", xytext=(-55, -28), fontsize=8.5,
                     arrowprops={"arrowstyle": "->", "color": "red"})
    ax2.set_xlabel("Liczba rozegranych rund z człowiekiem")
    ax2.set_ylabel("Skumulowana energia [Wh]")
    ax2.set_title("Koszt środowiskowy: AI vs algorytmy")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)

    return _chart(
        "bot_efficiency_cost",
        "Porównanie zasobów: czas CPU na grę [ms] i czas decyzji [ms]",
        "ms",
        labels,
        [
            _series("decyzja śr. [ms]", overall["decision_ms"]),
            _series("CPU na grę [s]", [v / 1000.0 for v in overall["cpu_ms_sum"]]),
        ],
        percent=False,
    )


def _compare_obstacles_pair(
    base_bots: pd.DataFrame,
    obs_bots: pd.DataFrame,
    base_label: str,
    obs_label: str,
    prefix: str,
    title_prefix: str,
    plots: Path,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Porównanie wariantu bez przeszkód i z ruchomymi przeszkodami."""
    labels = _ordered(set(base_bots["bot"]).union(set(obs_bots["bot"])))
    b_idx = base_bots.set_index("bot").reindex(labels).fillna(0)
    o_idx = obs_bots.set_index("bot").reindex(labels).fillna(0)

    charts = []
    for suffix, what, ylabel, metric, ci in (
        ("winrate", "odsetek zwycięstw", "% gier", "win_rate", ("win_lo", "win_hi")),
        ("escape", "skuteczność ucieczki", "% epizodów", "escape_rate", ("escape_lo", "escape_hi")),
        ("cost", "średni czas decyzji [ms]", "ms", "decision_ms", None),
    ):
        unit = " [ms]" if ci is None else ""
        series = [_series(label + unit, idx[metric], idx[ci[0]] if ci else None, idx[ci[1]] if ci else None)
                  for label, idx in ((base_label, b_idx), (obs_label, o_idx))]
        chart = _chart(f"{prefix}_{suffix}", f"{title_prefix}: {what} (bez przeszkód vs ruchome przeszkody)",
                       ylabel, labels, series, percent=ci is not None)
        _plot_grouped(chart, plots / f"{prefix}_{suffix}.png")
        charts.append(chart)

    comp_rows = []
    for bot in labels:
        rb = b_idx.loc[bot]
        ro = o_idx.loc[bot]
        comp_rows.append({
            "bot": bot,
            "wr_no_obs": float(rb["win_rate"]),
            "wr_obs": float(ro["win_rate"]),
            "wr_diff_pp": round((float(ro["win_rate"]) - float(rb["win_rate"])) * 100.0, 2),
            "esc_no_obs": float(rb["escape_rate"]),
            "esc_obs": float(ro["escape_rate"]),
            "suic_no_obs": float(rb["suicides_per_100"]),
            "suic_obs": float(ro["suicides_per_100"]),
            "ms_no_obs": float(rb["decision_ms"]),
            "ms_obs": float(ro["decision_ms"]),
            "cpu_game_no_obs": float(rb["cpu_ms_sum"]),
            "cpu_game_obs": float(ro["cpu_ms_sum"]),
            "ops_no_obs": float(rb["ops_mean"]),
            "ops_obs": float(ro["ops_mean"]),
            "ram_no_obs": float(rb["rss_kb_mean"]),
            "ram_obs": float(ro["rss_kb_mean"]),
        })
    return charts, pd.DataFrame(comp_rows)


def analyze(results_dir: Path = RESULTS_DIR) -> dict[str, Any]:
    plots = results_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    charts: list[dict[str, Any]] = []
    tables: dict[str, list[dict[str, Any]]] = {}
    md: list[str] = ["# Wyniki eksperymentów i analiza zasobów", ""]

    def load(name: str) -> pd.DataFrame | None:
        path = results_dir / f"{name}.csv"
        return pd.read_csv(path) if path.exists() else None

    per_bot: list[pd.DataFrame] = []
    bots_by_exp: dict[str, pd.DataFrame] = {}
    tournament_frames: list[pd.DataFrame] = []

    for name, title, short_var in TOURNAMENT_SPECS:
        df = load(name)
        if df is None:
            continue
        df = df.copy()
        df["variant"] = short_var
        tournament_frames.append(df)
        pairs = aggregate_matches(df, ["matchup", "bot"])
        charts.append(_plot_matchups(pairs, f"{name}: {title}, wyniki par", plots / f"{name}_matchups.png"))
        bots = aggregate_matches(df, ["bot"])
        bots["experiment"] = name
        bots["variant"] = short_var
        per_bot.append(bots)
        bots_by_exp[name] = bots
        tables[f"{name}_pairs"] = _records(pairs)
        tables[f"{name}_bots"] = _records(bots)
        md += _md_table(f"{name} ({title}): wyniki par (z perspektywy pierwszego bota w nazwie pary)",
                        pairs[pairs.apply(lambda r: r["matchup"].startswith(r["bot"] + " vs"), axis=1)],
                        ["matchup", "games", "wins", "draws", "losses", "win_rate", "draw_rate", "loss_rate"])
        md += _md_table(f"{name} ({title}): skuteczność i bezpieczeństwo botów (wszystkie gry)", bots,
                        ["bot", "games", "wins", "draws", "losses", "win_rate", "win_lo", "win_hi",
                         "suicides_per_100", "self_kill_rate", "escape_rate", "escape_ticks",
                         "bombs_per_game", "kicks_per_game", "physics_death_share"])
        md += _md_table(f"{name} ({title}): zużycie zasobów obliczeniowych i pamięci", bots,
                        ["bot", "family", "ticks", "decision_ms", "decision_ms_max", "decision_ms_sum",
                         "cpu_ms_mean", "cpu_ms_sum", "ops_mean", "ops_sum", "rss_kb_mean", "rss_kb_max",
                         "energy_mwh_game"])

    # E1 i E2 razem (bez przeszkód)
    if "E1" in bots_by_exp and "E2" in bots_by_exp:
        e1_e2_both = pd.concat([bots_by_exp["E1"], bots_by_exp["E2"]], ignore_index=True)
        labels = _ordered(e1_e2_both["bot"].unique())
        for metric, cid, title, ylabel, ci in (
            ("win_rate", "E1_E2_winrate", "Odsetek zwycięstw (95% CI): E1 (bez fizyki) vs E2 (z fizyką)", "% gier", ("win_lo", "win_hi")),
            ("escape_rate", "E1_E2_escape", "Skuteczność ucieczki: E1 (bez fizyki) vs E2 (z fizyką)",
             "% epizodów", ("escape_lo", "escape_hi")),
            ("suicides_per_100", "E1_E2_suicides", "Ruchy samobójcze na 100 ticków: E1 vs E2", "liczba", None),
        ):
            series = []
            for exp_id, var_name in (("E1", "bez fizyki"), ("E2", "z fizyką")):
                g = bots_by_exp[exp_id].set_index("bot").reindex(labels).fillna(0)
                series.append(_series(var_name, g[metric],
                                      g[ci[0]] if ci else None, g[ci[1]] if ci else None))
            chart = _chart(cid, title, ylabel, labels, series, percent=metric != "suicides_per_100")
            _plot_grouped(chart, plots / f"{cid}.png")
            charts.append(chart)
    elif per_bot:
        both_tmp = pd.concat(per_bot, ignore_index=True)
        labels = _ordered(both_tmp["bot"].unique())
        for metric, cid, title, ylabel, ci in (
            ("win_rate", "E1_E2_winrate", "Odsetek zwycięstw (95% CI), wszystkie pary", "% gier", ("win_lo", "win_hi")),
            ("escape_rate", "E1_E2_escape", "Skuteczność ucieczki z sytuacji, z których dało się uciec",
             "% epizodów", ("escape_lo", "escape_hi")),
            ("suicides_per_100", "E1_E2_suicides", "Ruchy samobójcze na 100 ticków", "liczba", None),
        ):
            series = []
            for exp_id, g in both_tmp.groupby("experiment", sort=False):
                g = g.set_index("bot").reindex(labels).fillna(0)
                series.append(_series(str(exp_id), g[metric],
                                      g[ci[0]] if ci else None, g[ci[1]] if ci else None))
            chart = _chart(cid, title, ylabel, labels, series, percent=metric != "suicides_per_100")
            _plot_grouped(chart, plots / f"{cid}.png")
            charts.append(chart)

    for base, phys, table_key in (("E1", "bez fizyki", "compare_no_physics_obstacles"),
                                  ("E2", "z fizyką", "compare_physics_obstacles")):
        obs = f"{base}_obs"
        if base not in bots_by_exp or obs not in bots_by_exp:
            continue
        c_list, comp_df = _compare_obstacles_pair(
            bots_by_exp[base], bots_by_exp[obs], f"{phys} (bez przeszkód)", f"{phys} + ruchome przeszkody",
            f"{base}_vs_{obs}", f"Porównanie {phys} ({base} vs {obs})", plots,
        )
        charts.extend(c_list)
        tables[table_key] = _records(comp_df)
        md += _md_table(
            f"Porównanie: ({phys}, bez przeszkód) vs ({phys} + ruchome przeszkody) [{base} vs {obs}]",
            comp_df,
            ["bot", "wr_no_obs", "wr_obs", "wr_diff_pp", "esc_no_obs", "esc_obs",
             "suic_no_obs", "suic_obs", "ms_no_obs", "ms_obs", "cpu_game_no_obs", "cpu_game_obs",
             "ops_no_obs", "ops_obs", "ram_no_obs", "ram_obs"],
        )

    # wszystkie warianty razem (gdy są co najmniej trzy)
    if len(per_bot) >= 3:
        all_both = pd.concat(per_bot, ignore_index=True)
        labels = _ordered(all_both["bot"].unique())
        for metric, cid, title, ylabel, ci, is_pct in (
            ("win_rate", "all4_variants_winrate", "Porównanie 4 wariantów środowiska: odsetek zwycięstw", "% gier", ("win_lo", "win_hi"), True),
            ("escape_rate", "all4_variants_escape", "Porównanie 4 wariantów środowiska: skuteczność ucieczki", "% epizodów", ("escape_lo", "escape_hi"), True),
            ("suicides_per_100", "all4_variants_suicides", "Porównanie 4 wariantów środowiska: ruchy samobójcze / 100 t.", "liczba", None, False),
            ("decision_ms", "all4_variants_cost", "Porównanie 4 wariantów środowiska: czas decyzji [ms]", "ms", None, False),
        ):
            series = []
            for exp_id, _, short_var in TOURNAMENT_SPECS:
                if exp_id not in bots_by_exp:
                    continue
                g = bots_by_exp[exp_id].set_index("bot").reindex(labels).fillna(0)
                series.append(_series(short_var, g[metric],
                                      g[ci[0]] if ci else None, g[ci[1]] if ci else None))
            ch = _chart(cid, title, ylabel, labels, series, percent=is_pct)
            _plot_grouped(ch, plots / f"{cid}.png")
            charts.append(ch)

    if per_bot:
        both = pd.concat(per_bot, ignore_index=True)
        train_info = _load_training_costs(results_dir)
        eff_chart = _plot_efficiency_and_breakeven(both, train_info, plots / "bot_efficiency_cost.png")
        charts.append(eff_chart)

        if len(tournament_frames) >= 2:
            combined_df = pd.concat(tournament_frames, ignore_index=True)
            comb_pairs = aggregate_matches(combined_df, ["matchup", "bot"])
            comb_bots = aggregate_matches(combined_df, ["bot"])
            tables["combined_pairs"] = _records(comb_pairs)
            tables["combined_bots"] = _records(comb_bots)
            md += _md_table(
                "Turniej łączny (wszystkie warianty): wyniki par",
                comb_pairs[comb_pairs.apply(lambda r: r["matchup"].startswith(r["bot"] + " vs"), axis=1)],
                ["matchup", "games", "wins", "draws", "losses", "win_rate", "draw_rate", "loss_rate"],
            )
            md += _md_table(
                "Turniej łączny (wszystkie warianty): ranking i zasoby botów",
                comb_bots,
                ["bot", "family", "games", "wins", "draws", "losses", "win_rate",
                 "decision_ms", "cpu_ms_sum", "ops_mean", "rss_kb_mean", "energy_mwh_game"],
            )

        be_rows = _build_breakeven_rows(both, train_info)
        if be_rows:
            tables["break_even"] = be_rows
            be_df = pd.DataFrame(be_rows)
            md += _md_table(
                "Analiza środowiskowa i próg opłacalności (Break-Even) przy grze z człowiekiem",
                be_df,
                ["variant", "reference_bot", "ref_ms_game", "q_ms_game", "saved_ms_game",
                 "saved_mwh_game", "train_energy_wh", "breakeven_games_model",
                 "ledger_energy_wh", "breakeven_games_ledger"],
            )

    df = load("E4")
    if df is not None:
        agg = _sort_kd(aggregate_matches(df[df["bot"].str.startswith("MC")], ["variant"]))
        charts += _plot_e4(agg, plots / "E4_grid.png")
        tables["E4"] = _records(agg)
        md += _md_table("E4: Monte Carlo (K, D) przeciw Plannerowi, bez fizyki", agg,
                        ["variant", "games", "win_rate", "draw_rate", "loss_rate", "suicides_per_100",
                         "escape_rate", "decision_ms", "decision_ms_max"])

    df = load("E5")
    if df is not None:
        agg = aggregate_escape(df)
        labels = _ordered(agg["bot"].unique())
        for metric, cid, title in (("success_rate", "E5_all", "E5: przeżyte sytuacje zagrożenia (wszystkie)"),
                                   ("escapable_rate", "E5_escapable", "E5: przeżyte sytuacje, z których dało się uciec")):
            series = []
            prefix = metric.split("_")[0]
            for variant, g in agg.groupby("variant", sort=False):
                g = g.set_index("bot").reindex(labels).fillna(0)
                series.append(_series(variant, g[metric], g[f"{prefix}_lo"], g[f"{prefix}_hi"]))
            chart = _chart(cid, title, "% sytuacji", labels, series)
            _plot_grouped(chart, plots / f"{cid}.png")
            charts.append(chart)
        tables["E5"] = _records(agg)
        md += _md_table("E5: ucieczka z 500 losowych sytuacji zagrożenia", agg,
                        ["variant", "bot", "scenarios", "success_rate", "escapable", "escapable_rate",
                         "hopeless", "hopeless_survived", "ticks_to_safety"])

    # E6 wyciągnięte z turniejów, gdy nie ma E6.csv
    df_e6 = load("E6")
    if df_e6 is None and tournament_frames:
        combined_q = pd.concat(tournament_frames, ignore_index=True)
        q_games = combined_q[
            (combined_q["bot"] == "Q-Learning (AI)") | (combined_q["opponent"] == "Q-Learning (AI)")
        ].copy()
        if len(q_games) > 0:
            df_e6 = q_games

    if df_e6 is not None and len(df_e6) > 0:
        ql = df_e6[df_e6["bot"] == "Q-Learning (AI)"]
        if len(ql) > 0:
            agg = aggregate_matches(ql, ["variant", "opponent", "bot"])
            agg["matchup"] = "Q-Learning (AI) vs " + agg["opponent"]
            agg = agg.sort_values(
                ["variant", "opponent"],
                key=lambda s: s.map(
                    lambda v: VARIANT_ORDER.index(v) if v in VARIANT_ORDER
                    else (BOT_ORDER.index(v) if v in BOT_ORDER else 99)
                ),
            ).reset_index(drop=True)
            labels = [f"{r['variant']}: {r['opponent']}" for _, r in agg.iterrows()]
            chart = _chart(
                "E6_winrate",
                "Q-Learning (AI): odsetek zwycięstw i remisów vs wszystkie boty",
                "% gier",
                labels,
                [_series("wygrane Q", agg["win_rate"], agg["win_lo"], agg["win_hi"]),
                 _series("remisy Q", agg["draw_rate"]),
                 _series("porażki Q", agg["loss_rate"], agg["loss_lo"], agg["loss_hi"])],
            )
            _plot_grouped(chart, plots / "E6_winrate.png")
            charts.append(chart)
            cost = _chart(
                "E6_cost",
                "Koszt decyzji Q-Learning vs przeciwnik (ms / ops)",
                "ms",
                labels,
                [_series("decyzja Q [ms]", agg["decision_ms"]),
                 _series("ops Q (śr.)", agg["ops_mean"])],
                percent=False,
            )
            _plot_grouped(cost, plots / "E6_cost.png")
            charts.append(cost)
            opp = df_e6[df_e6["bot"] != "Q-Learning (AI)"]
            opp_agg = aggregate_matches(opp, ["variant", "bot", "family"])
            tables["E6_q"] = _records(agg)
            tables["E6_opponents"] = _records(opp_agg)
            md += _md_table(
                "Q-Learning (AI): bezpośrednie pojedynki i koszty (wszystkie warianty)",
                agg,
                ["variant", "matchup", "games", "wins", "draws", "losses", "win_rate", "draw_rate", "loss_rate",
                 "decision_ms", "cpu_ms_sum", "ops_mean", "rss_kb_mean", "kicks_per_game"],
            )
            md += _md_table(
                "Koszty przeciwników w pojedynkach z Q-Learning (AI)",
                opp_agg,
                ["variant", "bot", "family", "games", "win_rate", "decision_ms", "cpu_ms_sum", "ops_mean", "rss_kb_mean"],
            )

    meta = {}
    for path in sorted(results_dir.glob("E*.meta.json")):
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        meta[path.name.split(".")[0]] = {"title": m["config"].get("title", ""), "seconds": m["seconds"],
                                         "tasks": m["tasks"], "workers": m["workers"], "scale": m["scale"]}
    summary = {"generated": time.strftime("%Y-%m-%d %H:%M"), "experiments": meta, "charts": charts,
               "tables": tables}
    with open(results_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    with open(results_dir / "tables.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"Analiza: {len(charts)} wykresów w {plots}, podsumowanie w {results_dir / 'summary.json'}")
    return summary


def _build_breakeven_rows(both: pd.DataFrame, train_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Po ilu grach z człowiekiem zwraca się energia treningu Q-learningu."""
    rows: list[dict[str, Any]] = []
    ledger_wh = float(train_info.get("ledger_total_energy_wh") or 0.0)
    q_pure_wh = float((train_info.get("q_pure") or {}).get("energy_wh_est") or 0.0)
    q_phys_wh = float((train_info.get("q_pure_physics") or {}).get("energy_wh_est") or 0.0)
    active_wh = float(train_info.get("active_models_energy_wh") or (q_pure_wh + q_phys_wh))

    for exp, var_label, is_phys in (
        ("E1", "bez fizyki", False),
        ("E1_obs", "bez fizyki + przeszkody", False),
        ("E2", "z fizyką", True),
        ("E2_obs", "z fizyką + przeszkody", True),
    ):
        model_wh = (q_phys_wh if q_phys_wh > 0 else active_wh / 2) if is_phys else (q_pure_wh if q_pure_wh > 0 else active_wh / 2)
        sub = both[both["experiment"] == exp]
        if len(sub) == 0 or "Q-Learning (AI)" not in sub["bot"].values:
            continue
        q_row = sub[sub["bot"] == "Q-Learning (AI)"].iloc[0]
        q_ms_game = float(q_row["cpu_ms_sum"])
        q_mwh_game = float(q_row["energy_mwh_game"])
        for ref_bot in ("MonteCarlo", "Planner"):
            if ref_bot not in sub["bot"].values:
                continue
            r_row = sub[sub["bot"] == ref_bot].iloc[0]
            ref_ms_game = float(r_row["cpu_ms_sum"])
            ref_mwh_game = float(r_row["energy_mwh_game"])
            saved_ms = ref_ms_game - q_ms_game
            saved_mwh = ref_mwh_game - q_mwh_game
            if saved_mwh > 1e-9:
                be_model = int(math.ceil((model_wh * 1000.0) / saved_mwh))
                be_ledger = int(math.ceil((ledger_wh * 1000.0) / saved_mwh))
            else:
                be_model = -1
                be_ledger = -1
            rows.append({
                "variant": var_label,
                "reference_bot": ref_bot,
                "ref_ms_game": round(ref_ms_game, 1),
                "q_ms_game": round(q_ms_game, 1),
                "saved_ms_game": round(saved_ms, 1),
                "saved_mwh_game": round(saved_mwh, 4),
                "train_energy_wh": round(model_wh, 2),
                "breakeven_games_model": be_model,
                "ledger_energy_wh": round(ledger_wh, 2),
                "breakeven_games_ledger": be_ledger,
            })
    return rows


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for rec in df.to_dict("records"):
        out.append({k: (round(v, 4) if isinstance(v, float) else (int(v) if hasattr(v, "item") else v))
                    for k, v in rec.items()})
    return out


PERCENT_COLUMNS = {
    "win_rate", "win_lo", "win_hi", "draw_rate", "loss_rate", "self_kill_rate", "escape_rate",
    "physics_death_share", "success_rate", "escapable_rate",
    "wr_no_obs", "wr_obs", "esc_no_obs", "esc_obs",
}
HEADERS = {
    "matchup": "para", "bot": "bot", "variant": "wariant", "games": "gry",
    "wins": "W", "draws": "R", "losses": "P",
    "win_rate": "wygrane", "win_lo": "CI od", "win_hi": "CI do", "draw_rate": "remisy", "loss_rate": "porażki",
    "suicides_per_100": "samobójcze/100 t.", "self_kill_rate": "śmierć od własnej bomby",
    "escape_rate": "udane ucieczki", "escape_ticks": "ticki do bezp. pola",
    "decision_ms": "decyzja śr. [ms]", "decision_ms_max": "max decyzja [ms]",
    "decision_ms_sum": "czas decyzji/grę [ms]",
    "cpu_ms_mean": "CPU/ruch [ms]", "cpu_ms_sum": "CPU/grę [ms]",
    "energy_mwh_game": "energia/grę [mWh]",
    "ops_mean": "ops/ruch", "ops_sum": "ops/grę",
    "rss_kb_mean": "RAM śr. [KiB]", "rss_kb_max": "RAM max [KiB]",
    "family": "rodzina", "ticks": "śr. ticków", "bombs_per_game": "bomby/grę", "kicks_per_game": "kopnięcia/grę",
    "physics_death_share": "śmierci z fizyką", "scenarios": "sytuacje", "success_rate": "przeżyte",
    "escapable": "do uniknięcia", "escapable_rate": "przeżyte (do uniknięcia)", "hopeless": "bez wyjścia",
    "hopeless_survived": "przeżyte bez wyjścia", "ticks_to_safety": "ticki do bezp. pola",
    "reference_bot": "bot odniesienia", "ref_ms_game": "CPU odniesienia/grę [ms]",
    "q_ms_game": "CPU Q-Learning/grę [ms]", "saved_ms_game": "oszczędność CPU/grę [ms]",
    "saved_mwh_game": "oszczędność energii/grę [mWh]", "train_energy_wh": "koszt treningu modelu [Wh]",
    "breakeven_games_model": "próg zwrotu (1 model) [gier]",
    "ledger_energy_wh": "całkowity koszt R&D [Wh]", "breakeven_games_ledger": "próg zwrotu (całe R&D) [gier]",
    "wr_no_obs": "WR (bez przeszkód)", "wr_obs": "WR (+ przeszkody)", "wr_diff_pp": "zmiana WR [p.p.]",
    "esc_no_obs": "ucieczki (bez przeszk.)", "esc_obs": "ucieczki (+ przeszk.)",
    "suic_no_obs": "samob./100t (bez)", "suic_obs": "samob./100t (+ przeszk.)",
    "ms_no_obs": "decyzja [ms] (bez)", "ms_obs": "decyzja [ms] (+ przeszk.)",
    "cpu_game_no_obs": "CPU/grę [ms] (bez)", "cpu_game_obs": "CPU/grę [ms] (+ przeszk.)",
    "ops_no_obs": "ops/ruch (bez)", "ops_obs": "ops/ruch (+ przeszk.)",
    "ram_no_obs": "RAM [KiB] (bez)", "ram_obs": "RAM [KiB] (+ przeszk.)",
}


def _md_table(title: str, df: pd.DataFrame, columns: list[str]) -> list[str]:
    avail = [c for c in columns if c in df.columns]
    lines = [f"## {title}", "", "| " + " | ".join(HEADERS.get(c, c) for c in avail) + " |",
             "|" + "---|" * len(avail)]
    for rec in df.to_dict("records"):
        cells = []
        for c in avail:
            v = rec[c]
            if c in PERCENT_COLUMNS:
                cells.append(f"{100 * v:.1f}%")
            elif c == "wr_diff_pp":
                cells.append(f"{v:+.1f} p.p.")
            elif isinstance(v, float):
                cells.append(f"{v:.4f}" if abs(v) < 0.1 and v != 0 else f"{v:.2f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return lines + [""]
