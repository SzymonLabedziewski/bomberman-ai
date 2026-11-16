"""Boty bazowe do porównań."""

from __future__ import annotations

from bomberman.ai.base import BaseBot
from bomberman.ai.danger import default_horizon, escape_path, in_danger, predict
from bomberman.ai.features import bomb_has_escape
from bomberman.ai.telemetry import set_debug
from bomberman.engine.rules import after_action, legal_actions
from bomberman.engine.state import Action, GameState


class RandomBot(BaseBot):
    """Losowa legalna akcja."""

    name = "random"

    def act(self, state: GameState, me: int) -> Action:
        legal = legal_actions(state, me, self.cfg)
        action = self.rng.choice(legal)
        set_debug(self, family="random", ops=1, detail="uniform", mode="random",
                  rationale=f"losowo -> {action.name}")
        return action


class RandomSafeBot(BaseBot):
    """Losowa akcja spośród tych, po których bot przeżyje następny tick."""

    name = "randomsafe"

    def act(self, state: GameState, me: int) -> Action:
        legal = legal_actions(state, me, self.cfg)
        horizon = default_horizon(self.cfg)
        own_bombs = [b for b in state.bombs if b.owner == me]

        if not own_bombs:
            safe = [a for a in legal if a != Action.BOMB and after_action(state, me, a, self.cfg).players[me].alive]
            if Action.BOMB in legal and bomb_has_escape(state, me, self.cfg) and self.rng.random() < 0.25:
                safe.append(Action.BOMB)
            pool = safe or legal
            action = self.rng.choice(pool)
            set_debug(self, family="random", ops=len(legal), detail=f"1step_sims={len(legal)}",
                      mode="randomsafe",
                      rationale=f"losowo wśród {len(pool)} bezpiecznych -> {action.name}")
            return action

        tier1_safe: list[Action] = []
        tier2_escapable: list[tuple[int, Action]] = []
        tier3_alive1: list[Action] = []

        for a in legal:
            if a == Action.BOMB:
                continue
            sim = after_action(state, me, a, self.cfg)
            if not sim.players[me].alive:
                continue
            tier3_alive1.append(a)

            own_sim = sim.clone()
            own_sim.bombs = [b for b in own_sim.bombs if b.owner == me]
            if own_sim.bombs or own_sim.flames:
                sim_tl = predict(own_sim, horizon, self.cfg, absent=me)
                esc = escape_path(own_sim, me, sim_tl, self.cfg)
                if esc is None:
                    continue
                if not in_danger(sim_tl, own_sim.player_cell(me)):
                    tier1_safe.append(a)
                else:
                    penalty = 1 if a == Action.STAY else 0
                    tier2_escapable.append((len(esc) + penalty, a))
            else:
                tier1_safe.append(a)

        if tier1_safe:
            pool = tier1_safe
        elif tier2_escapable:
            min_len = min(d for d, _ in tier2_escapable)
            pool = [a for d, a in tier2_escapable if d == min_len]
        elif tier3_alive1:
            pool = tier3_alive1
        else:
            pool = legal

        action = self.rng.choice(pool)
        set_debug(self, family="random", ops=len(legal), detail=f"own_bomb_safe={len(pool)}/{len(legal)}",
                  mode="randomsafe",
                  rationale=f"ochrona przed własną bombą ({len(pool)} opcji) -> {action.name}")
        return action
