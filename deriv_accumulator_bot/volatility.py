"""
Volatility and regime analysis for accumulator entry timing.
Accumulators need calm, low-volatility markets to survive tick-by-tick.
"""

import numpy as np
from collections import deque
from advanced_analyzer import AdvancedMarketAnalyzer


class VolatilityAnalyzer:
    def __init__(self, window: int = 30):
        self.window = window
        self.ticks = deque(maxlen=window * 2)
        self.advanced_analyzer = AdvancedMarketAnalyzer(window=50)

    def add_tick(self, price: float):
        self.ticks.append(price)
        self.advanced_analyzer.add_tick(price)

    def ready(self) -> bool:
        return len(self.ticks) >= self.window

    def analyze(self) -> dict:
        """
        Returns a dict of regime metrics used to decide entry.
        """
        if not self.ready():
            return {}

        prices = np.array(list(self.ticks))[-self.window:]
        returns = np.diff(prices) / (prices[:-1] + 1e-9)

        vol_short = float(np.std(returns[-5:]))
        vol_medium = float(np.std(returns[-15:]))
        vol_long = float(np.std(returns))

        # Hurst exponent proxy — >0.5 = trending (safer), <0.5 = choppy (risky)
        hurst = self._hurst_proxy(prices)

        # Shannon entropy of return signs — lower = more predictable
        signs = (returns > 0).astype(int)
        p = np.mean(signs) + 1e-9
        entropy = float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p + 1e-9)))

        # Autocorrelation lag-1 — negative = mean-reverting (risky for accumulators)
        ac_lag1 = 0.0
        if len(returns) > 1:
            ac = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            ac_lag1 = 0.0 if np.isnan(ac) else float(ac)

        # Volatility trend: is vol increasing or decreasing?
        vol_trend = vol_short - vol_medium  # negative = vol is calming down (good)

        # Momentum: check if price is in a clear directional move
        momentum = float(np.mean(returns[-10:]))  # positive = uptrend, negative = downtrend
        
        # Consistency: what % of recent ticks moved in the same direction?
        recent_signs = signs[-10:]
        consistency = max(np.mean(recent_signs), 1 - np.mean(recent_signs))  # 0.5-1.0

        return {
            "vol_short": vol_short,
            "vol_medium": vol_medium,
            "vol_long": vol_long,
            "hurst": hurst,
            "entropy": entropy,
            "ac_lag1": ac_lag1,
            "vol_trend": vol_trend,
            "momentum": momentum,
            "consistency": consistency,
        }

    def is_safe_to_enter(self, metrics: dict, growth_rate: float) -> tuple[bool, str]:
        """
        EXTREME DEFENSIVE entry logic with advanced knockout prediction.
        Uses multi-layered analysis to predict knockout probability.
        """
        if not metrics:
            return False, "insufficient data"
        
        # LAYER 1: Advanced knockout probability prediction
        knockout_prob, analysis = self.advanced_analyzer.predict_knockout_probability(growth_rate)
        
        # ABSOLUTE REJECTION if knockout probability > 15%
        if knockout_prob > 0.15:
            # Check if we have detailed risk breakdown
            if 'volatility_risk' in analysis:
                # Find highest risk factor
                risk_factors = {
                    'volatility': analysis.get('volatility_risk', 0),
                    'microstructure': analysis.get('microstructure_risk', 0),
                    'barrier': analysis.get('barrier_risk', 0),
                    'pattern': analysis.get('pattern_risk', 0),
                    'stress': analysis.get('stress_risk', 0),
                    'momentum': analysis.get('momentum_risk', 0)
                }
                highest_risk = max(risk_factors, key=risk_factors.get)
                return False, f"knockout risk {knockout_prob*100:.1f}% (high {highest_risk} risk)"
            else:
                # No detailed breakdown available (e.g., insufficient data)
                reason = analysis.get('reason', 'unknown')
                return False, f"knockout risk {knockout_prob*100:.1f}% ({reason})"

        # LAYER 2: Traditional volatility filters (BALANCED)
        if metrics["vol_short"] > 0.00020:
            return False, f"vol too high={metrics['vol_short']:.5f}"

        if metrics["vol_medium"] > 0.00025:
            return False, f"vol_medium too high={metrics['vol_medium']:.5f}"

        # LAYER 3: Consistency and trending (BALANCED)
        if metrics["consistency"] < 0.65:
            return False, f"too choppy (consistency={metrics['consistency']:.3f})"

        if metrics["hurst"] < 0.55:
            return False, f"not trending (hurst={metrics['hurst']:.3f})"

        # LAYER 4: Predictability
        if metrics["entropy"] > 0.90:
            return False, f"high entropy={metrics['entropy']:.3f}"

        # ALL CHECKS PASSED - Safe to enter
        return True, f"safe (knockout risk: {knockout_prob*100:.2f}%)"

    def _hurst_proxy(self, prices: np.ndarray) -> float:
        try:
            lags = [2, 4, 8, 16]
            rs_values = []
            for lag in lags:
                chunks = [prices[i:i + lag] for i in range(0, len(prices) - lag, lag)]
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
    
    def learn_from_knockout(self):
        """Learn from knockout to improve future predictions"""
        if len(self.ticks) >= 30:
            prices = np.array(list(self.ticks))[-30:]
            self.advanced_analyzer.learn_from_knockout(prices)
