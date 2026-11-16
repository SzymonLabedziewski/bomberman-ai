"""Wiersz poleceń: python -m bomberman {play,serve,train,experiment,analyze,reproduce}."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from bomberman.ai.registry import BOT_NAMES
from bomberman.config import load_config

DEMO_REPLAYS = [
    ("planner", "montecarlo", 3, True),
    ("planner", "montecarlo", 7, False),
    ("montecarlo", "randomsafe", 8, True),
    ("planner", "randomsafe", 14, True),
    ("planner", "randomsafe", 25, False),
    ("qlearner", "randomsafe", 11, False),
]


def _physics_flags(args: argparse.Namespace) -> dict[str, bool]:
    no_obs = getattr(args, "no_obstacles", False)
    return {
        "kick": bool(args.physics or getattr(args, "kick", False)),
        "knockback": bool(args.physics or getattr(args, "knockback", False)),
        "moving_obstacles": bool((args.physics or getattr(args, "obstacles", False)) and not no_obs),
    }


def cmd_play(args: argparse.Namespace) -> None:
    from bomberman.ai.telemetry import enrich_wall_ms
    from bomberman.engine.ascii_view import render
    from bomberman.engine.board import new_game
    from bomberman.engine.rules import step
    from bomberman.engine.serialize import save_replay, state_to_dict
    from bomberman.experiments.metrics import play_measured
    from bomberman.match import debug_payload, labels_for, make_bots

    cfg = load_config(args.config).with_physics(_physics_flags(args))
    names = [args.p1, args.p2]
    labels = labels_for(names)
    bots = make_bots(names, cfg, args.seed)

    def print_result(state) -> None:
        winner = "remis" if state.winner == -1 else f"wygrywa {'AB'[state.winner]} ({labels[state.winner]})"
        print(f"Koniec po {state.tick} tickach: {winner}")

    if args.stats:
        state, stats = play_measured(cfg, bots, args.seed)
        print_result(state)
        for pid, st in enumerate(stats):
            tot = st.totals()
            print(f"  {labels[pid]} [{st.family or '?'}]: "
                  f"decyzja śr. {tot['wall_ms_mean']:.3f} ms, "
                  f"ops śr. {tot['ops_mean']:.1f} (suma {tot['ops_sum']}), "
                  f"RSS śr. {tot['rss_kb_mean']:.0f} KiB")
        return

    state = new_game(cfg, args.seed)
    frames, events = [], []
    while True:
        if not args.quiet:
            print("\033[2J\033[H" if args.delay > 0 else "", end="")
            print(render(state, labels))
            print()
        if state.done:
            break
        actions = []
        for pid, bot in enumerate(bots):
            t0 = time.perf_counter()
            actions.append(bot.act(state, pid))
            enrich_wall_ms(bot, (time.perf_counter() - t0) * 1000)
        if args.save_replay is not None:
            frames.append(state_to_dict(state, events, debug_payload(state, cfg, bots, actions), labels))
        events = step(state, actions, cfg)
        if args.delay > 0:
            time.sleep(args.delay)
    print_result(state)
    if args.save_replay is not None:
        frames.append(state_to_dict(state, events, debug_payload(state, cfg, []), labels))
        path = Path(args.save_replay) if args.save_replay else (
            Path("results/replays") / f"{args.p1}_vs_{args.p2}_seed{args.seed}"
            f"{'_fizyka' if cfg.physics.enabled else ''}.json")
        meta = {"p1": labels[0], "p2": labels[1], "bots": names, "seed": args.seed, "winner": state.winner,
                "ticks": state.tick, "config": cfg.to_dict()}
        save_replay(path, frames, meta)
        print(f"Powtórka zapisana: {path}")


def cmd_train(args: argparse.Namespace) -> None:
    from bomberman.ai.q_table import DEFAULT_PHYSICS_TABLE_PATH, DEFAULT_TABLE_PATH
    from bomberman.ai.train import train_q

    phys_flags = _physics_flags(args)
    phys_enabled = any(phys_flags.values())
    default_out = DEFAULT_PHYSICS_TABLE_PATH if phys_enabled else DEFAULT_TABLE_PATH
    out = Path(args.out) if args.out else default_out
    print(f"Trening Q-learning: {args.episodes} epizodów, workers={args.workers}, "
          f"opponent={args.opponent}, physics={phys_flags if phys_enabled else False}, out={out}")
    meta = train_q(
        episodes=args.episodes, seed=args.seed,
        physics=phys_flags if phys_enabled else False,
        out_path=out, eval_games=args.eval_games, workers=args.workers,
        opponent=args.opponent, resume=args.resume,
        max_ticks=args.max_ticks,
    )
    print(f"Gotowe: stany={meta['n_states']}, czas={meta['wall_seconds']} s, "
          f"peak RSS={meta['peak_rss_mb']} MB, bomby={meta.get('train_bombs', '?')}, "
          f"kopnięcia={meta.get('train_kicks', 0)}")
    print(f"  koszt: ok. {meta.get('cpu_seconds_est')} s CPU, "
          f"ok. {meta.get('energy_wh_est')} Wh (P={meta.get('assumed_cpu_watts')} W)")
    ev = meta.get("final_eval") or {}
    for key, label in (("vs_randomsafe", "RandomSafe"), ("vs_planner", "Planner"), ("vs_montecarlo", "MonteCarlo")):
        r = ev.get(key)
        if r:
            print(f"  eval vs {label + ':':12} WR={r['win_rate']} draw={r['draw_rate']} loss={r['loss_rate']} "
                  f"bomb_rate={r['bomb_rate']} kicks/g={r['kicks_per_game']} self-kill={r['self_kill_rate']}")
    print("  (ewaluacja czystej polityki Q; przy bomb_rate bliskim 0 wygrane z RandomSafe nic nie znaczą,"
          " patrz docs/qlearning.md)")
    print(f"Tablica: {meta['table_path']}")
    print(f"Meta treningu: {meta['meta_path']}")
    print("Ledger kosztów: results/ai_cost_ledger.json")


def cmd_serve(args: argparse.Namespace) -> None:
    from bomberman.server import main as serve_main

    serve_main(args.host, args.port)


def cmd_experiment(args: argparse.Namespace) -> None:
    from bomberman.experiments.runner import RESULTS_DIR, run_experiment

    run_experiment(args.config, workers=args.workers, scale=args.scale, out_dir=Path(args.out or RESULTS_DIR))


def cmd_analyze(args: argparse.Namespace) -> None:
    from bomberman.experiments.analyze import analyze
    from bomberman.experiments.runner import RESULTS_DIR

    analyze(Path(args.out or RESULTS_DIR))


def cmd_reproduce(args: argparse.Namespace) -> None:
    from bomberman.experiments.analyze import analyze
    from bomberman.experiments.runner import RESULTS_DIR, experiment_paths, run_experiment

    out = Path(args.out) if args.out else (RESULTS_DIR / "quick" if args.quick else RESULTS_DIR)
    scale = 0.1 if args.quick else 1.0
    t0 = time.perf_counter()
    for path in experiment_paths():
        run_experiment(path, workers=args.workers, scale=scale, out_dir=out)
    analyze(out)
    save_demo_replays(out / "replays")
    print(f"Gotowe w {(time.perf_counter() - t0) / 60:.1f} min. Wyniki: {out}")


def save_demo_replays(directory: Path) -> None:
    from bomberman.engine.serialize import save_replay
    from bomberman.match import record_game

    for p1, p2, seed, physics in DEMO_REPLAYS:
        cfg = load_config().with_physics(physics)
        replay = record_game(cfg, [p1, p2], seed)
        name = f"{p1}_vs_{p2}_seed{seed}{'_fizyka' if physics else ''}.json"
        save_replay(directory / name, replay["frames"], replay["meta"])
    print(f"Powtórki demonstracyjne: {directory}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m bomberman", description="Bomberman AI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("play", help="gra botów w terminalu (podgląd ASCII)")
    p.add_argument("--p1", default="planner", choices=BOT_NAMES)
    p.add_argument("--p2", default="montecarlo", choices=BOT_NAMES)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--physics", action="store_true", help="włącza całą fizykę")
    p.add_argument("--kick", action="store_true")
    p.add_argument("--knockback", action="store_true")
    p.add_argument("--obstacles", action="store_true", help="ruchome przeszkody")
    p.add_argument("--delay", type=float, default=0.15, help="sekundy między tickami (0 = bez animacji)")
    p.add_argument("--quiet", action="store_true", help="pokazuje tylko wynik")
    p.add_argument("--stats", action="store_true",
                   help="gra bez animacji i wypisuje koszty decyzji (ms, ops, RSS)")
    p.add_argument("--save-replay", nargs="?", const="", default=None, metavar="PLIK",
                   help="zapisuje powtórkę dla Godota (domyślnie results/replays/...)")
    p.add_argument("--config", default=None, help="plik konfiguracji gry (domyślnie configs/default.json)")
    p.set_defaults(func=cmd_play)

    p = sub.add_parser("train", help="trening bota Q-learning (zapis tablicy + kosztów)")
    p.add_argument("--episodes", type=int, default=3000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--physics", action="store_true", help="włącza fizykę (domyślnie wszystko lub z --no-obstacles)")
    p.add_argument("--kick", action="store_true", help="włącza kopanie bomb")
    p.add_argument("--knockback", action="store_true", help="włącza odrzut po wybuchu")
    p.add_argument("--obstacles", action="store_true", help="włącza ruchome przeszkody")
    p.add_argument("--no-obstacles", action="store_true", help="wyłącza ruchome przeszkody przy --physics")
    p.add_argument("--max-ticks", type=int, default=None, help="limit ticków w epizodzie treningowym")
    p.add_argument("--eval-games", type=int, default=80)
    p.add_argument("--workers", type=int, default=1,
                   help="liczba procesów treningu (scalanie tablic Q)")
    p.add_argument("--opponent", default="montecarlo",
                   choices=["montecarlo", "aggressive", "curriculum", "randomsafe", "random", "planner", "self"],
                   help="montecarlo = trening vs MonteCarlo + self-play (bez random/planner; domyślne)")
    p.add_argument("--resume", default=None,
                   help="kontynuuj od istniejącej tablicy JSON")
    p.add_argument("--out", default=None, help="ścieżka tablicy JSON (domyślnie ai/models/q_pure*.json)")
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("serve", help="serwer WebSocket dla Godota")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("experiment", help="jeden eksperyment z configs/experiments/")
    p.add_argument("config")
    p.add_argument("--workers", type=int, default=None, help="liczba procesów (domyślnie liczba rdzeni)")
    p.add_argument("--scale", type=float, default=1.0, help="ułamek liczby gier (np. 0.1 do próby)")
    p.add_argument("--out", default=None, help="katalog wyników (domyślnie results/)")
    p.set_defaults(func=cmd_experiment)

    p = sub.add_parser("analyze", help="wykresy, summary.json i tables.md z plików CSV")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("reproduce", help="wszystkie eksperymenty (E1, E2, E4-E6) i analiza jednym poleceniem")
    p.add_argument("--quick", action="store_true", help="10%% gier, wyniki w results/quick/")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_reproduce)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
