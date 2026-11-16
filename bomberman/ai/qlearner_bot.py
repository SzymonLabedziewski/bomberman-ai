"""Bot AI: tabular Q-learning. W grze akcja pochodzi z tablicy Q, bez przeszukiwania."""

from __future__ import annotations

from pathlib import Path

from bomberman.ai.base import BaseBot
from bomberman.ai.danger import (
    default_horizon,
    escape_path,
    in_danger,
    opponent_reach,
    predict,
    with_kick_threats,
)
from bomberman.ai.features import bomb_has_escape, bomb_is_useful, encode_state
from bomberman.ai.q_table import DEFAULT_TABLE_PATH, QTable
from bomberman.ai.telemetry import set_debug
from bomberman.config import GameConfig
from bomberman.engine.rules import after_action, bomb_at, legal_actions
from bomberman.engine.state import BOX, DIRECTIONS, MOVES, Action, GameState, move_between


class QLearnerBot(BaseBot):
    """Polityka z tablicy Q (argmax, w treningu epsilon-greedy)."""

    name = "qlearner"

    def __init__(self, cfg: GameConfig, seed: int = 0, table: QTable | None = None,
                 table_path: str | Path | None = None, epsilon: float = 0.0,
                 alpha: float = 0.1, gamma: float = 0.95,
                 learn: bool = False, safe_play: bool = False,
                 bomb_explore: float = 0.0) -> None:
        super().__init__(cfg, seed)
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.learn = learn
        self.safe_play = safe_play
        self.bomb_explore = bomb_explore
        self._reset_memory()
        if table is not None:
            self.table = table
        else:
            path = Path(table_path) if table_path else DEFAULT_TABLE_PATH
            if not path.exists():
                raise FileNotFoundError(f"Brak tablicy Q: {path}. Uruchom: python -m bomberman train")
            self.table = QTable.load(path)

    def _reset_memory(self) -> None:
        self._last_key: str | None = None
        self._last_action: Action | None = None
        self._prev_cell: int | None = None
        self._curr_cell: int | None = None
        self._last_was_kick = False
        self._last_box_count = -1
        self._edge_counts: dict[tuple[int, Action], int] = {}
        self._bomb_counts: dict[int, int] = {}

    def act(self, state: GameState, me: int, precomputed_key: str | None = None) -> Action:
        if state.tick <= 1:
            self._reset_memory()

        p = state.players[me]
        if not p.alive or p.stunned:
            set_debug(self, family="rl", ops=0, detail="stunned", mode="stunned",
                      rationale="ogłuszony / martwy")
            self._last_key = None
            self._last_action = None
            self._last_was_kick = False
            return Action.STAY

        # Liczniki powtórzeń są ważne tylko do zmiany planszy (zniszczenia skrzyni).
        box_count = state.grid.count(BOX)
        if box_count != self._last_box_count:
            self._last_box_count = box_count
            self._edge_counts.clear()
            self._bomb_counts.clear()

        here = state.player_cell(me)
        # stoi w miejscu i nie kopnął -> zderzenie z przeciwnikiem
        collided = None
        if self._curr_cell == here and self._last_action in MOVES and not self._last_was_kick:
            collided = self._last_action
        if self._curr_cell is not None and self._curr_cell != here:
            self._prev_cell = self._curr_cell
        self._curr_cell = here

        legal = legal_actions(state, me, self.cfg)
        key = precomputed_key if precomputed_key is not None else encode_state(state, me, self.cfg)

        if self.safe_play and not self.learn and (state.bombs or state.flames):
            action = self._escape_if_needed(state, me, here, key, legal)
            if action is not None:
                return action

        candidates = legal
        if self.safe_play and not self.learn:
            candidates = self._safe_actions(state, me, legal) or legal

        if key != "dead" and key not in self.table.data:
            from bomberman.ai.train import _init_state_priors
            _init_state_priors(self.table, key, legal, alpha=1.0)
        values = self.table.values_for(key, candidates)

        if self.learn and self.epsilon > 0 and self.rng.random() < self.epsilon:
            action = self._explore_action(state, me, legal, key)
            mode = "explore"
            rationale = f"eksploracja -> {action.name}"
        else:
            action, best = self._exploit(state, me, here, key, candidates, values, collided)
            mode = "exploit"
            rationale = f"max Q -> {action.name} ({best:+.3f})"
            if Action.BOMB in legal and Action.BOMB not in candidates:
                if not bomb_has_escape(state, me, self.cfg):
                    rationale += "; BOMB zablokowany (brak ucieczki)"
                else:
                    rationale += "; BOMB zbędny (brak zagrożenia / skrzyń)"

        set_debug(self, family="rl", ops=1 + len(candidates),
                  detail=f"q_lookup states={self.table.n_states}",
                  mode=mode, values=self.table.values_for(key, legal), rationale=rationale)
        self._remember(state, here, key, action)
        return action

    def _exploit(self, state: GameState, me: int, here: int, key: str, candidates: list[Action],
                 values: dict[str, float], collided: Action | None) -> tuple[Action, float]:
        """Argmax Q z poprawkami przerywającymi pętle."""
        parts = key.split("|")
        if len(parts) > 14:
            fire, nav, mask, useful, knock = parts[0], int(parts[3]), parts[4], parts[11], parts[14]
        else:
            fire, nav, mask, useful, knock = "0", 0, "2222", "0", "0"
        calm = fire == "0" and knock != "1"

        def is_safe(a: Action) -> bool:
            if a in MOVES:
                return mask[MOVES.index(a)] == "2"
            if a == Action.BOMB:
                return useful == "1" and self._bomb_counts.get(here, 0) < 2
            return calm

        pool = list(candidates)

        # Po zderzeniu czołowym jeden z graczy (na zmianę) wybiera inny bezpieczny ruch.
        if collided is not None and collided in pool and len(pool) > 1:
            if (state.tick + me) % 2 == 0 or self._edge_counts.get((here, collided), 0) >= 2:
                alt = [a for a in pool if a != collided and is_safe(a)]
                if alt:
                    pool = alt

        # Bez trzeciej bomby z rzędu na tym samym polu, jeśli jest bezpieczny ruch.
        if fire == "0" and Action.BOMB in pool and self._bomb_counts.get(here, 0) >= 2:
            if any(a in MOVES and is_safe(a) for a in pool):
                pool = [a for a in pool if a != Action.BOMB]

        # Bez cofania się na poprzednie pole, gdy nic nie grozi (kopnięcia bomby to nie dotyczy).
        if self._prev_cell is not None and self._last_action != Action.BOMB and calm and len(pool) > 1:
            back = move_between(here, self._prev_cell, state.width)
            if back != Action.STAY and back in pool and bomb_at(state, self._prev_cell) is None:
                others = [a for a in pool if a != back and a != Action.STAY and is_safe(a)]
                if others:
                    pool = others

        safe_pool = [a for a in pool if a != Action.STAY and is_safe(a)]
        if calm and len(safe_pool) > 1 and not self.learn:
            # Wśród bezpiecznych ruchów kara za powtarzanie tej samej akcji z tego samego pola.
            def effective(a: Action) -> float:
                nav_bonus = 0.08 if (1 <= nav <= 4 and a == MOVES[nav - 1]) else 0.0
                return values[a.name] + nav_bonus - 0.22 * self._edge_counts.get((here, a), 0)

            best_unsafe = max((values[a.name] for a in pool if a not in safe_pool), default=-999.0)
            if max(values[a.name] for a in safe_pool) >= best_unsafe - 1e-9:
                best_eff = max(effective(a) for a in safe_pool)
                choices = [a for a in safe_pool if effective(a) >= best_eff - 1e-12]
                best = max(values[a.name] for a in choices)
            else:
                best = max(values[a.name] for a in pool)
                choices = [a for a in pool if values[a.name] >= best - 1e-12]
        else:
            best = max(values[a.name] for a in pool)
            choices = [a for a in pool if values[a.name] >= best - 1e-12]

        if len(choices) > 1 and Action.STAY in choices:
            choices = [a for a in choices if a != Action.STAY]
        action = choices[0] if len(choices) == 1 else self.rng.choice(choices)
        return action, best

    def _remember(self, state: GameState, here: int, key: str, action: Action) -> None:
        self._last_key = key
        self._last_action = action
        if action in MOVES:
            dx, dy = DIRECTIONS[action]
            self._last_was_kick = bomb_at(state, here + dy * state.width + dx) is not None
        else:
            self._last_was_kick = False
        self._edge_counts[(here, action)] = self._edge_counts.get((here, action), 0) + 1
        if action == Action.BOMB:
            self._bomb_counts[here] = self._bomb_counts.get(here, 0) + 1

    def _escape_if_needed(self, state: GameState, me: int, here: int, key: str,
                          legal: list[Action]) -> Action | None:
        """Wariant hybrydowy: gdy pole bota będzie w ogniu, pierwszy krok ścieżki ucieczki."""
        horizon = default_horizon(self.cfg)
        timeline = predict(state, horizon, self.cfg, absent=me)
        if not in_danger(timeline, here):
            return None
        reach = opponent_reach(state, me, horizon)
        cautious = with_kick_threats(state, me, timeline, self.cfg, reach)
        attempts = [(cautious, reach), (cautious, None)] if cautious is not timeline else []
        attempts += [(timeline, reach), (timeline, None)]
        path = None
        for tl, contested in attempts:
            path = escape_path(state, me, tl, self.cfg, contested=contested)
            if path is not None:
                break
        if path is None:
            path = escape_path(state, me, timeline, self.cfg, best_effort=True)
        action = Action.STAY
        if path and len(path) >= 2:
            action = move_between(path[0], path[1], state.width)
            if action not in legal:
                action = Action.STAY
        plan = [[c % state.width, c // state.width] for c in (path or [here])]
        set_debug(self, family="rl", ops=len(path or []), detail="escape_override",
                  mode="escape", plan=plan, values=self.table.values_for(key, legal),
                  rationale=f"ucieczka BFS -> {action.name} (zagrożenie ogniem)")
        self._last_key, self._last_action = key, action
        return action

    def _explore_action(self, state: GameState, me: int, legal: list[Action], key: str = "") -> Action:
        """Losowa akcja z podpowiedziami z cech zapisanych w kluczu (kopnięcie, ucieczka, bomba, cel)."""
        parts = key.split("|") if key else []
        if len(parts) >= 14:
            fire = parts[0]
            esc = int(parts[2])
            nav = int(parts[3])
            useful = parts[11]
            kick = parts[13]
            if kick == "3" and 1 <= nav <= 4 and self.rng.random() < max(0.65, self.bomb_explore):
                if MOVES[nav - 1] in legal:
                    return MOVES[nav - 1]
            if fire != "0" and 1 <= esc <= 4 and self.rng.random() < 0.65:
                if MOVES[esc - 1] in legal:
                    return MOVES[esc - 1]
            if (self.bomb_explore > 0 and Action.BOMB in legal
                    and useful == "1" and self.rng.random() < self.bomb_explore):
                return Action.BOMB
            if fire == "0" and 1 <= nav <= 4 and self.rng.random() < 0.50:
                if MOVES[nav - 1] in legal:
                    return MOVES[nav - 1]
        elif (self.bomb_explore > 0 and Action.BOMB in legal
              and self.rng.random() < self.bomb_explore
              and bomb_is_useful(state, me, self.cfg)):
            return Action.BOMB
        moves = [a for a in legal if a != Action.STAY] or legal
        return self.rng.choice(moves)

    def _safe_actions(self, state: GameState, me: int, legal: list[Action]) -> list[Action]:
        """Akcje, po których bot przeżyje tick i nadal ma ucieczkę; BOMB tylko użyteczna."""
        safe: list[Action] = []
        bombs_out = bool(state.bombs or state.flames)
        for a in legal:
            if a == Action.BOMB:
                if bomb_is_useful(state, me, self.cfg):
                    safe.append(a)
                continue
            sim = after_action(state, me, a, self.cfg)
            if not sim.players[me].alive:
                continue
            if bombs_out and (sim.bombs or sim.flames) and not self._still_escapable(sim, me):
                continue
            safe.append(a)
        return safe

    def _still_escapable(self, state: GameState, me: int) -> bool:
        horizon = default_horizon(self.cfg)
        timeline = predict(state, horizon, self.cfg, absent=me)
        if not in_danger(timeline, state.player_cell(me)):
            return True
        reach = opponent_reach(state, me, horizon)
        return escape_path(state, me, timeline, self.cfg, contested=reach) is not None

    def learn_from(self, prev_state: GameState, me: int, action: Action, reward: float,
                   next_state: GameState, done: bool,
                   prev_key: str | None = None, next_key: str | None = None) -> None:
        if not self.learn:
            return
        alive = next_state.players[me].alive
        key = prev_key if prev_key is not None else encode_state(prev_state, me, self.cfg)
        if next_key is None:
            next_key = encode_state(next_state, me, self.cfg) if alive else "dead"
        next_legal = legal_actions(next_state, me, self.cfg) if alive else []
        self.table.update(key, action.name, reward, next_key, next_legal, self.alpha, self.gamma, done)
