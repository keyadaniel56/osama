"""
Feature engineering for hidden pattern detection.
Goes beyond tick percentages — uses momentum, entropy, autocorrelation,
volatility clustering, micro-structure signals, and digit-specific features.
"""

import numpy as np
import pandas as pd
from collections import deque


# Named feature indices — keeps heuristic and model aligned
FEAT = {
    "short_mom":    0,
    "med_mom":      1,
    "long_mom":     2,
    "vol_short":    3,
    "vol_std":      4,
    "ac_lag1":      5,
    "ac_lag2":      6,
    "ac_lag3":      7,
    "ac_lag5":      8,
    "entropy":      9,
    "streak":       10,
    "price_pos":    11,
    "mean_rev":     12,
    "imbalance":    13,
    "skew":         14,
    "kurt":         15,
    "hurst":        16,
    # Digit-specific features
    "last_digit":   17,   # last digit of last price (0-9), normalised /9
    "digit_bias":   18,   # rolling bias: fraction of last 20 ticks where last digit > 4
    "digit_streak": 19,   # streak of last digit being high (>4) or low (<=4), normalised
    "digit_entropy":20,   # entropy of last-digit distribution over window
}

FEATURE_DIM = len(FEAT)


class FeatureEngine:
    def __init__(self, window: int = 50):
        self.window = window
        self.ticks = deque(maxlen=window * 2)

    def add_tick(self, price: float):
        self.ticks.append(price)

    def ready(self) -> bool:
        return len(self.ticks) >= self.window

    def extract(self) -> np.ndarray | None:
        if not self.ready():
            return None

        prices = np.array(list(self.ticks))[-self.window:]
        returns = np.diff(prices) / prices[:-1]

        features = [None] * FEATURE_DIM

        # --- Momentum signals ---
        features[FEAT["short_mom"]]  = float(np.mean(returns[-5:]))
        features[FEAT["med_mom"]]    = float(np.mean(returns[-10:]))
        features[FEAT["long_mom"]]   = float(np.mean(returns[-20:]))

        # --- Volatility clustering ---
        sq_returns = returns ** 2
        features[FEAT["vol_short"]]  = float(np.mean(sq_returns[-5:]))
        features[FEAT["vol_std"]]    = float(np.std(sq_returns[-10:]))

        # --- Autocorrelation ---
        for feat_key, lag in [("ac_lag1", 1), ("ac_lag2", 2), ("ac_lag3", 3), ("ac_lag5", 5)]:
            if len(returns) > lag:
                ac = np.corrcoef(returns[:-lag], returns[lag:])[0, 1]
                features[FEAT[feat_key]] = 0.0 if np.isnan(ac) else float(ac)
            else:
                features[FEAT[feat_key]] = 0.0

        # --- Shannon entropy of return signs ---
        signs = (returns > 0).astype(int)
        p = np.mean(signs) + 1e-9
        features[FEAT["entropy"]] = float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p + 1e-9)))

        # --- Streak detection ---
        streak = 1
        for i in range(len(signs) - 2, -1, -1):
            if signs[i] == signs[-1]:
                streak += 1
            else:
                break
        features[FEAT["streak"]] = streak / self.window

        # --- Price position within recent range ---
        high = np.max(prices[-20:])
        low  = np.min(prices[-20:])
        rng  = high - low if high != low else 1e-9
        features[FEAT["price_pos"]] = float((prices[-1] - low) / rng)

        # --- Mean reversion signal ---
        ma = np.mean(prices[-20:])
        features[FEAT["mean_rev"]] = float((prices[-1] - ma) / (np.std(prices[-20:]) + 1e-9))

        # --- Tick direction imbalance ---
        up_ticks   = np.sum(returns > 0)
        down_ticks = np.sum(returns < 0)
        total = up_ticks + down_ticks + 1e-9
        features[FEAT["imbalance"]] = float((up_ticks - down_ticks) / total)

        # --- Higher-order moments ---
        features[FEAT["skew"]] = float(pd.Series(returns).skew())
        features[FEAT["kurt"]] = float(pd.Series(returns).kurt())

        # --- Hurst exponent proxy ---
        features[FEAT["hurst"]] = self._hurst_proxy(prices)

        # --- Digit-specific features ---
        digits = np.array([self._last_digit(p) for p in prices])
        last_d = digits[-1]
        features[FEAT["last_digit"]]    = last_d / 9.0

        recent_digits = digits[-20:]
        features[FEAT["digit_bias"]]    = float(np.mean(recent_digits > 4))

        # Digit streak: how many consecutive ticks the last digit stayed high or low
        is_high = last_d > 4
        d_streak = 1
        for i in range(len(digits) - 2, -1, -1):
            if (digits[i] > 4) == is_high:
                d_streak += 1
            else:
                break
        features[FEAT["digit_streak"]]  = d_streak / self.window

        # Digit entropy over full window
        counts = np.bincount(digits.astype(int), minlength=10) + 1e-9
        probs  = counts / counts.sum()
        features[FEAT["digit_entropy"]] = float(-np.sum(probs * np.log2(probs)))

        return np.array(features, dtype=np.float32)

    @staticmethod
    def _last_digit(price: float) -> int:
        """Extract the last digit of a price (e.g. 1234.56 → 6)."""
        s = f"{price:.2f}".replace(".", "")
        return int(s[-1])

    def _hurst_proxy(self, prices: np.ndarray) -> float:
        """Simplified R/S analysis for Hurst exponent estimation."""
        try:
            lags = [2, 4, 8, 16]
            rs_values = []
            for lag in lags:
                chunks = [prices[i:i+lag] for i in range(0, len(prices) - lag, lag)]
                rs_list = []
                for chunk in chunks:
                    mean = np.mean(chunk)
                    deviation = np.cumsum(chunk - mean)
                    r = np.max(deviation) - np.min(deviation)
                    s = np.std(chunk) + 1e-9
                    rs_list.append(r / s)
                if rs_list:
                    rs_values.append(np.mean(rs_list))
            if len(rs_values) >= 2:
                hurst = np.polyfit(np.log(lags[:len(rs_values)]), np.log(rs_values), 1)[0]
                return float(np.clip(hurst, 0, 1))
        except Exception:
            pass
        return 0.5
