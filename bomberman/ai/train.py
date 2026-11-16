"""Trening tabularnego Q-learningu."""

from __future__ import annotations

import json
import multiprocessing as mp
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from bomberman.ai.baselines import RandomBot, RandomSafeBot
from bomberman.ai.features import encode_state, kick_is_useful
from bomberman.ai.q_table import DEFAULT_PHYSICS_TABLE_PATH, DEFAULT_TABLE_PATH, QTable
from bomberman.ai.qlearner_bot import QLearnerBot
from bomberman.ai.telemetry import rss_kb
from bomberman.config import PROJECT_ROOT, GameConfig, load_config
from bomberman.engine.board import new_game
from bomberman.engine.rules import legal_actions, step
from bomberman.engine.state import BOX, MOVES, Action, GameState

SURVIVE_SHAPING = 0.0005
DEATH_PENALTY = -1.4
SELF_KILL_EXTRA = -2.0
UNSAFE_BOMB_PENALTY = -1.0
SAFE_BOMB_BONUS = 0.15
THREAT_BOMB_BONUS = 0.45       # bomba, która niszczy skrzynie albo grozi przeciwnikowi
KICK_ATTACK_BONUS = 0.68       # większe niż ESCAPE_MOVE_BONUS, żeby bot wolał kopnąć niż uciekać
KNOCK_ENEMY_BONUS = 0.35
SELF_KNOCK_PENALTY = -0.25
USELESS_BOMB_PENALTY = -0.5
BOX_BONUS = 0.12
KILL_BONUS = 1.5               # tylko gdy przeciwnik nie zginął od własnej bomby
APPROACH_BONUS = 0.05          # krok najkrótszą bezpieczną drogą do celu
BACKTRACK_PENALTY = -0.06      # powrót na poprzednie pole bez zagrożenia
IDLE_PENALTY = -0.04
DANGER_STAY_PENALTY = -0.85
ESCAPE_MOVE_BONUS = 0.55       # wyjście ze strefy zagrożenia na bezpieczne pole
ESCAPE_STEP_BONUS = 0.25       # krok ucieczki, po którym bot nadal jest w strefie
WRONG_ESCAPE_PENALTY = -0.45
ENTER_DANGER_PENALTY = -0.75   # musi być większe niż ESCAPE_MOVE_BONUS
PASSIVE_PENALTY = -0.6         # koniec gry bez żadnego ataku
WIN_REWARD = 1.5
LOSS_REWARD = -1.0
DRAW_REWARD = -0.4             # mniej dotkliwe niż śmierć, ale zniechęca do biernego czekania

# założony średni pobór mocy CPU [W]
ASSUMED_CPU_WATTS = 15.0
COST_LEDGER_PATH = PROJECT_ROOT / "results" / "ai_cost_ledger.json"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _make_opponent(name: str, cfg: GameConfig, seed: int):
    if name == "montecarlo":
        from bomberman.ai.montecarlo_bot import MonteCarloBot
        return MonteCarloBot(cfg, seed, rollouts=5, depth=6)
    if name == "randomsafe":
        return RandomSafeBot(cfg, seed)
    if name == "random":
        return RandomBot(cfg, seed)
    if name == "planner":
        from bomberman.ai.planner_bot import PlannerBot
        return PlannerBot(cfg, seed)
    if name == "self":
        return None
    raise ValueError(f"nieznany opponent treningu: {name}")


def _physics_flags(cfg: GameConfig) -> dict[str, bool]:
    ph = cfg.physics
    return {"kick": ph.kick, "knockback": ph.knockback, "moving_obstacles": ph.moving_obstacles}


def _manhattan(state: GameState, me: int) -> int:
    if not state.players[1 - me].alive:
        return 99
    ax, ay = state.players[me].cell
    bx, by = state.players[1 - me].cell
    return abs(ax - bx) + abs(ay - by)


def _init_state_priors(table: QTable, key: str, legal: list[Action], alpha: float) -> None:
    """Wartości startowe Q dla nowego stanu, wyliczone z cech zapisanych w kluczu."""
    parts = key.split("|")
    if len(parts) < 15:
        return
    fire_code = parts[0]
    esc_code = int(parts[2])
    nav_code = int(parts[3])
    dir_mask = parts[4]
    safe_bomb = parts[9] == "1"
    useful_bomb = parts[11] == "1"
    kick_code = parts[13]
    knock_code = parts[14]

    for a in legal:
        if a == Action.BOMB:
            if fire_code != "0" or knock_code == "1" or not safe_bomb:
                r = UNSAFE_BOMB_PENALTY
            elif useful_bomb:
                r = SAFE_BOMB_BONUS + THREAT_BOMB_BONUS
            else:
                r = USELESS_BOMB_PENALTY
        elif a == Action.STAY:
            r = IDLE_PENALTY + (DANGER_STAY_PENALTY if (fire_code != "0" or knock_code == "1") else 0.0)
        elif a in MOVES:
            idx = MOVES.index(a)
            safety = dir_mask[idx] if idx < len(dir_mask) else "2"
            code = idx + 1
            if safety == "0":
                r = DEATH_PENALTY
            elif kick_code == "3" and nav_code == code:
                r = KICK_ATTACK_BONUS
            elif fire_code != "0" or knock_code == "1":
                if esc_code == code and safety == "2":
                    r = ESCAPE_MOVE_BONUS + 0.08
                elif safety == "2":
                    r = ESCAPE_MOVE_BONUS
                elif esc_code == code:
                    r = ESCAPE_STEP_BONUS
                else:
                    r = WRONG_ESCAPE_PENALTY
            else:
                if safety == "1":
                    r = ENTER_DANGER_PENALTY
                elif nav_code == code:
                    r = APPROACH_BONUS + (0.04 if knock_code == "2" else 0.0)
                else:
                    r = -0.01
        else:
            r = 0.0
        table.update(key, a.name, r, key, [], alpha, 0.0, True)


def _step_reward(prev: GameState, nxt: GameState, me: int, action: Action,
                 done: bool, events: list, cfg: GameConfig,
                 prev_cell: int | None = None, active_attacks: int = 1,
                 prev_key: str | None = None, next_key: str | None = None) -> float:
    reward = SURVIVE_SHAPING
    opp = 1 - me

    p_key = prev_key if prev_key is not None else encode_state(prev, me, cfg)
    n_key = next_key if next_key is not None else (
        "dead" if not nxt.players[me].alive else encode_state(nxt, me, cfg)
    )
    p = p_key.split("|")
    if len(p) < 15:
        p = ["0"] * 15
    n: list[str] | None = n_key.split("|")
    if len(n) < 15:
        n = None

    prev_danger = p[0] != "0" or p[14] == "1"
    nxt_danger = n is not None and (n[0] != "0" or n[14] == "1")
    nxt_can_escape = n is not None and n[1] == "1"
    esc_code = int(p[2])
    nav_code = int(p[3])
    safe_bomb = p[9] == "1"
    useful_bomb = p[11] == "1"
    p_kick_code = p[13]
    p_knock_code = p[14]
    n_knock_code = n[14] if n is not None else "0"

    if action == Action.BOMB:
        if prev_danger or not safe_bomb:
            reward += UNSAFE_BOMB_PENALTY
        elif useful_bomb:
            reward += SAFE_BOMB_BONUS + THREAT_BOMB_BONUS
            if n_knock_code == "2":
                reward += KNOCK_ENEMY_BONUS * 0.5
        else:
            reward += USELESS_BOMB_PENALTY
    elif action == Action.STAY:
        reward += IDLE_PENALTY
        if prev_danger:
            reward += DANGER_STAY_PENALTY
    else:
        act_code = MOVES.index(action) + 1
        kicked_usefully = (
            cfg.physics.kick
            and prev.bombs
            and ((p_kick_code == "3" and act_code == nav_code) or kick_is_useful(prev, me, action, cfg))
        )
        if kicked_usefully:
            reward += KICK_ATTACK_BONUS
            if n_knock_code == "2":
                reward += KNOCK_ENEMY_BONUS * 0.5

        if nxt.players[me].alive:
            if kicked_usefully and nxt_can_escape:
                if not nxt_danger:
                    reward += ESCAPE_MOVE_BONUS * 0.5
            elif prev_danger and not nxt_danger:
                reward += ESCAPE_MOVE_BONUS + (0.08 if esc_code == act_code else 0.0)
            elif not prev_danger and nxt_danger:
                reward += ENTER_DANGER_PENALTY
                if not nxt_can_escape:
                    reward += UNSAFE_BOMB_PENALTY
            elif prev_danger and nxt_danger:
                reward += ESCAPE_STEP_BONUS if esc_code == act_code else WRONG_ESCAPE_PENALTY
            else:
                if prev_cell is not None and nxt.player_cell(me) == prev_cell:
                    reward += BACKTRACK_PENALTY
                if nav_code != 0 and act_code == nav_code:
                    reward += APPROACH_BONUS + (0.03 if p_knock_code == "2" else 0.0)
                elif prev.players[opp].alive:
                    d_before = _manhattan(prev, me)
                    d_after = _manhattan(nxt, me)
                    if d_after < d_before:
                        reward += APPROACH_BONUS * 0.5
                    elif d_after > d_before:
                        reward -= APPROACH_BONUS * 0.6

    for e in events:
        if e.get("type") == "knock":
            if e.get("player") == opp:
                reward += KNOCK_ENEMY_BONUS
            elif e.get("player") == me:
                reward += SELF_KNOCK_PENALTY

    boxes_before = prev.grid.count(BOX)
    boxes_after = nxt.grid.count(BOX)
    if boxes_after < boxes_before:
        reward += BOX_BONUS * (boxes_before - boxes_after)

    if prev.players[me].alive and not nxt.players[me].alive:
        reward += DEATH_PENALTY

    opp_self_kill = False
    for e in events:
        if e.get("type") != "death":
            continue
        if e.get("player") == me and e.get("by_self"):
            reward += SELF_KILL_EXTRA
        if e.get("player") == opp:
            if e.get("by_self"):
                opp_self_kill = True
            else:
                reward += KILL_BONUS

    if done:
        if nxt.winner == me:
            # Wygrana po samobójstwie przeciwnika liczy się mniej, a przy biernej grze wcale.
            if not opp_self_kill:
                reward += WIN_REWARD
            elif active_attacks > 0:
                reward += WIN_REWARD * 0.25
        else:
            reward += DRAW_REWARD if nxt.winner in (-1, None) else LOSS_REWARD
            if active_attacks <= 0:
                reward += PASSIVE_PENALTY
    return reward


def _curriculum_opponent(ep: int, episodes: int, mode: str) -> str:
    """Przeciwnik w epizodzie `ep` zależnie od trybu treningu."""
    if mode == "montecarlo":
        return "self" if ep % 5 in (3, 4) else "montecarlo"
    if mode in ("randomsafe", "random", "planner", "self"):
        return mode
    frac = ep / max(1, episodes)
    if frac < 0.15:
        return "self" if (ep % 3 == 2) else "randomsafe"
    roll = ep % 8
    if roll <= 3:
        return "montecarlo"
    if roll in (4, 5, 6):
        return "self"
    return "randomsafe"


def _train_shard(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config().with_physics(payload["physics"])
    if payload.get("max_ticks") is not None:
        cfg = replace(cfg, max_ticks=int(payload["max_ticks"]))
    episodes = int(payload["episodes"])
    seed = int(payload["seed"])
    table = QTable.load(payload["init_table"]) if payload.get("init_table") else QTable()
    learner = QLearnerBot(
        cfg, seed=seed, table=table, epsilon=payload["epsilon_start"],
        alpha=payload["alpha"], gamma=payload["gamma"], learn=True,
        safe_play=False, bomb_explore=0.35,
    )
    peak_rss = rss_kb()
    wins = draws = losses = self_kills = bombs = kicks = 0
    curriculum = payload.get("curriculum", "aggressive")

    for ep in range(episodes):
        frac = ep / max(1, episodes - 1)
        learner.epsilon = payload["epsilon_start"] + (
            payload["epsilon_end"] - payload["epsilon_start"]) * frac
        opp_name = _curriculum_opponent(ep, episodes, curriculum)
        state = new_game(cfg, seed + ep + 1)
        me = ep % 2
        opp_id = 1 - me
        if opp_name == "self":
            opp = QLearnerBot(
                cfg, seed=seed + ep + 99, table=table,
                epsilon=max(0.15, learner.epsilon * 0.5),
                learn=False, safe_play=False, bomb_explore=0.0,
            )
        else:
            opp = _make_opponent(opp_name, cfg, seed + ep + 7)

        prev_cell: int | None = None
        curr_cell: int | None = state.player_cell(me)
        active_attacks = 0
        curr_key = encode_state(state, me, cfg)

        while not state.done:
            prev = state.clone()
            here = prev.player_cell(me)
            if curr_cell is not None and curr_cell != here:
                prev_cell = curr_cell
            curr_cell = here

            if curr_key != "dead" and curr_key not in table.visits:
                _init_state_priors(table, curr_key, legal_actions(prev, me, cfg), learner.alpha)

            a_me = learner.act(state, me, precomputed_key=curr_key)
            a_opp = opp.act(state, opp_id)
            if a_me == Action.BOMB:
                bombs += 1
                active_attacks += 1
            elif cfg.physics.kick and prev.bombs and kick_is_useful(prev, me, a_me, cfg):
                active_attacks += 1

            acts = [Action.STAY, Action.STAY]
            acts[me] = a_me
            acts[opp_id] = a_opp
            events = step(state, acts, cfg)
            done = state.done
            next_key = "dead" if not state.players[me].alive else encode_state(state, me, cfg)
            reward = _step_reward(
                prev, state, me, a_me, done, events, cfg,
                prev_cell=prev_cell, active_attacks=active_attacks,
                prev_key=curr_key, next_key=next_key,
            )
            learner.learn_from(prev, me, a_me, reward, state, done, prev_key=curr_key, next_key=next_key)
            curr_key = next_key
            peak_rss = max(peak_rss, rss_kb())
            for e in events:
                if e.get("type") == "kick" and e.get("player") == me:
                    kicks += 1
                    active_attacks += 1
                if e.get("type") == "death" and e.get("player") == me and e.get("by_self"):
                    self_kills += 1

        if state.winner == me:
            wins += 1
        elif state.winner == -1:
            draws += 1
        else:
            losses += 1

    return {
        "q": table.data,
        "visits": table.visits,
        "wins": wins, "draws": draws, "losses": losses,
        "self_kills": self_kills, "bombs": bombs, "kicks": kicks,
        "peak_rss_kb": peak_rss,
        "n_states": table.n_states,
    }


def train_q(cfg: GameConfig | None = None, episodes: int = 3000, seed: int = 42,
            physics: bool | dict[str, bool] = False, epsilon_start: float = 1.0, epsilon_end: float = 0.08,
            alpha: float = 0.2, gamma: float = 0.97, eval_games: int = 40,
            out_path: Path | str | None = None, opponent: str = "montecarlo",
            workers: int = 1, resume: Path | str | None = None,
            max_ticks: int | None = None) -> dict[str, Any]:
    """Trening tablicy Q, ewaluacja i zapis z metadanymi kosztu."""
    cfg = (cfg or load_config()).with_physics(physics)
    if max_ticks is not None:
        cfg = replace(cfg, max_ticks=int(max_ticks))
    workers = max(1, int(workers))
    default_out = DEFAULT_PHYSICS_TABLE_PATH if cfg.physics.enabled else DEFAULT_TABLE_PATH
    out = Path(out_path) if out_path else default_out
    init_table = str(Path(resume)) if resume else None
    physics_payload = _physics_flags(cfg) if cfg.physics.enabled else False

    per = episodes // workers
    rem = episodes % workers
    jobs = []
    for w in range(workers):
        n = per + (1 if w < rem else 0)
        if n <= 0:
            continue
        jobs.append({
            "episodes": n,
            "seed": seed + w * 1_000_003,
            "physics": physics_payload,
            "max_ticks": cfg.max_ticks,
            "epsilon_start": epsilon_start,
            "epsilon_end": epsilon_end,
            "alpha": alpha,
            "gamma": gamma,
            "curriculum": opponent,
            "init_table": init_table,
        })

    t0 = time.perf_counter()
    if workers == 1:
        results = [_train_shard(jobs[0])]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(workers) as pool:
            results = pool.map(_train_shard, jobs)

    table = QTable()
    wins = draws = losses = self_kills = bombs = kicks = 0
    peak_rss = 0.0
    for r in results:
        part = QTable(r["q"], r["visits"])
        table.merge_from(part)
        wins += r["wins"]
        draws += r["draws"]
        losses += r["losses"]
        self_kills += r["self_kills"]
        bombs += r.get("bombs", 0)
        kicks += r.get("kicks", 0)
        peak_rss = max(peak_rss, r["peak_rss_kb"])

    wall = time.perf_counter() - t0
    learner = QLearnerBot(cfg, seed=seed, table=table, epsilon=0.0, learn=False, safe_play=False)
    eval_stats = _evaluate_suite(cfg, learner, seed=seed + 100_000, games=eval_games)

    cpu_seconds_est = round(wall * workers, 2)
    energy_wh_est = round(cpu_seconds_est / 3600.0 * ASSUMED_CPU_WATTS, 4)

    out.parent.mkdir(parents=True, exist_ok=True)
    table.save(out)
    meta_file = out.with_name(out.stem + ".train.meta.json")
    meta = {
        "episodes": episodes,
        "workers": workers,
        "wall_seconds": round(wall, 2),
        "peak_rss_mb": round(peak_rss / 1024.0, 2),
        "cpu_seconds_est": cpu_seconds_est,
        "energy_wh_est": energy_wh_est,
        "assumed_cpu_watts": ASSUMED_CPU_WATTS,
        "pure_policy": True,
        "safe_play_eval": False,
        "opponent": opponent,
        "physics": cfg.physics.enabled,
        "physics_flags": _physics_flags(cfg),
        "max_ticks": cfg.max_ticks,
        "alpha": alpha,
        "gamma": gamma,
        "epsilon_start": epsilon_start,
        "epsilon_end": epsilon_end,
        "n_states": table.n_states,
        "train_wins": wins,
        "train_draws": draws,
        "train_losses": losses,
        "train_self_kills": self_kills,
        "train_bombs": bombs,
        "train_kicks": kicks,
        "final_eval_winrate": eval_stats["vs_randomsafe"]["win_rate"],
        "final_eval_self_kill_rate": eval_stats["vs_randomsafe"]["self_kill_rate"],
        "final_eval_bomb_rate": eval_stats["vs_randomsafe"]["bomb_rate"],
        "final_eval": eval_stats,
        "final_eval_games": eval_games,
        "table_path": _rel(out),
        "meta_path": _rel(meta_file),
        "seed": seed,
        "resume": _rel(Path(resume)) if resume else None,
        "note": "Czysta polityka Q (safe_play=False). Sam WR vs RandomSafe wprowadza w błąd, patrz vs_planner i bomb_rate.",
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    _append_cost_ledger(meta)
    return meta


def _append_cost_ledger(meta: dict[str, Any]) -> None:
    """Dopisuje koszt treningu do results/ai_cost_ledger.json i przelicza sumy."""
    COST_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {k: meta.get(k) for k in (
        "table_path", "episodes", "workers", "wall_seconds", "cpu_seconds_est", "energy_wh_est",
        "assumed_cpu_watts", "peak_rss_mb", "n_states", "physics", "opponent", "pure_policy",
        "safe_play_eval", "resume", "final_eval", "seed",
    )}
    ledger: dict[str, Any]
    if COST_LEDGER_PATH.exists():
        with open(COST_LEDGER_PATH, encoding="utf-8") as f:
            ledger = json.load(f)
    else:
        ledger = {
            "assumed_cpu_watts": ASSUMED_CPU_WATTS,
            "note": "cpu_seconds_est = wall_seconds * workers; energy_wh_est = cpu_s/3600 * P_W",
            "runs": [],
        }
    runs = list(ledger.get("runs") or [])
    runs.append(entry)
    ledger["runs"] = runs
    ledger["assumed_cpu_watts"] = ASSUMED_CPU_WATTS
    ledger["total_episodes"] = sum(int(r.get("episodes") or 0) for r in runs)
    ledger["total_wall_seconds"] = round(sum(float(r.get("wall_seconds") or 0) for r in runs), 2)
    ledger["total_cpu_seconds_est"] = round(sum(float(r.get("cpu_seconds_est") or 0) for r in runs), 2)
    ledger["total_energy_wh_est"] = round(sum(float(r.get("energy_wh_est") or 0) for r in runs), 4)
    with open(COST_LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)


def _evaluate_suite(cfg: GameConfig, learner: QLearnerBot, seed: int, games: int) -> dict[str, Any]:
    """Wyniki przeciw RandomSafe, Plannerowi i MonteCarlo, z naprzemienną zamianą narożników."""
    from bomberman.ai.montecarlo_bot import MonteCarloBot
    from bomberman.ai.planner_bot import PlannerBot

    out: dict[str, Any] = {}
    for label, factory in (
        ("vs_randomsafe", lambda i: RandomSafeBot(cfg, seed + i * 2 + 1)),
        ("vs_planner", lambda i: PlannerBot(cfg, seed + i * 2 + 1)),
        ("vs_montecarlo", lambda i: MonteCarloBot(cfg, seed + i * 2 + 1, rollouts=12, depth=7)),
    ):
        wins = draws = losses = self_kills = games_with_bomb = total_kicks = 0
        for i in range(games):
            opp = factory(i)
            state = new_game(cfg, seed + i)
            me = i % 2
            opp_id = 1 - me
            placed = 0
            while not state.done:
                a_me = learner.act(state, me)
                a_opp = opp.act(state, opp_id)
                if a_me == Action.BOMB:
                    placed += 1
                acts = [Action.STAY, Action.STAY]
                acts[me] = a_me
                acts[opp_id] = a_opp
                for e in step(state, acts, cfg):
                    if e.get("type") == "kick" and e.get("player") == me:
                        total_kicks += 1
                    if e.get("type") == "death" and e.get("player") == me and e.get("by_self"):
                        self_kills += 1
            if placed:
                games_with_bomb += 1
            if state.winner == me:
                wins += 1
            elif state.winner == -1:
                draws += 1
            else:
                losses += 1
        n = max(1, games)
        out[label] = {
            "win_rate": round(wins / n, 4),
            "draw_rate": round(draws / n, 4),
            "loss_rate": round(losses / n, 4),
            "self_kill_rate": round(self_kills / n, 4),
            "bomb_rate": round(games_with_bomb / n, 4),
            "kicks_per_game": round(total_kicks / n, 4),
        }
    return out
