"""
Unified decision engine that combines ML predictions + pattern recognition + technical indicators.
Uses ensemble approach for robust trade signals.
Prioritizes multi-timeframe trend analysis as the primary signal source.
"""

from typing import Dict, Tuple, Optional
import numpy as np
from logger import agent_logger
from config import MIN_CONFIDENCE


class DecisionEngine:
    """
    Intelligent decision engine combining:
    1. Multi-timeframe trend analysis (PRIMARY - highest weight)
    2. ML model predictions (secondary)
    3. Chart pattern recognition (tertiary)
    4. Technical indicators (quaternary)
    
    Decision flow:
    1. Check higher timeframe trend FIRST - defines the bias
    2. Check medium timeframe for confirmation
    3. Only enter trades when higher AND medium timeframes agree
    4. Use lower timeframe for entry timing
    """
    
    def __init__(self):
        self.ml_weight = 0.20        # ML model confidence weight
        self.trend_weight = 0.40     # Multi-timeframe trend weight (HIGHEST - primary)
        self.pattern_weight = 0.25   # Pattern recognition weight (including candle)
        self.indicator_weight = 0.15 # Technical indicators weight
        
        # Thresholds for confidence
        self.min_ensemble_confidence = MIN_CONFIDENCE
        
    def make_decision(
        self,
        ml_prediction: Optional[Dict],
        patterns: Optional[Dict],
        indicators: Optional[Dict],
        market_state: str,
        market_health: float,
        multi_tf_trend: Optional[Dict] = None
    ) -> Tuple[Optional[str], float]:
        """
        Make trading decision using ensemble of signals.
        
        KEY RULES:
        - Multi-timeframe trend is PRIMARY - only trade if higher+medium agree
        - In trending markets, all signals get a boost
        - In ranging markets, require strong candle pattern or breakout signal
        - Never trade against the higher timeframe trend
        
        Returns:
            (direction: 'up'/'down' or None, confidence: 0-1)
        """
        
        signals = {}
        confidences = {}
        
        # 1. MULTI-TIMEFRAME TREND SIGNAL (PRIMARY - 40% weight)
        if multi_tf_trend and multi_tf_trend.get('is_trending'):
            tf_signal = self._process_trend_signal(multi_tf_trend)
            if tf_signal:
                signals['trend'] = tf_signal['direction']
                confidences['trend'] = tf_signal['confidence']
                agent_logger.log_info(
                    f"📊 Multi-TF Trend: {tf_signal['direction'].upper()} "
                    f"(strength={tf_signal['confidence']:.2f}, "
                    f"all_aligned={tf_signal.get('all_aligned', False)})"
                )
        
        # 2. ML MODEL SIGNAL (secondary - 20% weight)
        if ml_prediction:
            ml_signal = self._process_ml_signal(ml_prediction)
            if ml_signal:
                signals['ml'] = ml_signal['direction']
                confidences['ml'] = ml_signal['confidence']
        
        # 3. PATTERN RECOGNITION SIGNAL (tertiary - 25% weight)
        if patterns:
            pattern_signal = self._process_pattern_signal(patterns)
            if pattern_signal:
                signals['pattern'] = pattern_signal['direction']
                confidences['pattern'] = pattern_signal['confidence']
        
        # 4. TECHNICAL INDICATORS SIGNAL (quaternary - 15% weight)
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
        
        # === TREND-BASED GUARD ===
        # If we have a multi-timeframe trend signal, it defines the bias.
        # All other signals must agree with the trend direction.
        has_trend_signal = 'trend' in signals
        trend_direction = signals.get('trend')
        
        if has_trend_signal:
            # Check if other signals conflict with the trend
            conflicting_signals = []
            agreeing_signals = []
            
            for sig_type in ['ml', 'pattern', 'indicator']:
                if sig_type in signals:
                    if signals[sig_type] == trend_direction:
                        agreeing_signals.append(sig_type)
                    else:
                        conflicting_signals.append(sig_type)
            
            if conflicting_signals and not agreeing_signals:
                # ALL other signals conflict with trend - this is suspicious
                agent_logger.log_warning(
                    f"⚠️ Trend ({trend_direction}) conflicts with ALL other signals "
                    f"({', '.join(conflicting_signals)}). Reducing confidence."
                )
                # Still allow trade if trend is very strong, but with penalty
                trend_conf = confidences.get('trend', 0.5)
                if trend_conf < 0.7:
                    return None, 0.0
            elif conflicting_signals:
                agent_logger.log_info(
                    f"⚡ Trend ({trend_direction}) agreed by {len(agreeing_signals)} signals, "
                    f"disagreed by {len(conflicting_signals)}"
                )
        
        # === SINGLE SOURCE GUARD ===
        single_source = len(signals) == 1
        is_trending = 'trending' in market_state
        
        if single_source:
            if is_trending:
                agent_logger.log_info(
                    f"⚡ Single-source signal ({list(signals.keys())[0]}) "
                    f"in {market_state} market — allowing (trending market)"
                )
            else:
                agent_logger.log_info(
                    f"⚡ Single-source signal ({list(signals.keys())[0]}) "
                    f"in {market_state} market — allowing with reduced confidence"
                )
        
        # Calculate ensemble confidence
        ensemble_confidence = self._calculate_ensemble_confidence(signals, confidences, multi_tf_trend)
        
        # Determine direction (majority voting with confidence weighting)
        direction = self._determine_direction(signals, confidences)
        
        if direction and ensemble_confidence >= self.min_ensemble_confidence:
            # Log detailed breakdown
            signal_summary = []
            for sig_type in ['trend', 'ml', 'pattern', 'indicator']:
                if sig_type in signals:
                    sig_dir = signals[sig_type].upper()
                    sig_conf = confidences[sig_type]
                    signal_summary.append(f"{sig_type}={sig_dir}@{sig_conf:.2f}")
            
            agent_logger.log_info(
                f"Decision Engine: {direction.upper()} | "
                f"Confidence: {ensemble_confidence:.1%} | "
                f"Market Health: {market_health}/100 | "
                f"State: {market_state} | "
                f"Signals: [{', '.join(signal_summary)}]"
            )
            return direction, ensemble_confidence
        
        return None, 0.0
    
    def _process_trend_signal(self, multi_tf_trend: Dict) -> Optional[Dict]:
        """
        Process multi-timeframe trend analysis into a signal.
        The TREND is the PRIMARY signal - highest confidence.
        """
        primary_direction = multi_tf_trend.get('primary_direction')
        strength = multi_tf_trend.get('strength', 0.0)
        all_aligned = multi_tf_trend.get('all_timeframes_align', False)
        higher_medium_agree = multi_tf_trend.get('higher_medium_agree', False)
        
        if not higher_medium_agree or primary_direction not in ('up', 'down'):
            return None
        
        if primary_direction == 'up':
            direction = 'up'
        elif primary_direction == 'down':
            direction = 'down'
        else:
            return None
        
        # Base confidence on trend strength + alignment bonus
        base_confidence = strength
        if all_aligned:
            base_confidence = min(base_confidence * 1.3, 0.95)  # All timeframes aligned = very strong
        
        confidence = min(max(base_confidence, 0.5), 0.95)
        
        return {
            'direction': direction,
            'confidence': confidence,
            'all_aligned': all_aligned,
            'higher_medium_agree': higher_medium_agree
        }
    
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
        """
        Process chart patterns into signal.
        Prioritizes candlestick patterns and multi-timeframe trend patterns
        over traditional chart patterns.
        """
        if not patterns or not patterns.get('patterns'):
            return None
        
        detected_patterns = patterns['patterns']
        
        # Check for special high-confidence patterns first
        candle_patterns = ['bullish_engulfing', 'bearish_engulfing', 'hammer', 
                          'shooting_star', 'three_white_soldiers', 'three_black_crows']
        
        # Score patterns
        bullish_score = 0.0
        bearish_score = 0.0
        pattern_count = 0
        
        for pattern_name, pattern_data in detected_patterns.items():
            if not pattern_data:
                continue
            
            pattern_type = pattern_data.get('type') or pattern_data.get('signal', '')
            confidence = pattern_data.get('confidence', 0.5)
            pattern_count += 1
            
            # Map patterns to direction
            if pattern_type in ['bullish', 'upside_breakout', 'bullish_continuation',
                                'bullish_reversal'] or 'bullish' in str(pattern_type):
                bullish_score += confidence
            elif pattern_type in ['bearish', 'downside_breakout', 'bearish_continuation',
                                  'bearish_reversal'] or 'bearish' in str(pattern_type):
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
        """Process technical indicators into signal with proper signal weighting."""
        if not indicators:
            return None
        
        rsi = indicators.get('rsi', 50)
        macd_histogram = indicators.get('macd_histogram', 0)
        momentum = indicators.get('momentum', 0)
        bb_position = indicators.get('bb_position', 0.5)  # 0=lower band, 1=upper band
        
        # Use weighted voting system instead of signal_strength
        up_score = 0.0
        down_score = 0.0
        
        # RSI signals (REVERSAL indicator - extremes suggest opposite direction)
        if rsi < 30:  # Oversold - expect bounce UP
            up_score += 0.25
        elif rsi > 70:  # Overbought - expect reversal DOWN
            down_score += 0.25
        elif rsi < 40:  # Moderately oversold
            up_score += 0.1
        elif rsi > 60:  # Moderately overbought
            down_score += 0.1
        
        # MACD signals (TREND indicator - follows momentum)
        if macd_histogram > 0.0001:  # Positive momentum
            up_score += 0.2
        elif macd_histogram < -0.0001:  # Negative momentum
            down_score += 0.2
        
        # Momentum signals (TREND indicator)
        if momentum > 0.0001:
            up_score += 0.15
        elif momentum < -0.0001:
            down_score += 0.15
        
        # Bollinger Bands signals (REVERSAL indicator - extremes suggest opposite)
        if bb_position < 0.2:  # Near lower band - expect bounce UP
            up_score += 0.15
        elif bb_position > 0.8:  # Near upper band - expect reversal DOWN
            down_score += 0.15
        
        # Determine direction and confidence
        total_score = up_score + down_score
        
        if total_score < 0.3:  # Not enough signal strength
            return None
        
        if up_score > down_score:
            direction = 'up'
            confidence = up_score / (up_score + down_score)  # Normalize to 0-1
        elif down_score > up_score:
            direction = 'down'
            confidence = down_score / (up_score + down_score)
        else:
            return None  # Tied - no clear signal
        
        # Adjust confidence based on market state
        state_multiplier = {
            'trending_up': 1.15 if direction == 'up' else 0.85,
            'trending_down': 1.15 if direction == 'down' else 0.85,
            'ranging': 0.95,  # Slightly reduce in ranging markets
            'volatile': 0.8,   # Reduce significantly in volatile markets
            'calm': 1.1,
            'unknown': 0.9
        }.get(market_state, 1.0)
        
        confidence = min(confidence * state_multiplier, 0.85)
        
        # Only return signal if confidence is reasonable
        if confidence >= 0.5:
            return {'direction': direction, 'confidence': confidence}
        
        return None
    
    def _calculate_ensemble_confidence(self, signals: Dict, confidences: Dict, multi_tf_trend: Optional[Dict] = None) -> float:
        """Calculate weighted ensemble confidence with dynamic adjustments."""
        if not signals:
            return 0.0
        
        weighted_confidence = 0.0
        total_weight = 0.0
        
        # Weight each signal (trend gets highest weight)
        for signal_type, weight in [
            ('trend', self.trend_weight),
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
        
        # Check agreement/disagreement
        directions = list(signals.values())
        up_count = directions.count('up')
        down_count = directions.count('down')
        total_signals = len(directions)
        
        if total_signals >= 2:
            if up_count == total_signals or down_count == total_signals:
                # Perfect agreement - boost confidence
                ensemble_conf = min(ensemble_conf * 1.2, 0.98)
            elif total_signals >= 3 and (up_count >= 2 or down_count >= 2):
                # Majority agreement - slight boost
                ensemble_conf = min(ensemble_conf * 1.05, 0.95)
            else:
                # Disagreement - reduce confidence
                ensemble_conf = ensemble_conf * 0.7
        
        # Penalize if only one signal source (less reliable)
        if total_signals == 1:
            ensemble_conf = ensemble_conf * 0.85
        
        # Trend alignment bonus
        if multi_tf_trend and multi_tf_trend.get('all_timeframes_align'):
            ensemble_conf = min(ensemble_conf * 1.15, 0.98)
        elif multi_tf_trend and multi_tf_trend.get('higher_medium_agree'):
            ensemble_conf = min(ensemble_conf * 1.05, 0.95)
        
        return ensemble_conf
    
    def _determine_direction(self, signals: Dict, confidences: Dict) -> Optional[str]:
        """Determine final direction via weighted voting."""
        if not signals:
            return None
        
        # Weight votes
        up_votes = 0.0
        down_votes = 0.0
        
        weights = {
            'trend': self.trend_weight,
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
        multi_tf_trend: Optional[Dict] = None,
        current_winning_streak: int = 0,
        recent_win_rate: float = 0.5
    ) -> Tuple[Optional[str], float]:
        """
        Get trade signal with risk adjustments.
        Reduces confidence after losses, boosts after wins.
        """
        
        direction, confidence = self.engine.make_decision(
            ml_prediction, patterns, indicators, market_state, market_health, multi_tf_trend
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