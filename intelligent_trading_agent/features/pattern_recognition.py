"""
Chart Pattern Recognition - Detects technical chart patterns.
Recognizes: Head & Shoulders, Triangles, Double Tops/Bottoms, Flags, Wedges, Breakouts
"""

import numpy as np
from typing import Dict, List, Optional
from collections import deque


class ChartPatternRecognizer:
    """
    Recognizes technical chart patterns for trading opportunities.
    Detects 8+ chart patterns that indicate potential price movements.
    """
    
    def __init__(self, window: int = 100):
        self.window = window
        self.prices = deque(maxlen=window)
        self.patterns_detected = {}
    
    def add_price(self, price: float):
        """Add price to pattern recognizer."""
        self.prices.append(price)
    
    def detect_all_patterns(self) -> Dict:
        """Detect all chart patterns in current price data."""
        if len(self.prices) < 20:
            return {}
        
        patterns = {}
        
        # Detect each pattern type
        patterns_to_check = [
            ('head_shoulders', self.detect_head_and_shoulders),
            ('double_top', self.detect_double_top),
            ('double_bottom', self.detect_double_bottom),
            ('triangle', self.detect_triangle),
            ('flag', self.detect_flag),
            ('wedge', self.detect_wedge),
            ('breakout', self.detect_breakout),
            ('support_resistance', self.detect_support_resistance),
        ]
        
        for pattern_name, detector_func in patterns_to_check:
            result = detector_func()
            if result:
                patterns[pattern_name] = result
        
        self.patterns_detected = patterns
        return patterns
    
    def detect_head_and_shoulders(self) -> Optional[Dict]:
        """Detect head and shoulders pattern (bearish reversal)."""
        if len(self.prices) < 30:
            return None
        
        prices = list(self.prices)[-30:]
        peaks = self._find_local_maxima(prices)
        
        if len(peaks) < 3:
            return None
        
        left_shoulder = prices[peaks[0]]
        head = prices[peaks[1]]
        right_shoulder = prices[peaks[2]]
        
        # Head must be highest
        if head <= left_shoulder or head <= right_shoulder:
            return None
        
        # Shoulders should be similar height (within 5%)
        shoulder_diff = abs(left_shoulder - right_shoulder) / max(left_shoulder, right_shoulder)
        if shoulder_diff > 0.05:
            return None
        
        neckline = (left_shoulder + right_shoulder) / 2
        target = neckline - (head - neckline)
        
        return {
            'pattern': 'head_and_shoulders',
            'signal': 'bearish',
            'confidence': 0.75,
            'target_price': target,
            'breakdown_level': neckline
        }
    
    def detect_double_top(self) -> Optional[Dict]:
        """Detect double top pattern (bearish reversal)."""
        if len(self.prices) < 20:
            return None
        
        prices = list(self.prices)[-20:]
        peaks = self._find_local_maxima(prices)
        
        if len(peaks) < 2:
            return None
        
        top1 = prices[peaks[0]]
        top2 = prices[peaks[1]]
        
        # Tops should be similar (within 3%)
        top_diff = abs(top1 - top2) / max(top1, top2)
        if top_diff > 0.03:
            return None
        
        # Find valley between tops for support
        valley_min = min(prices[peaks[0]:peaks[1]])
        target = valley_min - (top1 - valley_min)
        
        return {
            'pattern': 'double_top',
            'signal': 'bearish',
            'confidence': 0.70,
            'resistance': max(top1, top2),
            'support': valley_min,
            'target_price': target
        }
    
    def detect_double_bottom(self) -> Optional[Dict]:
        """Detect double bottom pattern (bullish reversal)."""
        if len(self.prices) < 20:
            return None
        
        prices = list(self.prices)[-20:]
        troughs = self._find_local_minima(prices)
        
        if len(troughs) < 2:
            return None
        
        bottom1 = prices[troughs[0]]
        bottom2 = prices[troughs[1]]
        
        # Bottoms should be similar (within 3%)
        bottom_diff = abs(bottom1 - bottom2) / max(bottom1, bottom2)
        if bottom_diff > 0.03:
            return None
        
        # Find peak between bottoms for resistance
        peak_max = max(prices[troughs[0]:troughs[1]])
        target = peak_max + (peak_max - bottom1)
        
        return {
            'pattern': 'double_bottom',
            'signal': 'bullish',
            'confidence': 0.70,
            'support': min(bottom1, bottom2),
            'resistance': peak_max,
            'target_price': target
        }
    
    def detect_triangle(self) -> Optional[Dict]:
        """Detect triangle consolidation pattern."""
        if len(self.prices) < 20:
            return None
        
        prices = list(self.prices)[-20:]
        highs = self._find_local_maxima(prices)
        lows = self._find_local_minima(prices)
        
        if len(highs) < 2 or len(lows) < 2:
            return None
        
        high_trend = prices[highs[-1]] - prices[highs[-2]]
        low_trend = prices[lows[-1]] - prices[lows[-2]]
        
        # Check for convergence (opposite trends = converging)
        converging = (high_trend < 0 and low_trend > 0) or (high_trend > 0 and low_trend < 0)
        
        if not converging:
            return None
        
        return {
            'pattern': 'triangle',
            'signal': 'breakout_pending',
            'confidence': 0.65,
            'upper_level': max([prices[i] for i in highs]),
            'lower_level': min([prices[i] for i in lows]),
            'breakout_direction': 'up' if low_trend > 0 else 'down'
        }
    
    def detect_flag(self) -> Optional[Dict]:
        """Detect flag pattern (continuation pattern)."""
        if len(self.prices) < 15:
            return None
        
        prices = list(self.prices)[-15:]
        
        # Flag: low volatility after strong trend
        recent_volatility = np.std(prices[-5:])
        prior_volatility = np.std(prices[:-5])
        
        if prior_volatility == 0 or recent_volatility >= prior_volatility:
            return None
        
        # Strong trend before consolidation
        trend = prices[-6] - prices[0]
        
        if abs(trend) < 0.5:
            return None
        
        signal_direction = 'bullish' if trend > 0 else 'bearish'
        pole_height = abs(trend)
        target = prices[-1] + (pole_height * 0.75) if trend > 0 else prices[-1] - (pole_height * 0.75)
        
        return {
            'pattern': 'flag',
            'signal': f'{signal_direction}_continuation',
            'confidence': 0.70,
            'pole_height': pole_height,
            'target_price': target
        }
    
    def detect_wedge(self) -> Optional[Dict]:
        """Detect rising or falling wedge pattern."""
        if len(self.prices) < 15:
            return None
        
        prices = list(self.prices)[-15:]
        highs = self._find_local_maxima(prices)
        lows = self._find_local_minima(prices)
        
        if len(highs) < 2 or len(lows) < 2:
            return None
        
        high_trend = prices[highs[-1]] - prices[highs[-2]]
        low_trend = prices[lows[-1]] - prices[lows[-2]]
        
        # Both moving in same direction = converging wedge
        if (high_trend > 0 and low_trend > 0) or (high_trend < 0 and low_trend < 0):
            wedge_type = 'rising' if high_trend > 0 else 'falling'
            
            return {
                'pattern': 'wedge',
                'signal': f'{wedge_type}_wedge',
                'confidence': 0.65,
                'breakout_likely': True,
                'upper_level': max([prices[i] for i in highs]),
                'lower_level': min([prices[i] for i in lows])
            }
        
        return None
    
    def detect_breakout(self) -> Optional[Dict]:
        """Detect potential breakout from consolidation."""
        if len(self.prices) < 10:
            return None
        
        prices = list(self.prices)[-10:]
        
        # Recent strong move after consolidation
        recent_volatility = np.std(prices[-5:])
        consolidation_volatility = np.std(prices[:-5])
        
        if consolidation_volatility == 0:
            return None
        
        recent_move = prices[-1] - prices[0]
        momentum = abs(recent_move) / consolidation_volatility
        
        if momentum > 2.0:  # Strong breakout
            direction = 'up' if recent_move > 0 else 'down'
            
            return {
                'pattern': 'breakout',
                'signal': f'{direction}side_breakout',
                'confidence': 0.72,
                'momentum_strength': momentum,
                'breakout_price': prices[-1]
            }
        
        return None
    
    def detect_support_resistance(self) -> Optional[Dict]:
        """Detect support and resistance levels."""
        if len(self.prices) < 20:
            return None
        
        prices = list(self.prices)[-20:]
        
        supports_idx = self._find_local_minima(prices)
        resistances_idx = self._find_local_maxima(prices)
        
        if not supports_idx or not resistances_idx:
            return None
        
        supports = [prices[i] for i in supports_idx]
        resistances = [prices[i] for i in resistances_idx]
        
        primary_support = min(supports)
        primary_resistance = max(resistances)
        
        return {
            'pattern': 'support_resistance',
            'signal': 'structural',
            'confidence': 0.80,
            'primary_support': primary_support,
            'primary_resistance': primary_resistance,
            'middle_ground': (primary_support + primary_resistance) / 2,
            'range': primary_resistance - primary_support
        }
    
    def get_strongest_pattern(self) -> Optional[Dict]:
        """Get the strongest detected pattern."""
        if not self.patterns_detected:
            return None
        
        strongest = max(self.patterns_detected.items(), key=lambda x: x[1].get('confidence', 0))
        return {'name': strongest[0], **strongest[1]}
    
    def _find_local_maxima(self, prices: List[float]) -> List[int]:
        """Find indices of local maximum values."""
        maxima = []
        for i in range(1, len(prices) - 1):
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                maxima.append(i)
        return maxima
    
    def _find_local_minima(self, prices: List[float]) -> List[int]:
        """Find indices of local minimum values."""
        minima = []
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                minima.append(i)
        return minima
