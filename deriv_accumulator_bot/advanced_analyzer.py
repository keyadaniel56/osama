"""
Advanced Market Analyzer - Multi-layered knockout prediction system
Analyzes market microstructure to predict knockout probability
"""

import numpy as np
from collections import deque
from typing import Tuple, Dict


class AdvancedMarketAnalyzer:
    """
    Advanced analyzer that predicts knockout probability using multiple techniques:
    1. Volatility regime detection
    2. Microstructure analysis (tick-by-tick patterns)
    3. Barrier distance estimation
    4. Historical knockout pattern matching
    5. Market stress indicators
    """
    
    def __init__(self, window: int = 50):
        self.window = window
        self.ticks = deque(maxlen=window * 2)
        self.knockout_patterns = []  # Learn from past knockouts
        
    def add_tick(self, price: float):
        self.ticks.append(price)
    
    def ready(self) -> bool:
        return len(self.ticks) >= self.window
    
    def predict_knockout_probability(self, growth_rate: float = 0.01) -> Tuple[float, Dict]:
        """
        Predict probability of knockout in next 3 ticks.
        Returns (probability, detailed_analysis)
        
        probability: 0.0 = safe, 1.0 = certain knockout
        """
        if not self.ready():
            return 1.0, {"reason": "insufficient data"}
        
        prices = np.array(list(self.ticks))[-self.window:]
        
        # Multiple analysis layers
        vol_risk = self._analyze_volatility_regime(prices)
        micro_risk = self._analyze_microstructure(prices)
        barrier_risk = self._estimate_barrier_distance(prices, growth_rate)
        pattern_risk = self._detect_knockout_patterns(prices)
        stress_risk = self._measure_market_stress(prices)
        momentum_risk = self._analyze_momentum_stability(prices)
        
        # Weighted combination of all risk factors
        weights = {
            'volatility': 0.25,
            'microstructure': 0.20,
            'barrier': 0.20,
            'pattern': 0.15,
            'stress': 0.10,
            'momentum': 0.10
        }
        
        total_risk = (
            vol_risk * weights['volatility'] +
            micro_risk * weights['microstructure'] +
            barrier_risk * weights['barrier'] +
            pattern_risk * weights['pattern'] +
            stress_risk * weights['stress'] +
            momentum_risk * weights['momentum']
        )
        
        analysis = {
            'total_risk': total_risk,
            'volatility_risk': vol_risk,
            'microstructure_risk': micro_risk,
            'barrier_risk': barrier_risk,
            'pattern_risk': pattern_risk,
            'stress_risk': stress_risk,
            'momentum_risk': momentum_risk,
            'recommendation': 'REJECT' if total_risk > 0.05 else 'ACCEPT'
        }
        
        return total_risk, analysis
    
    def _analyze_volatility_regime(self, prices: np.ndarray) -> float:
        """
        Analyze volatility regime and predict sudden spikes.
        Returns risk score 0.0-1.0
        """
        returns = np.diff(prices) / (prices[:-1] + 1e-9)
        
        # Multi-timeframe volatility
        vol_1 = np.std(returns[-3:])   # Ultra-short (last 3 ticks)
        vol_5 = np.std(returns[-5:])   # Short
        vol_10 = np.std(returns[-10:]) # Medium
        vol_20 = np.std(returns[-20:]) # Long
        
        # Check for volatility expansion
        vol_expanding = (vol_1 > vol_5 > vol_10)
        
        # Check for volatility clustering (high vol follows high vol)
        recent_high_vol = np.sum(np.abs(returns[-5:]) > vol_20 * 2)
        
        # Extreme move detection
        max_recent_move = np.max(np.abs(returns[-5:]))
        
        risk = 0.0
        
        # Risk from high absolute volatility
        if vol_1 > 0.00015:
            risk += 0.4
        elif vol_1 > 0.00010:
            risk += 0.2
        
        # Risk from volatility expansion
        if vol_expanding:
            risk += 0.3
        
        # Risk from volatility clustering
        if recent_high_vol >= 2:
            risk += 0.2
        
        # Risk from extreme recent moves
        if max_recent_move > 0.0003:
            risk += 0.3
        
        return min(risk, 1.0)
    
    def _analyze_microstructure(self, prices: np.ndarray) -> float:
        """
        Analyze tick-by-tick microstructure for reversal signals.
        Returns risk score 0.0-1.0
        """
        returns = np.diff(prices) / (prices[:-1] + 1e-9)
        
        # Detect rapid reversals (up-down-up or down-up-down)
        last_3_signs = np.sign(returns[-3:])
        reversals = np.sum(np.abs(np.diff(last_3_signs))) / 2
        
        # Detect acceleration (increasing move sizes)
        last_3_abs = np.abs(returns[-3:])
        accelerating = (last_3_abs[-1] > last_3_abs[-2] > last_3_abs[-3])
        
        # Detect exhaustion (very large move followed by small moves)
        if len(returns) >= 5:
            recent_range = np.max(np.abs(returns[-5:]))
            current_move = np.abs(returns[-1])
            exhaustion = (recent_range > 0.0002 and current_move < recent_range * 0.3)
        else:
            exhaustion = False
        
        # Tick imbalance (too many moves in one direction)
        direction_balance = np.abs(np.sum(np.sign(returns[-10:]))) / 10
        
        risk = 0.0
        
        if reversals >= 2:
            risk += 0.4  # Choppy market
        
        if accelerating:
            risk += 0.3  # Momentum building (could reverse)
        
        if exhaustion:
            risk += 0.2  # Exhaustion reversal likely
        
        if direction_balance > 0.8:
            risk += 0.2  # Overextended in one direction
        
        return min(risk, 1.0)
    
    def _estimate_barrier_distance(self, prices: np.ndarray, growth_rate: float) -> float:
        """
        Estimate how close price might get to knockout barrier.
        Returns risk score 0.0-1.0
        """
        current_price = prices[-1]
        returns = np.diff(prices) / (prices[:-1] + 1e-9)
        
        # Estimate barrier distance (accumulator grows by growth_rate per tick)
        # Barrier is approximately at current_price * (1 + growth_rate * ticks)
        # We care about next 3 ticks
        barrier_distance_pct = growth_rate * 3  # ~3% for 1% growth over 3 ticks
        
        # Estimate maximum adverse move in next 3 ticks
        recent_vol = np.std(returns[-10:])
        max_expected_move = recent_vol * 3 * 2.5  # 2.5 std devs (99% confidence)
        
        # Risk increases as expected move approaches barrier
        risk_ratio = max_expected_move / barrier_distance_pct
        
        risk = 0.0
        
        if risk_ratio > 0.8:
            risk = 0.9  # Very high risk
        elif risk_ratio > 0.6:
            risk = 0.6
        elif risk_ratio > 0.4:
            risk = 0.3
        elif risk_ratio > 0.2:
            risk = 0.1
        
        return risk
    
    def _detect_knockout_patterns(self, prices: np.ndarray) -> float:
        """
        Detect patterns that historically led to knockouts.
        Returns risk score 0.0-1.0
        """
        returns = np.diff(prices) / (prices[:-1] + 1e-9)
        
        # Pattern 1: Sudden spike after calm period
        recent_vol = np.std(returns[-5:])
        previous_vol = np.std(returns[-15:-5])
        vol_spike = recent_vol > previous_vol * 2
        
        # Pattern 2: Gap-like behavior (large single move)
        max_single_move = np.max(np.abs(returns[-5:]))
        avg_move = np.mean(np.abs(returns[-20:]))
        gap_behavior = max_single_move > avg_move * 3
        
        # Pattern 3: Whipsaw (rapid back-and-forth)
        sign_changes = np.sum(np.abs(np.diff(np.sign(returns[-10:])))) / 2
        whipsaw = sign_changes >= 5
        
        # Pattern 4: Trend exhaustion (long run in one direction)
        consecutive_same_direction = 0
        for i in range(len(returns)-1, max(0, len(returns)-10), -1):
            if np.sign(returns[i]) == np.sign(returns[len(returns)-1]):
                consecutive_same_direction += 1
            else:
                break
        exhaustion = consecutive_same_direction >= 7
        
        risk = 0.0
        
        if vol_spike:
            risk += 0.3
        
        if gap_behavior:
            risk += 0.4
        
        if whipsaw:
            risk += 0.3
        
        if exhaustion:
            risk += 0.2
        
        return min(risk, 1.0)
    
    def _measure_market_stress(self, prices: np.ndarray) -> float:
        """
        Measure overall market stress indicators.
        Returns risk score 0.0-1.0
        """
        returns = np.diff(prices) / (prices[:-1] + 1e-9)
        
        # Stress indicator 1: Kurtosis (fat tails = stress)
        if len(returns) >= 20:
            kurtosis = np.mean((returns - np.mean(returns))**4) / (np.std(returns)**4 + 1e-9)
            high_kurtosis = kurtosis > 4  # Normal is 3
        else:
            high_kurtosis = False
        
        # Stress indicator 2: Range expansion
        recent_range = np.max(prices[-10:]) - np.min(prices[-10:])
        previous_range = np.max(prices[-20:-10]) - np.min(prices[-20:-10])
        range_expanding = recent_range > previous_range * 1.5
        
        # Stress indicator 3: Autocorrelation breakdown
        if len(returns) >= 20:
            ac_recent = np.corrcoef(returns[-10:-1], returns[-9:])[0, 1]
            ac_previous = np.corrcoef(returns[-20:-11], returns[-19:-10])[0, 1]
            ac_breakdown = (not np.isnan(ac_recent) and not np.isnan(ac_previous) and 
                          abs(ac_recent - ac_previous) > 0.5)
        else:
            ac_breakdown = False
        
        risk = 0.0
        
        if high_kurtosis:
            risk += 0.3
        
        if range_expanding:
            risk += 0.4
        
        if ac_breakdown:
            risk += 0.3
        
        return min(risk, 1.0)
    
    def _analyze_momentum_stability(self, prices: np.ndarray) -> float:
        """
        Analyze momentum stability and continuation probability.
        Returns risk score 0.0-1.0
        """
        returns = np.diff(prices) / (prices[:-1] + 1e-9)
        
        # Check momentum consistency
        recent_momentum = np.mean(returns[-5:])
        previous_momentum = np.mean(returns[-10:-5])
        
        # Momentum reversal risk
        momentum_reversal = (recent_momentum * previous_momentum < 0)
        
        # Momentum weakening
        momentum_weakening = (abs(recent_momentum) < abs(previous_momentum) * 0.5)
        
        # Momentum acceleration (can lead to reversal)
        momentum_acceleration = (abs(recent_momentum) > abs(previous_momentum) * 2)
        
        risk = 0.0
        
        if momentum_reversal:
            risk += 0.5
        
        if momentum_weakening:
            risk += 0.3
        
        if momentum_acceleration:
            risk += 0.2
        
        return min(risk, 1.0)
    
    def learn_from_knockout(self, prices_before_knockout: np.ndarray):
        """
        Learn from knockout events to improve future predictions.
        """
        self.knockout_patterns.append({
            'prices': prices_before_knockout.copy(),
            'volatility': np.std(np.diff(prices_before_knockout)),
            'pattern': 'knockout'
        })
        
        # Keep only last 100 knockout patterns
        if len(self.knockout_patterns) > 100:
            self.knockout_patterns.pop(0)
