"""
Chart Pattern Recognition - Detects technical chart patterns and candlestick patterns.
Recognizes: Head & Shoulders, Triangles, Double Tops/Bottoms, Flags, Wedges, Breakouts
Plus: Japanese candlestick patterns (doji, hammer, engulfing, harami, etc.)
Plus: Multi-timeframe trend analysis and candle-by-candle learning.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque, defaultdict
from logger import agent_logger


class Candle:
    """Represents a single candlestick with OHLC data."""
    def __init__(self, open_p: float, high: float, low: float, close: float, volume: float = 1.0):
        self.open = open_p
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.body = abs(close - open_p)
        self.upper_wick = high - max(open_p, close)
        self.lower_wick = min(open_p, close) - low
        self.total_range = high - low
        self.is_bullish = close > open_p
        self.is_bearish = close < open_p
        self.body_ratio = self.body / self.total_range if self.total_range > 0 else 0

    def __repr__(self):
        return f"Candle(O={self.open:.2f}, H={self.high:.2f}, L={self.low:.2f}, C={self.close:.2f}, {'BULL' if self.is_bullish else 'BEAR'})"


class CandlePatternLearner:
    """
    Learns from every candle movement - tracks how each candle type
    predicts the next N candles' direction. Builds a statistical model
    of candle pattern effectiveness.
    """
    
    def __init__(self, max_history: int = 500):
        self.candle_history = deque(maxlen=max_history)
        self.pattern_performance = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0})
        self.lookahead = 5  # How many candles ahead to check for prediction accuracy
        
    def add_candle(self, candle: Candle):
        """Add a candle and update pattern performance statistics."""
        self.candle_history.append(candle)
        self._update_pattern_learning(candle)
    
    def _update_pattern_learning(self, candle: Candle):
        """Learn from this candle - check if previous patterns predicted correctly."""
        if len(self.candle_history) < self.lookahead + 1:
            return
        
        # Check what patterns were detected `lookahead` candles ago
        history_list = list(self.candle_history)
        for i in range(len(history_list) - self.lookahead):
            past_candle = history_list[i]
            future_candle = history_list[i + self.lookahead]
            
            # Determine if past candle's pattern predicted correctly
            pattern_name = self._classify_candle_type(past_candle)
            if pattern_name == 'unknown':
                continue
            
            # Did the price move in the expected direction?
            if past_candle.is_bullish and future_candle.close > past_candle.close:
                self.pattern_performance[pattern_name]['wins'] += 1
            elif past_candle.is_bearish and future_candle.close < past_candle.close:
                self.pattern_performance[pattern_name]['wins'] += 1
            else:
                self.pattern_performance[pattern_name]['losses'] += 1
            self.pattern_performance[pattern_name]['total'] += 1
    
    def _classify_candle_type(self, candle: Candle) -> str:
        """Classify a candle into a type for learning."""
        if candle.body_ratio < 0.1 and candle.total_range > 0:
            return 'doji'
        if candle.is_bullish and candle.lower_wick > candle.body * 2 and candle.upper_wick < candle.body * 0.3:
            return 'hammer'
        if candle.is_bearish and candle.upper_wick > candle.body * 2 and candle.lower_wick < candle.body * 0.3:
            return 'shooting_star'
        if candle.is_bullish and candle.body > np.mean([c.body for c in list(self.candle_history)[-20:]]) * 1.5 if len(self.candle_history) >= 20 else 0:
            return 'strong_bullish'
        if candle.is_bearish and candle.body > np.mean([c.body for c in list(self.candle_history)[-20:]]) * 1.5 if len(self.candle_history) >= 20 else 0:
            return 'strong_bearish'
        if candle.is_bullish:
            return 'bullish'
        if candle.is_bearish:
            return 'bearish'
        return 'unknown'
    
    def get_pattern_accuracy(self, pattern_name: str) -> float:
        """Get the historical accuracy of a candle pattern."""
        stats = self.pattern_performance.get(pattern_name)
        if not stats or stats['total'] == 0:
            return 0.5
        return stats['wins'] / stats['total']
    
    def get_best_patterns(self, top_n: int = 3) -> List[Tuple[str, float]]:
        """Get the top N most accurate candle patterns."""
        patterns = []
        for name, stats in self.pattern_performance.items():
            if stats['total'] >= 5:  # Minimum sample size
                accuracy = stats['wins'] / stats['total']
                patterns.append((name, accuracy, stats['total']))
        
        patterns.sort(key=lambda x: x[1], reverse=True)
        return [(p[0], p[1]) for p in patterns[:top_n]]


class MultiTimeframeTrendAnalyzer:
    """
    Analyzes trends across multiple timeframes.
    Higher timeframes (slower) define the primary trend.
    Lower timeframes (faster) define entry timing.
    Only trades when multiple timeframes align.
    
    ENHANCED for lower timeframe profitability:
    - Added ultra_short timeframe (10 ticks) for quick entries
    - Added trend confidence scoring (0-100) to identify "sure trends"
    - A "sure trend" requires: all 5 timeframes aligned + strong R-squared + momentum consistency
    - Tracks trend persistence (how long the trend has been valid)
    """
    
    def __init__(self):
        # Define timeframe windows (in ticks)
        # ENHANCED: Added ultra_short for faster entries on lower timeframes
        self.timeframes = {
            'ultra_short': 10,   # ~10 seconds - immediate momentum for quick entries
            'micro': 20,         # ~20 seconds - entry timing
            'lower': 50,         # ~50 seconds - short-term trend
            'medium': 100,       # ~1.7 minutes - secondary trend
            'higher': 200,       # ~3.3 minutes - primary trend
        }
        self.price_histories = {name: deque(maxlen=window) for name, window in self.timeframes.items()}
        
        # Trend persistence tracking
        self._trend_history = deque(maxlen=50)  # Track last 50 trend states
        self._consecutive_trend_ticks = 0       # How many ticks trend has been consistent
        self._last_primary_direction = None
        
    def add_price(self, price: float):
        """Add price to all timeframe histories."""
        for name, history in self.price_histories.items():
            history.append(price)
    
    def get_trend_for_timeframe(self, tf_name: str) -> Dict:
        """
        Analyze trend for a specific timeframe.
        Returns: {'direction': 'up'/'down'/'sideways', 'strength': 0-1, 'momentum': float}
        """
        history = self.price_histories[tf_name]
        if len(history) < 20:
            return {'direction': 'unknown', 'strength': 0.0, 'momentum': 0.0}
        
        prices = list(history)
        
        # Linear regression for slope
        x = np.arange(len(prices))
        slope = np.polyfit(x, prices, 1)[0]
        avg_price = np.mean(prices)
        
        # Normalize slope as percentage change per tick
        momentum = (slope / avg_price) * 100 if avg_price > 0 else 0
        
        # Calculate R-squared for trend strength
        if len(prices) > 2:
            z = np.polyfit(x, prices, 1)
            p = np.poly1d(z)
            residuals = prices - p(x)
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((prices - np.mean(prices)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        else:
            r_squared = 0
        
        # Determine direction
        if momentum > 0.01:
            direction = 'up'
        elif momentum < -0.01:
            direction = 'down'
        else:
            direction = 'sideways'
        
        # Strength based on R-squared and momentum magnitude
        strength = min(abs(r_squared) * 2, 1.0) * min(abs(momentum) * 10, 1.0)
        
        return {
            'direction': direction,
            'strength': strength,
            'momentum': momentum,
            'r_squared': r_squared,
            'slope': slope
        }
    
    def get_aligned_trend(self) -> Dict:
        """
        Get the aligned trend across all timeframes.
        Returns the primary trend direction and alignment score.
        Only returns a direction if higher and medium timeframes agree.
        
        ENHANCED: 
        - 5 timeframes now (ultra_short, micro, lower, medium, higher)
        - Added trend_confidence_score (0-100) for "sure trend" identification
        - Added trend_persistence (how long trend has been consistent)
        - A "sure trend" requires: confidence >= 80 AND persistence >= 20 ticks
        """
        trends = {}
        for tf_name in self.timeframes:
            trends[tf_name] = self.get_trend_for_timeframe(tf_name)
        
        higher = trends.get('higher', {})
        medium = trends.get('medium', {})
        lower = trends.get('lower', {})
        micro = trends.get('micro', {})
        ultra_short = trends.get('ultra_short', {})
        
        higher_dir = higher.get('direction', 'unknown')
        medium_dir = medium.get('direction', 'unknown')
        lower_dir = lower.get('direction', 'unknown')
        micro_dir = micro.get('direction', 'unknown')
        ultra_short_dir = ultra_short.get('direction', 'unknown')
        
        # Count directions across timeframes (weighted by timeframe importance)
        direction_weights = {
            'up': 0,
            'down': 0,
            'sideways': 0,
            'unknown': 0
        }
        
        # ENHANCED weights: higher=5x, medium=3x, lower=2x, micro=1x, ultra_short=0.5x
        weights = {'higher': 5, 'medium': 3, 'lower': 2, 'micro': 1, 'ultra_short': 0.5}
        
        for tf_name, trend in trends.items():
            d = trend.get('direction', 'unknown')
            w = weights.get(tf_name, 1)
            if d in direction_weights:
                direction_weights[d] += w * trend.get('strength', 0.5)
        
        # Determine primary direction
        if direction_weights['up'] > direction_weights['down'] and direction_weights['up'] > direction_weights['sideways']:
            primary = 'up'
            alignment_score = direction_weights['up'] / (direction_weights['up'] + direction_weights['down'] + direction_weights['sideways'] + 0.001)
        elif direction_weights['down'] > direction_weights['up'] and direction_weights['down'] > direction_weights['sideways']:
            primary = 'down'
            alignment_score = direction_weights['down'] / (direction_weights['up'] + direction_weights['down'] + direction_weights['sideways'] + 0.001)
        else:
            primary = 'sideways'
            alignment_score = direction_weights['sideways'] / (direction_weights['up'] + direction_weights['down'] + direction_weights['sideways'] + 0.001)
        
        # Check if higher and medium timeframes agree (required for strong signal)
        higher_medium_agree = higher_dir == medium_dir and higher_dir != 'unknown' and higher_dir != 'sideways'
        
        # Check if ALL THREE (higher + medium + lower) align
        all_three_align = higher_medium_agree and lower_dir == higher_dir and lower_dir != 'unknown' and lower_dir != 'sideways'
        
        # Check if all timeframes align (strongest signal)
        all_align = (
            higher_dir == medium_dir == lower_dir == micro_dir and
            higher_dir != 'unknown' and higher_dir != 'sideways'
        )
        
        # ENHANCED: Check if ALL 5 timeframes align (ultra_short included)
        all_5_align = (
            higher_dir == medium_dir == lower_dir == micro_dir == ultra_short_dir and
            higher_dir != 'unknown' and higher_dir != 'sideways'
        )
        
        # === TREND CONFIDENCE SCORING ===
        # This identifies "SURE TRENDS" - trends so clear we can trade with high confidence
        # Score 0-100 where 80+ = "sure trend"
        trend_confidence_score = 0
        
        # 1. Timeframe alignment (max 40 points)
        if all_5_align:
            trend_confidence_score += 40  # All 5 timeframes aligned = very strong
        elif all_align:
            trend_confidence_score += 30  # 4 timeframes aligned = strong
        elif higher_medium_agree:
            trend_confidence_score += 20  # 2 main timeframes agree = moderate
        
        # 2. R-squared strength across timeframes (max 30 points)
        r_squared_scores = []
        for tf_name in ['higher', 'medium', 'lower']:
            tf = trends.get(tf_name, {})
            r2 = abs(tf.get('r_squared', 0))
            r_squared_scores.append(min(r2 * 30, 10))  # Each timeframe up to 10 points
        trend_confidence_score += sum(r_squared_scores)
        
        # 3. Momentum consistency (max 20 points)
        # All timeframes should have momentum in the same direction
        momentum_directions = []
        for tf_name in self.timeframes:
            tf = trends.get(tf_name, {})
            mom = tf.get('momentum', 0)
            if mom > 0.005:
                momentum_directions.append(1)
            elif mom < -0.005:
                momentum_directions.append(-1)
            else:
                momentum_directions.append(0)
        
        # Check if all non-zero momentum directions agree
        non_zero_mom = [d for d in momentum_directions if d != 0]
        if non_zero_mom:
            all_same_dir = all(d == non_zero_mom[0] for d in non_zero_mom)
            if all_same_dir:
                trend_confidence_score += 20  # All momentum in same direction
            elif len(non_zero_mom) >= 3:
                trend_confidence_score += 10  # Most agree
        else:
            trend_confidence_score += 5  # Low momentum overall
        
        # 4. Trend persistence (max 10 points)
        # Track how long the trend direction has been consistent
        if primary in ('up', 'down'):
            if primary == self._last_primary_direction:
                self._consecutive_trend_ticks += 1
            else:
                self._consecutive_trend_ticks = 0
            self._last_primary_direction = primary
            
            persistence_points = min(self._consecutive_trend_ticks / 5, 10)  # 1 point per 5 ticks, max 10
            trend_confidence_score += persistence_points
        
        # Cap at 100
        trend_confidence_score = min(trend_confidence_score, 100)
        
        # Determine if this is a "SURE TREND"
        is_sure_trend = trend_confidence_score >= 80 and self._consecutive_trend_ticks >= 20
        
        return {
            'primary_direction': primary,
            'alignment_score': alignment_score,
            'higher_medium_agree': higher_medium_agree,
            'all_three_align': higher_medium_agree and lower_dir == higher_dir and lower_dir != 'unknown' and lower_dir != 'sideways',
            'all_timeframes_align': all_align,
            'all_5_timeframes_align': all_5_align,
            'timeframes': trends,
            'is_trending': higher_medium_agree and lower_dir == higher_dir and lower_dir != 'unknown' and lower_dir != 'sideways' and primary in ('up', 'down'),
            'strength': alignment_score * (1.5 if all_5_align else 1.3 if all_align else 1.15 if all_three_align else 1.0 if higher_medium_agree else 0.5),
            # ENHANCED fields:
            'trend_confidence_score': trend_confidence_score,  # 0-100 score
            'is_sure_trend': is_sure_trend,                    # True if confidence >= 80 AND persistent
            'trend_persistence': self._consecutive_trend_ticks, # How many ticks trend has been consistent
            'momentum_consistency': all(m == non_zero_mom[0] for m in non_zero_mom) if non_zero_mom else False,
        }


class ChartPatternRecognizer:
    """
    Recognizes technical chart patterns for trading opportunities.
    Detects 8+ chart patterns that indicate potential price movements.
    Plus: Japanese candlestick patterns and multi-timeframe trend analysis.
    """
    
    def __init__(self, window: int = 100):
        self.window = window
        self.prices = deque(maxlen=window)
        self.patterns_detected = {}
        self.candle_learner = CandlePatternLearner()
        self.multi_tf_analyzer = MultiTimeframeTrendAnalyzer()
        self.last_candle = None
        self.candle_count = 0
    
    def add_price(self, price: float):
        """Add price to pattern recognizer with candle formation.
        
        For synthetic indices (R_10..R_100), ticks arrive ~1/sec so we form
        a candle every 3 ticks to get enough candles for pattern detection
        within the 10-minute contract window.
        """
        self.prices.append(price)
        self.multi_tf_analyzer.add_price(price)
        
        # Build candles from tick data (group every N ticks into a candle)
        self.candle_count += 1
        if self.last_candle is None:
            self.last_candle = {'open': price, 'high': price, 'low': price, 'close': price, 'ticks': 1}
        else:
            candle = self.last_candle
            candle['high'] = max(candle['high'], price)
            candle['low'] = min(candle['low'], price)
            candle['close'] = price
            candle['ticks'] += 1
            
            # Every 3 ticks, form a complete candle and learn from it
            # Faster candle formation = more pattern detections in a 10-min window
            if candle['ticks'] >= 3:
                new_candle = Candle(
                    open_p=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close']
                )
                self.candle_learner.add_candle(new_candle)
                # Start new candle
                self.last_candle = {'open': price, 'high': price, 'low': price, 'close': price, 'ticks': 1}
    
    def detect_all_patterns(self) -> Dict:
        """Detect all chart patterns in current price data."""
        if len(self.prices) < 20:
            return {}
        
        patterns = {}
        
        # Detect each chart pattern type
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
        
        # Add candlestick pattern analysis
        candle_patterns = self._detect_candlestick_patterns()
        if candle_patterns:
            patterns.update(candle_patterns)
        
        # Add multi-timeframe trend analysis
        tf_analysis = self.multi_tf_analyzer.get_aligned_trend()
        if tf_analysis['is_trending']:
            patterns['multi_timeframe_trend'] = {
                'pattern': 'multi_timeframe_trend',
                'signal': f"{tf_analysis['primary_direction']}_trend",
                'confidence': min(tf_analysis['strength'], 0.95),
                'alignment_score': tf_analysis['alignment_score'],
                'all_timeframes_align': tf_analysis['all_timeframes_align'],
                'higher_medium_agree': tf_analysis['higher_medium_agree'],
                'timeframes': {
                    tf: {
                        'direction': t['direction'],
                        'strength': t['strength'],
                        'momentum': t['momentum']
                    }
                    for tf, t in tf_analysis['timeframes'].items()
                }
            }
        
        # Add candle learner insights
        best_patterns = self.candle_learner.get_best_patterns(3)
        if best_patterns:
            patterns['candle_learning'] = {
                'pattern': 'candle_learning',
                'signal': 'learning_insight',
                'confidence': 0.6,
                'best_patterns': best_patterns,
                'details': {
                    name: {
                        'accuracy': acc,
                        'total_observations': self.candle_learner.pattern_performance[name]['total']
                    }
                    for name, acc in best_patterns
                }
            }
        
        self.patterns_detected = patterns
        return patterns
    
    def _detect_candlestick_patterns(self) -> Dict:
        """Detect Japanese candlestick patterns from recent candles."""
        if len(self.candle_learner.candle_history) < 3:
            return {}
        
        candles = list(self.candle_learner.candle_history)
        patterns = {}
        
        # Need at least 2 candles for most patterns
        if len(candles) >= 2:
            c1, c2 = candles[-2], candles[-1]
            
            # Bullish Engulfing
            if (c1.is_bearish and c2.is_bullish and 
                c2.open < c1.close and c2.close > c1.open):
                patterns['bullish_engulfing'] = {
                    'pattern': 'bullish_engulfing',
                    'signal': 'bullish_reversal',
                    'confidence': 0.75,
                    'strength': c2.body / c1.body if c1.body > 0 else 1.0
                }
            
            # Bearish Engulfing
            if (c1.is_bullish and c2.is_bearish and 
                c2.open > c1.close and c2.close < c1.open):
                patterns['bearish_engulfing'] = {
                    'pattern': 'bearish_engulfing',
                    'signal': 'bearish_reversal',
                    'confidence': 0.75,
                    'strength': c2.body / c1.body if c1.body > 0 else 1.0
                }
            
            # Bullish Harami
            if (c1.is_bearish and c2.is_bullish and
                c2.open > c1.close and c2.close < c1.open and
                c2.body < c1.body * 0.5):
                patterns['bullish_harami'] = {
                    'pattern': 'bullish_harami',
                    'signal': 'bullish_reversal',
                    'confidence': 0.65
                }
            
            # Bearish Harami
            if (c1.is_bullish and c2.is_bearish and
                c2.open < c1.close and c2.close > c1.open and
                c2.body < c1.body * 0.5):
                patterns['bearish_harami'] = {
                    'pattern': 'bearish_harami',
                    'signal': 'bearish_reversal',
                    'confidence': 0.65
                }
        
        # Check last single candle for doji/hammer/shooting star
        if len(candles) >= 1:
            last = candles[-1]
            
            # Doji (indecision)
            if last.body_ratio < 0.1 and last.total_range > 0:
                patterns['doji'] = {
                    'pattern': 'doji',
                    'signal': 'indecision',
                    'confidence': 0.5,
                    'location': 'high' if last.close > np.mean([c.close for c in candles[-10:]]) else 'low' if len(candles) >= 10 else 'middle'
                }
            
            # Hammer (bullish reversal)
            if (last.is_bullish and last.lower_wick > last.body * 2 and 
                last.upper_wick < last.body * 0.3 and last.body > 0):
                patterns['hammer'] = {
                    'pattern': 'hammer',
                    'signal': 'bullish_reversal',
                    'confidence': 0.7,
                    'lower_wick_ratio': last.lower_wick / last.body
                }
            
            # Shooting Star (bearish reversal)
            if (last.is_bearish and last.upper_wick > last.body * 2 and 
                last.lower_wick < last.body * 0.3 and last.body > 0):
                patterns['shooting_star'] = {
                    'pattern': 'shooting_star',
                    'signal': 'bearish_reversal',
                    'confidence': 0.7,
                    'upper_wick_ratio': last.upper_wick / last.body
                }
        
        # Three White Soldiers (strong bullish continuation)
        if len(candles) >= 3:
            c1, c2, c3 = candles[-3], candles[-2], candles[-1]
            if (c1.is_bullish and c2.is_bullish and c3.is_bullish and
                c2.close > c1.close and c3.close > c2.close and
                c2.open > c1.open and c3.open > c2.open):
                patterns['three_white_soldiers'] = {
                    'pattern': 'three_white_soldiers',
                    'signal': 'bullish_continuation',
                    'confidence': 0.8
                }
            
            # Three Black Crows (strong bearish continuation)
            if (c1.is_bearish and c2.is_bearish and c3.is_bearish and
                c2.close < c1.close and c3.close < c2.close and
                c2.open < c1.open and c3.open < c2.open):
                patterns['three_black_crows'] = {
                    'pattern': 'three_black_crows',
                    'signal': 'bearish_continuation',
                    'confidence': 0.8
                }
        
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
        """Detect flag pattern (continuation pattern).
        
        For synthetic indices (R_10..R_100) with prices ~4884, we use
        PERCENTAGE-based thresholds instead of absolute price differences.
        """
        if len(self.prices) < 15:
            return None
        
        prices = list(self.prices)[-15:]
        avg_price = np.mean(prices)
        if avg_price == 0:
            return None
        
        # Flag: low volatility after strong trend
        recent_volatility = np.std(prices[-5:])
        prior_volatility = np.std(prices[:-5])
        
        if prior_volatility == 0 or recent_volatility >= prior_volatility:
            return None
        
        # Strong trend before consolidation (as percentage of average price)
        trend_pct = (prices[-6] - prices[0]) / avg_price * 100
        
        # Require at least 0.01% trend (works for any price level)
        if abs(trend_pct) < 0.01:
            return None
        
        signal_direction = 'bullish' if trend_pct > 0 else 'bearish'
        pole_height = abs(trend_pct)
        target_pct = prices[-1] * (1 + pole_height * 0.0075) if trend_pct > 0 else prices[-1] * (1 - pole_height * 0.0075)
        
        return {
            'pattern': 'flag',
            'signal': f'{signal_direction}_continuation',
            'confidence': 0.70,
            'pole_height_pct': pole_height,
            'target_price': target_pct
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
        """Detect potential breakout from consolidation.
        
        For synthetic indices (R_10..R_100), uses percentage-based
        momentum that scales with price level.
        """
        if len(self.prices) < 10:
            return None
        
        prices = list(self.prices)[-10:]
        
        # Recent strong move after consolidation
        recent_volatility = np.std(prices[-5:])
        consolidation_volatility = np.std(prices[:-5])
        
        if consolidation_volatility == 0:
            return None
        
        recent_move = prices[-1] - prices[0]
        avg_price = np.mean(prices)
        
        # Use percentage momentum instead of absolute
        recent_move_pct = (recent_move / avg_price) * 100 if avg_price > 0 else 0
        momentum = abs(recent_move) / consolidation_volatility
        
        if momentum > 2.0 and abs(recent_move_pct) > 0.005:  # Strong breakout
            direction = 'up' if recent_move > 0 else 'down'
            
            return {
                'pattern': 'breakout',
                'signal': f'{direction}side_breakout',
                'confidence': 0.72,
                'momentum_strength': momentum,
                'breakout_price': prices[-1],
                'breakout_pct': recent_move_pct
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