"""
Unified decision engine that combines ML predictions + pattern recognition + technical indicators.
Uses ensemble approach for robust trade signals.
"""

from typing import Dict, Tuple, Optional
import numpy as np
from logger import agent_logger
from config import MIN_CONFIDENCE


class DecisionEngine:
    """
    Intelligent decision engine combining:
    1. ML model predictions (primary)
    2. Chart pattern recognition (secondary)
    3. Technical indicators (tertiary)
    """
    
    def __init__(self):
        self.ml_weight = 0.5      # ML model confidence weight
        self.pattern_weight = 0.3  # Pattern recognition weight
        self.indicator_weight = 0.2 # Technical indicators weight
        
        # Thresholds for confidence
        self.min_ensemble_confidence = MIN_CONFIDENCE
        
    def make_decision(
        self,
        ml_prediction: Optional[Dict],
        patterns: Optional[Dict],
        indicators: Optional[Dict],
        market_state: str,
        market_health: float
    ) -> Tuple[Optional[str], float]:
        """
        Make trading decision using ensemble of signals.
        
        Returns:
            (direction: 'up'/'down' or None, confidence: 0-1)
        """
        
        signals = {}
        confidences = {}
        
        # 1. ML MODEL SIGNAL (primary - 50% weight)
        if ml_prediction:
            ml_signal = self._process_ml_signal(ml_prediction)
            if ml_signal:
                signals['ml'] = ml_signal['direction']
                confidences['ml'] = ml_signal['confidence']
        
        # 2. PATTERN RECOGNITION SIGNAL (secondary - 30% weight)
        if patterns:
            pattern_signal = self._process_pattern_signal(patterns)
            if pattern_signal:
                signals['pattern'] = pattern_signal['direction']
                confidences['pattern'] = pattern_signal['confidence']
        
        # 3. TECHNICAL INDICATORS SIGNAL (tertiary - 20% weight)
        if indicators:
            indicator_signal = self._process_indicator_signal(indicators, market_state)
            if indicator_signal:
                signals['indicator'] = indicator_signal['direction']
                confidences['indicator'] = indicator_signal['confidence']
        
        # Ensure market health is acceptable
        if market_health < 50:
            agent_logger.log_warning(f"Market health too low: {market_health}")
            return None, 0.0
        
        # Ensemble decision
        if not signals:
            return None, 0.0
        
        # Calculate ensemble confidence
        ensemble_confidence = self._calculate_ensemble_confidence(signals, confidences)
        
        # Determine direction (majority voting with confidence weighting)
        direction = self._determine_direction(signals, confidences)
        
        if direction and ensemble_confidence >= self.min_ensemble_confidence:
            agent_logger.log_info(
                f"Decision Engine: {direction.upper()} | "
                f"Confidence: {ensemble_confidence:.1%} | "
                f"Market Health: {market_health}/100 | "
                f"State: {market_state}"
            )
            return direction, ensemble_confidence
        
        return None, 0.0
    
    def _process_ml_signal(self, ml_prediction: Dict) -> Optional[Dict]:
        """Process ML model prediction into signal."""
        if not ml_prediction:
            return None
        
        direction = ml_prediction.get('direction')  # 'up', 'down', or None
        confidence = ml_prediction.get('confidence', 0.0)
        
        if direction and confidence >= 0.55:  # ML threshold slightly lower than ensemble
            return {
                'direction': direction,
                'confidence': min(confidence, 0.95)  # Cap at 95%
            }
        
        return None
    
    def _process_pattern_signal(self, patterns: Dict) -> Optional[Dict]:
        """Process chart patterns into signal."""
        if not patterns or not patterns.get('patterns'):
            return None
        
        detected_patterns = patterns['patterns']
        
        # Score patterns
        bullish_score = 0.0
        bearish_score = 0.0
        pattern_count = 0
        
        for pattern_name, pattern_data in detected_patterns.items():
            if not pattern_data:
                continue
            
            pattern_type = pattern_data.get('type')
            confidence = pattern_data.get('confidence', 0.5)
            pattern_count += 1
            
            # Map patterns to direction
            if pattern_type in ['bullish', 'upside_breakout', 'bullish_continuation']:
                bullish_score += confidence
            elif pattern_type in ['bearish', 'downside_breakout', 'bearish_continuation']:
                bearish_score += confidence
            else:
                # Neutral patterns add to confidence but don't bias
                pass
        
        if pattern_count == 0:
            return None
        
        # Normalize scores
        total_score = bullish_score + bearish_score
        
        if total_score > 0:
            bullish_ratio = bullish_score / total_score
            
            # Only signal if clear bias
            if bullish_ratio >= 0.6:
                confidence = min(bullish_ratio, 0.85)
                return {'direction': 'up', 'confidence': confidence}
            elif bullish_ratio <= 0.4:
                confidence = min((1 - bullish_ratio), 0.85)
                return {'direction': 'down', 'confidence': confidence}
        
        return None
    
    def _process_indicator_signal(self, indicators: Dict, market_state: str) -> Optional[Dict]:
        """Process technical indicators into signal."""
        if not indicators:
            return None
        
        rsi = indicators.get('rsi', 50)
        macd_histogram = indicators.get('macd_histogram', 0)
        momentum = indicators.get('momentum', 0)
        bb_position = indicators.get('bb_position', 0.5)  # 0=lower band, 1=upper band
        
        signal_strength = 0.0
        direction = None
        
        # RSI signals
        if rsi < 30:  # Oversold - potential reversal up
            signal_strength += 0.2
            direction = 'up'
        elif rsi > 70:  # Overbought - potential reversal down
            signal_strength += 0.2
            direction = 'down'
        
        # MACD signals
        if macd_histogram > 0:
            signal_strength += 0.15
            if direction is None:
                direction = 'up'
        elif macd_histogram < 0:
            signal_strength += 0.15
            if direction is None:
                direction = 'down'
        
        # Momentum signals
        if momentum > 0:
            signal_strength += 0.15
            if direction is None:
                direction = 'up'
        elif momentum < 0:
            signal_strength += 0.15
            if direction is None:
                direction = 'down'
        
        # Bollinger Bands signals
        if bb_position < 0.2:  # Near lower band
            signal_strength += 0.1
            if direction is None:
                direction = 'up'
        elif bb_position > 0.8:  # Near upper band
            signal_strength += 0.1
            if direction is None:
                direction = 'down'
        
        # Adjust confidence based on market state
        state_multiplier = {
            'trending_up': 1.2 if direction == 'up' else 0.8,
            'trending_down': 1.2 if direction == 'down' else 0.8,
            'ranging': 0.9,
            'volatile': 0.85,
            'calm': 1.1,
            'unknown': 1.0
        }.get(market_state, 1.0)
        
        confidence = min(signal_strength * state_multiplier, 0.85)
        
        if direction and confidence >= 0.5:
            return {'direction': direction, 'confidence': confidence}
        
        return None
    
    def _calculate_ensemble_confidence(self, signals: Dict, confidences: Dict) -> float:
        """Calculate weighted ensemble confidence."""
        if not signals:
            return 0.0
        
        weighted_confidence = 0.0
        total_weight = 0.0
        
        # Weight each signal
        for signal_type, weight in [
            ('ml', self.ml_weight),
            ('pattern', self.pattern_weight),
            ('indicator', self.indicator_weight)
        ]:
            if signal_type in signals and signal_type in confidences:
                weighted_confidence += confidences[signal_type] * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        ensemble_conf = weighted_confidence / total_weight
        
        # Boost if all signals agree
        if len(signals) >= 2:
            directions = set(signals.values())
            if len(directions) == 1:  # All signals agree
                ensemble_conf = min(ensemble_conf * 1.15, 1.0)  # Boost by 15%
        
        return ensemble_conf
    
    def _determine_direction(self, signals: Dict, confidences: Dict) -> Optional[str]:
        """Determine final direction via weighted voting."""
        if not signals:
            return None
        
        # Weight votes
        up_votes = 0.0
        down_votes = 0.0
        
        weights = {
            'ml': self.ml_weight,
            'pattern': self.pattern_weight,
            'indicator': self.indicator_weight
        }
        
        for signal_type, direction in signals.items():
            weight = weights.get(signal_type, 1.0)
            confidence = confidences.get(signal_type, 0.5)
            
            weighted_vote = weight * confidence
            
            if direction == 'up':
                up_votes += weighted_vote
            elif direction == 'down':
                down_votes += weighted_vote
        
        if up_votes > down_votes:
            return 'up'
        elif down_votes > up_votes:
            return 'down'
        
        return None


class RiskAdjustedDecision:
    """
    Wraps decision engine with risk management adjustments.
    """
    
    def __init__(self, decision_engine: DecisionEngine, risk_manager):
        self.engine = decision_engine
        self.risk_manager = risk_manager
    
    def get_trade_signal(
        self,
        ml_prediction,
        patterns,
        indicators,
        market_state,
        market_health,
        current_winning_streak: int = 0,
        recent_win_rate: float = 0.5
    ) -> Tuple[Optional[str], float]:
        """
        Get trade signal with risk adjustments.
        Reduces confidence after losses, boosts after wins.
        """
        
        direction, confidence = self.engine.make_decision(
            ml_prediction, patterns, indicators, market_state, market_health
        )
        
        if direction is None:
            return None, 0.0
        
        # Risk adjustments
        
        # After consecutive losses, reduce confidence
        if self.risk_manager.consecutive_losses > 0:
            loss_penalty = 0.1 * self.risk_manager.consecutive_losses
            confidence = max(confidence - loss_penalty, 0.0)
            agent_logger.log_info(
                f"Confidence adjusted for consecutive losses ({self.risk_manager.consecutive_losses}): "
                f"{confidence:.1%}"
            )
        
        # After winning streak, slightly boost confidence
        if current_winning_streak > 1:
            win_boost = 0.05 * min(current_winning_streak, 3)
            confidence = min(confidence + win_boost, 0.95)
        
        # If win rate is poor, reduce confidence
        if recent_win_rate < 0.45:
            confidence = confidence * 0.85
        
        return direction, confidence
