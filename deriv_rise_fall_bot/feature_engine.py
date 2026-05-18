"""
Feature engineering for Rise/Fall prediction.
Extracts momentum, volatility, entropy, autocorrelation, and other technical indicators.
"""

import numpy as np
import pandas as pd
from collections import deque


FEAT = {
    "short_mom":    0,   # Short-term momentum
    "med_mom":      1,   # Medium-term momentum
    "long_mom":     2,   # Long-term momentum
    "vol_short":    3,   # Short-term volatility
    "vol_std":      4,   # Volatility standard deviation
    "ac_lag1":      5,   # Autocorrelation lag 1
    "ac_lag2":      6,   # Autocorrelation lag 2
    "ac_lag3":      7,   # Autocorrelation lag 3
    "ac_lag5":      8,   # Autocorrelation lag 5
    "entropy":      9,   # Shannon entropy of returns
    "streak":       10,  # Current streak length
    "price_pos":    11,  # Price position in range
    "mean_rev":     12,  # Mean reversion signal
    "imbalance":    13,  # Up/down tick imbalance
    "skew":         14,  # Return skewness
    "kurt":         15,  # Return kurtosis
    "hurst":        16,  # Hurst exponent
    "rsi":          17,  # RSI indicator
    "bb_pos":       18,  # Bollinger Band position
    "trend":        19,  # Trend strength
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

        # Momentum signals
        features[FEAT["short_mom"]]  = float(np.mean(returns[-5:]))
        features[FEAT["med_mom"]]    = float(np.mean(returns[-10:]))
        features[FEAT["long_mom"]]   = float(np.mean(returns[-20:]))

        # Volatility
        sq_returns = returns ** 2
        features[FEAT["vol_short"]]  = float(np.mean(sq_returns[-5:]))
        features[FEAT["vol_std"]]    = float(np.std(sq_returns[-10:]))

        # Autocorrelation
        for feat_key, lag in [("ac_lag1", 1), ("ac_lag2", 2), ("ac_lag3", 3), ("ac_lag5", 5)]:
            if len(returns) > lag:
                ac = np.corrcoef(returns[:-lag], returns[lag:])[0, 1]
                features[FEAT[feat_key]] = 0.0 if np.isnan(ac) else float(ac)
            else:
                features[FEAT[feat_key]] = 0.0

        # Entropy
        signs = (returns > 0).astype(int)
        p = np.mean(signs) + 1e-9
        features[FEAT["entropy"]] = float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p + 1e-9)))

        # Streak
        streak = 1
        for i in range(len(signs) - 2, -1, -1):
            if signs[i] == signs[-1]:
                streak += 1
            else:
                break
        features[FEAT["streak"]] = streak / self.window

        # Price position
        high = np.max(prices[-20:])
        low  = np.min(prices[-20:])
        rng  = high - low if high != low else 1e-9
        features[FEAT["price_pos"]] = float((prices[-1] - low) / rng)

        # Mean reversion
        ma = np.mean(prices[-20:])
        features[FEAT["mean_rev"]] = float((prices[-1] - ma) / (np.std(prices[-20:]) + 1e-9))

        # Imbalance
        up_ticks   = np.sum(returns > 0)
        down_ticks = np.sum(returns < 0)
        total = up_ticks + down_ticks + 1e-9
        features[FEAT["imbalance"]] = float((up_ticks - down_ticks) / total)

        # Higher moments
        features[FEAT["skew"]] = float(pd.Series(returns).skew())
        features[FEAT["kurt"]] = float(pd.Series(returns).kurt())

        # Hurst exponent
        features[FEAT["hurst"]] = self._hurst_proxy(prices)

        # RSI
        features[FEAT["rsi"]] = self._calculate_rsi(prices, period=14)

        # Bollinger Band position
        features[FEAT["bb_pos"]] = self._bollinger_position(prices, period=20)

        # Trend strength
        features[FEAT["trend"]] = self._trend_strength(prices)

        return np.array(features, dtype=np.float32)

    def _hurst_proxy(self, prices: np.ndarray) -> float:
        """Simplified R/S analysis for Hurst exponent."""
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

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 0.5
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 1.0
        
        rs = avg_gain / avg_loss
        rsi = 1 - (1 / (1 + rs))
        return float(rsi)

    def _bollinger_position(self, prices: np.ndarray, period: int = 20) -> float:
        """Calculate position within Bollinger Bands."""
        if len(prices) < period:
            return 0.5
        
        ma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        if std == 0:
            return 0.5
        
        upper = ma + 2 * std
        lower = ma - 2 * std
        
        position = (prices[-1] - lower) / (upper - lower)
        return float(np.clip(position, 0, 1))

    def _trend_strength(self, prices: np.ndarray) -> float:
        """Calculate trend strength using linear regression."""
        if len(prices) < 10:
            return 0.0
        
        x = np.arange(len(prices[-20:]))
        y = prices[-20:]
        
        try:
            slope, _ = np.polyfit(x, y, 1)
            normalized_slope = slope / (np.mean(y) + 1e-9)
            return float(np.clip(normalized_slope * 100, -1, 1))
        except:
            return 0.0
