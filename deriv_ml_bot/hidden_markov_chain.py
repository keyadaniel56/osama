#!/usr/bin/env python3
"""
Hidden Markov Chain for Market Pattern Analysis
Detects hidden market states from win/loss sequences and price features.
Used to guide trade direction and skip trades during unfavorable regimes.
"""

import numpy as np
from collections import deque
from typing import Optional, Tuple
import json
import os

STATE_BULLISH  = 0  # Upward regime  → favor OVER
STATE_BEARISH  = 1  # Downward regime → favor UNDER
STATE_SIDEWAYS = 2  # Choppy/random  → skip or reduce stake

OBS_WIN  = 0
OBS_LOSS = 1

STATE_NAMES = ["BULLISH", "BEARISH", "SIDEWAYS"]


class HiddenMarkovChain:
    """
    3-state HMM over win/loss observations.

    Hidden states  : BULLISH (0), BEARISH (1), SIDEWAYS (2)
    Observations   : WIN (0), LOSS (1)

    The forward algorithm runs on the recent observation window to compute
    the posterior probability of each state given the observed sequence.
    Matrices are updated online via soft Baum-Welch after every trade.
    """

    STATE_FILE = os.path.join(os.path.dirname(__file__), "hmc_state.json")

    def __init__(self, history_length: int = 20, min_confidence: float = 0.60):
        self.history_length = history_length
        self.min_confidence = min_confidence

        # --- Transition matrix A[i,j] = P(state_j | state_i) ---
        self.A = np.array([
            [0.70, 0.20, 0.10],  # BULLISH  → ...
            [0.20, 0.70, 0.10],  # BEARISH  → ...
            [0.30, 0.30, 0.40],  # SIDEWAYS → ...
        ], dtype=float)

        # --- Emission matrix B[i,k] = P(obs_k | state_i) ---
        # BULLISH  → mostly wins on OVER trades
        # BEARISH  → mostly losses on OVER trades (wins on UNDER)
        # SIDEWAYS → ~50/50
        self.B = np.array([
            [0.75, 0.25],  # BULLISH  → [WIN, LOSS]
            [0.25, 0.75],  # BEARISH  → [WIN, LOSS]
            [0.50, 0.50],  # SIDEWAYS → [WIN, LOSS]
        ], dtype=float)

        # Initial state distribution
        self.pi = np.array([1/3, 1/3, 1/3], dtype=float)

        # Rolling observation buffer (WIN=0 / LOSS=1)
        self.obs_buffer: deque = deque(maxlen=history_length)

        # Current posterior state probabilities (updated after each trade)
        self.state_probs = self.pi.copy()

        # Smoothing counts for online matrix updates
        self._A_counts = np.ones_like(self.A)   # pseudo-counts
        self._B_counts = np.ones_like(self.B)

        # Pattern memory: maps recent obs tuple → win rate
        self._pattern_memory: dict = {}

        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, won: bool, trade_type: str = "OVER"):
        """
        Feed in the result of a completed trade.
        Updates the observation buffer and re-estimates state probabilities.

        Args:
            won       : True if the trade was a win
            trade_type: "OVER" or "UNDER" — affects emission interpretation
        """
        # Normalise observation: a UNDER win is equivalent to a BEARISH signal
        if trade_type == "UNDER":
            obs = OBS_WIN if won else OBS_LOSS
            effective_obs = obs  # treat win/loss the same regardless of direction
        else:
            obs = OBS_WIN if won else OBS_LOSS
            effective_obs = obs

        self.obs_buffer.append(effective_obs)
        self._update_state_probs()
        self._soft_update_matrices(effective_obs)
        self._update_pattern_memory()

    def predict(self) -> Tuple[Optional[int], float, str]:
        """
        Predict the best trade direction based on current market state.

        Returns:
            (prediction, confidence, state_name)
            prediction: 1=OVER, 0=UNDER, -1=skip
        """
        if len(self.obs_buffer) < 3:
            return -1, 0.0, "UNKNOWN"

        state = self._most_likely_state()
        state_conf = float(self.state_probs[state])
        state_name = STATE_NAMES[state]

        # Pattern-based boost
        pattern_boost = self._get_pattern_boost()

        if state == STATE_BULLISH:
            confidence = min(state_conf + pattern_boost, 1.0)
            if confidence >= self.min_confidence:
                return 1, confidence, state_name   # OVER
        elif state == STATE_BEARISH:
            confidence = min(state_conf + pattern_boost, 1.0)
            if confidence >= self.min_confidence:
                return 0, confidence, state_name   # UNDER
        else:  # SIDEWAYS
            # In sideways, only trade if pattern memory gives a strong signal
            if pattern_boost > 0.15:
                # Lean toward whichever direction pattern memory favors
                direction = self._pattern_direction()
                if direction != -1:
                    return direction, self.min_confidence + pattern_boost, state_name

        return -1, state_conf, state_name

    def should_skip_trade(self) -> Tuple[bool, str]:
        """
        Returns (should_skip, reason).
        Call this before placing any trade to check if HMC advises skipping.
        """
        if len(self.obs_buffer) < 3:
            return False, "insufficient data"

        state = self._most_likely_state()
        state_conf = float(self.state_probs[state])

        # Skip if we're confidently in SIDEWAYS
        if state == STATE_SIDEWAYS and state_conf > 0.55:
            return True, f"SIDEWAYS state ({state_conf:.2f})"

        # Skip if recent loss streak is severe
        recent = list(self.obs_buffer)[-5:]
        loss_rate = sum(1 for o in recent if o == OBS_LOSS) / len(recent)
        if loss_rate >= 0.8:
            return True, f"high loss rate ({loss_rate:.0%} in last {len(recent)})"

        return False, ""

    def get_state_summary(self) -> str:
        state = self._most_likely_state()
        conf  = self.state_probs[state]
        recent = list(self.obs_buffer)[-5:] if self.obs_buffer else []
        loss_rate = sum(1 for o in recent if o == OBS_LOSS) / max(len(recent), 1)
        return (f"HMC state={STATE_NAMES[state]}({conf:.2f}) "
                f"loss_rate={loss_rate:.0%} obs={len(self.obs_buffer)}")

    def save_state(self):
        """Persist learned matrices to disk."""
        data = {
            "transition_matrix": self.A.tolist(),
            "emission_matrix":   self.B.tolist(),
            "state_probabilities": self.state_probs.tolist(),
            "pattern_memory":    self._pattern_memory,
            "trade_history":     list(self.obs_buffer),
        }
        try:
            with open(self.STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[HMC] Warning: could not save state: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_state(self):
        """Load previously learned matrices if available."""
        try:
            if not os.path.exists(self.STATE_FILE):
                return
            with open(self.STATE_FILE) as f:
                data = json.load(f)
            if "transition_matrix" in data:
                self.A = np.array(data["transition_matrix"], dtype=float)
            if "emission_matrix" in data:
                self.B = np.array(data["emission_matrix"], dtype=float)
            if "state_probabilities" in data:
                self.state_probs = np.array(data["state_probabilities"], dtype=float)
            if "pattern_memory" in data:
                self._pattern_memory = data["pattern_memory"]
            if "trade_history" in data:
                for obs in data["trade_history"][-self.history_length:]:
                    self.obs_buffer.append(int(obs))
        except Exception as e:
            print(f"[HMC] Warning: could not load state: {e}")

    def _forward(self, observations: list) -> np.ndarray:
        """
        Forward algorithm — computes alpha[t] = P(o_1..o_t, state_t).
        Returns the final alpha vector (unnormalised posterior).
        """
        alpha = self.pi * self.B[:, observations[0]]
        alpha /= (alpha.sum() + 1e-12)

        for obs in observations[1:]:
            alpha = (alpha @ self.A) * self.B[:, obs]
            s = alpha.sum()
            if s > 0:
                alpha /= s

        return alpha

    def _update_state_probs(self):
        """Run forward algorithm on current buffer to update state posteriors."""
        if not self.obs_buffer:
            return
        obs = list(self.obs_buffer)
        self.state_probs = self._forward(obs)

    def _most_likely_state(self) -> int:
        return int(np.argmax(self.state_probs))

    def _soft_update_matrices(self, obs: int):
        """
        Online soft Baum-Welch: nudge emission and transition counts
        toward the current observation given the current state belief.
        """
        # Update emission counts
        for s in range(3):
            self._B_counts[s, obs] += self.state_probs[s]

        # Normalise emission rows
        for s in range(3):
            row_sum = self._B_counts[s].sum()
            self.B[s] = self._B_counts[s] / row_sum

        # Update transition counts using consecutive state beliefs
        # (simplified: use current state probs as soft source)
        if len(self.obs_buffer) >= 2:
            prev_obs = list(self.obs_buffer)[-2]
            prev_alpha = self._forward(list(self.obs_buffer)[:-1])
            for i in range(3):
                for j in range(3):
                    self._A_counts[i, j] += prev_alpha[i] * self.state_probs[j]

            for i in range(3):
                row_sum = self._A_counts[i].sum()
                self.A[i] = self._A_counts[i] / row_sum

    def _update_pattern_memory(self):
        """
        Track short observation patterns (last 3 obs) and their outcomes.
        Key = tuple of last 3 obs, value = [wins, total].
        """
        if len(self.obs_buffer) < 4:
            return
        obs_list = list(self.obs_buffer)
        pattern = tuple(obs_list[-4:-1])   # last 3 obs before current
        outcome = obs_list[-1]             # current obs (0=win, 1=loss)

        key = str(pattern)
        if key not in self._pattern_memory:
            self._pattern_memory[key] = [0, 0]
        self._pattern_memory[key][1] += 1
        if outcome == OBS_WIN:
            self._pattern_memory[key][0] += 1

    def _get_pattern_boost(self) -> float:
        """
        Look up the current 3-obs pattern in memory.
        Returns a confidence boost (0..0.2) if pattern has a strong win rate.
        """
        if len(self.obs_buffer) < 3:
            return 0.0
        obs_list = list(self.obs_buffer)
        pattern = tuple(obs_list[-3:])
        key = str(pattern)
        if key not in self._pattern_memory:
            return 0.0
        wins, total = self._pattern_memory[key]
        if total < 3:
            return 0.0
        win_rate = wins / total
        # Boost proportional to how far win_rate deviates from 0.5
        return float(max(0.0, (win_rate - 0.5) * 0.4))

    def _pattern_direction(self) -> int:
        """
        In SIDEWAYS state, check if pattern memory favors OVER(1) or UNDER(0).
        Returns -1 if no clear direction.
        """
        if len(self.obs_buffer) < 3:
            return -1
        obs_list = list(self.obs_buffer)
        pattern = tuple(obs_list[-3:])
        key = str(pattern)
        if key not in self._pattern_memory:
            return -1
        wins, total = self._pattern_memory[key]
        if total < 3:
            return -1
        win_rate = wins / total
        if win_rate > 0.65:
            return 1   # pattern historically leads to wins → OVER
        if win_rate < 0.35:
            return 0   # pattern historically leads to losses → UNDER
        return -1
