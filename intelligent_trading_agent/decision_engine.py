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
    
    KEY IMPROVEMENTS to reduce losses:
    - Requires CONFIRMED trend before trading (no trend = no trade)
    - In ranging markets, confidence must be ULTRA_HIGH or don't trade
    - ML threshold raised to 0.65 to filter noise
    - Trend disagreement is a hard block, not just a penalty
    """
    
    def __init__(self):
        self.ml_weight = 0.20        # ML model confidence weight (reduced - less reliable)
        self.trend_weight = 0.30     # Multi-timeframe trend weight (primary signal)
        self.pattern_weight = 0.20   # Pattern recognition weight (chart patterns)
        self.candle_dir_weight = 0.20 # NEW: Candle direction analysis weight (consecutive candles, wicks, velocity)
        self.indicator_weight = 0.10 # Technical indicators weight (supporting only)
        
        # Thresholds for confidence
        self.min_ensemble_confidence = MIN_CONFIDENCE
        
        # ENHANCED: Sure trend detection
        # When multi-timeframe trend confidence is high, we can trade with less indicator confirmation
        self.sure_trend_confidence_threshold = 80  # trend_confidence_score >= 80 = sure trend
        self.sure_trend_min_confidence = 0.70      # Lower confidence threshold for sure trends
        
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
        
        ENHANCED: Patterns and trend are now PRIMARY over indicators.
        KEY RULES:
        - Multi-timeframe trend is PRIMARY - only trade if higher+medium agree
        - Chart patterns are SECONDARY - strong patterns can override weak indicators
        - In ranging markets, trading is STRONGLY DISFAVORED (only ultra-high confidence)
        - Never trade against the higher timeframe trend
        - ML predictions alone are NOT sufficient without trend confirmation
        - "SURE TREND" detection: when trend_confidence_score >= 80, trade with lower thresholds
        
        Returns:
            (direction: 'up'/'down' or None, confidence: 0-1)
        """
        
        signals = {}
        confidences = {}
        
        # Check for "SURE TREND" - when multi-timeframe trend confidence is very high
        is_sure_trend = False
        if multi_tf_trend:
            is_sure_trend = multi_tf_trend.get('is_sure_trend', False)
            trend_confidence = multi_tf_trend.get('trend_confidence_score', 0)
            if is_sure_trend:
                agent_logger.log_info(
                    f"🎯 SURE TREND DETECTED! Confidence score: {trend_confidence}/100, "
                    f"Persistence: {multi_tf_trend.get('trend_persistence', 0)} ticks"
                )
        
        # 1. MULTI-TIMEFRAME TREND SIGNAL (PRIMARY - highest weight)
        if multi_tf_trend and multi_tf_trend.get('is_trending'):
            tf_signal = self._process_trend_signal(multi_tf_trend)
            if tf_signal:
                signals['trend'] = tf_signal['direction']
                confidences['trend'] = tf_signal['confidence']
                agent_logger.log_info(
                    f"📊 Multi-TF Trend: {tf_signal['direction'].upper()} "
                    f"(strength={tf_signal['confidence']:.2f}, "
                    f"all_aligned={tf_signal.get('all_aligned', False)}, "
                    f"sure_trend={is_sure_trend})"
                )
        
        # 2. CANDLE DIRECTION SIGNAL (NEW - real-time candle analysis)
        # Analyzes consecutive candle directions, wicks, body momentum, and velocity
        # This is a fast, real-time signal that captures immediate market direction
        if patterns and 'candle_direction' in patterns.get('patterns', {}):
            candle_dir = patterns['patterns']['candle_direction']
            candle_signal = self._process_candle_direction_signal(candle_dir)
            if candle_signal:
                signals['candle_dir'] = candle_signal['direction']
                confidences['candle_dir'] = candle_signal['confidence']
                agent_logger.log_info(
                    f"🕯️ Candle Direction: {candle_signal['direction'].upper()} "
                    f"(conf={candle_signal['confidence']:.2f}, "
                    f"streak={candle_dir.get('streak', 0)}, "
                    f"velocity={candle_dir.get('candle_velocity', 0):.2f})"
                )
        
        # 3. PATTERN RECOGNITION SIGNAL (tertiary priority)
        # Patterns are more reliable than indicators for synthetic indices
        if patterns:
            pattern_signal = self._process_pattern_signal(patterns)
            if pattern_signal:
                signals['pattern'] = pattern_signal['direction']
                confidences['pattern'] = pattern_signal['confidence']
        
        # 4. ML MODEL SIGNAL (quaternary - reduced weight)
        if ml_prediction:
            ml_signal = self._process_ml_signal(ml_prediction)
            if ml_signal:
                signals['ml'] = ml_signal['direction']
                confidences['ml'] = ml_signal['confidence']
        
        # 5. TECHNICAL INDICATORS SIGNAL (quinary - supporting only)
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
        
        # === SURE TREND OVERRIDE ===
        # When a "sure trend" is detected, we can trade with less confirmation
        # because the multi-timeframe alignment is very strong
        if is_sure_trend and 'trend' in signals:
            # For sure trends, we only need the trend signal + at least one other signal
            if len(signals) >= 2:
                trend_dir = signals['trend']
                # Check if at least one other signal agrees with the trend
                other_agree = any(
                    signals.get(s) == trend_dir 
                    for s in ['candle_dir', 'pattern', 'ml', 'indicator'] 
                    if s in signals
                )
                if other_agree:
                    agent_logger.log_info(
                        f"🎯 SURE TREND CONFIRMED: {trend_dir.upper()} with "
                        f"{len(signals)} signal sources. Trading with confidence."
                    )
                    # Use the trend direction with boosted confidence
                    ensemble_confidence = max(
                        confidences.get('trend', 0.7),
                        self.sure_trend_min_confidence
                    )
                    return trend_dir, min(ensemble_confidence * 1.1, 0.95)
        
        # === RANGING MARKET GUARD ===
        # In ranging markets, trading is very risky (40.3% win rate observed).
        # Only trade in ranging if confidence is ULTRA_HIGH and we have
        # agreement from at least 2 signal sources.
        is_ranging = 'ranging' in market_state
        if is_ranging:
            # In ranging, require at least 2 signal sources AND high confidence
            if len(signals) < 2:
                agent_logger.log_info(
                    f"⚠️ Ranging market: only {len(signals)} signal source(s). "
                    f"Requiring 2+ sources in ranging. No trade."
                )
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
            
            for sig_type in ['candle_dir', 'pattern', 'ml', 'indicator']:
                if sig_type in signals:
                    if signals[sig_type] == trend_direction:
                        agreeing_signals.append(sig_type)
                    else:
                        conflicting_signals.append(sig_type)
            
            if conflicting_signals and not agreeing_signals:
                # ALL other signals conflict with trend - this is suspicious
                agent_logger.log_warning(
                    f"⚠️ Trend ({trend_direction}) conflicts with ALL other signals "
                    f"({', '.join(conflicting_signals)}). Blocking trade."
                )
                return None, 0.0  # HARD BLOCK - don't trade against clear trend
            
            # ENHANCED: If ANY signal conflicts with the multi-tf trend, block the trade.
            # Synthetic indices are momentum-driven: the multi-timeframe trend is the
            # most reliable signal. Even one conflicting signal is enough to skip.
            if conflicting_signals:
                agent_logger.log_warning(
                    f"⚠️ Trend ({trend_direction}) conflicts with {', '.join(conflicting_signals)}. "
                    f"Blocking trade — multi-tf trend is the primary signal."
                )
                return None, 0.0
        
        # === MARKET STATE TREND GUARD ===
        # Even without a multi-tf trend signal, the market state tells us the direction.
        # NEVER trade against the market state's trend direction.
        # For synthetic indices (R_10..R_100), momentum persists — trading against
        # the prevailing trend is a guaranteed loss.
        if 'trending_up' in market_state:
            # Check if any signal wants to go DOWN
            for sig_type, sig_dir in signals.items():
                if sig_dir == 'down':
                    agent_logger.log_warning(
                        f"⚠️ Market state is {market_state} but {sig_type} wants DOWN. "
                        f"Blocking — never trade against the market trend."
                    )
                    return None, 0.0
        elif 'trending_down' in market_state:
            # Check if any signal wants to go UP
            for sig_type, sig_dir in signals.items():
                if sig_dir == 'up':
                    agent_logger.log_warning(
                        f"⚠️ Market state is {market_state} but {sig_type} wants UP. "
                        f"Blocking — never trade against the market trend."
                    )
                    return None, 0.0
        
        # === SIGNAL AGREEMENT CHECK ===
        up_count = sum(1 for d in signals.values() if d == 'up')
        down_count = sum(1 for d in signals.values() if d == 'down')
        total_signals = len(signals)
        
        # If there's disagreement with no clear majority, don't trade
        if total_signals >= 3:
            if up_count == down_count:
                agent_logger.log_warning(
                    f"⚠️ Split decision: {up_count} up vs {down_count} down. "
                    f"Not trading without majority signal."
                )
                return None, 0.0
        
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
                    f"in {market_state} market — blocking (non-trending market)"
                )
                return None, 0.0  # HARD BLOCK in non-trending with single source
        
        # === NO TREND GUARD ===
        # If neither trend nor candle_dir signals are present, the bot only has
        # pattern + indicator signals. These are weaker signals that have produced
        # false signals in the past. Require either:
        # - At least one trend-based signal (trend or candle_dir) present, OR
        # - Higher confidence if only pattern+indicator agree
        has_trend_signal = 'trend' in signals
        has_candle_dir_signal = 'candle_dir' in signals
        if not has_trend_signal and not has_candle_dir_signal:
            agent_logger.log_info(
                f"⚠️ No trend signal present — only pattern/ML/indicator signals ({list(signals.keys())}). "
                f"Requiring higher confidence threshold."
            )
            # Raise effective min confidence since we lack trend validation
            no_trend_penalty = 0.08  # +8% confidence required
            self._no_trend_penalty_active = True
        else:
            self._no_trend_penalty_active = False
        
        # Calculate ensemble confidence
        ensemble_confidence = self._calculate_ensemble_confidence(signals, confidences, multi_tf_trend)
        
        # Determine direction (majority voting with confidence weighting)
        direction = self._determine_direction(signals, confidences)
        
        # Apply no-trend penalty (raise effective min confidence)
        effective_min_confidence = self.min_ensemble_confidence
        if hasattr(self, '_no_trend_penalty_active') and self._no_trend_penalty_active:
            effective_min_confidence += 0.08
            agent_logger.log_info(
                f"⚠️ No trend guard: raised min confidence from {self.min_ensemble_confidence:.2f} "
                f"to {effective_min_confidence:.2f} (no trend/candle_dir signal present)"
            )
        
        if direction and ensemble_confidence >= effective_min_confidence:
            # Log detailed breakdown
            signal_summary = []
            for sig_type in ['trend', 'candle_dir', 'pattern', 'ml', 'indicator']:
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
    
    def _process_candle_direction_signal(self, candle_dir: Dict) -> Optional[Dict]:
        """
        Process candle direction analysis into a signal.
        
        This analyzes:
        - Consecutive same-direction candles (streak)
        - Candle body momentum (accelerating/decelerating bodies)
        - Wick analysis (rejection at support/resistance)
        - Candle velocity (net direction over last N candles)
        
        For synthetic indices (R_10..R_100), consecutive candles in the
        same direction are a strong indicator of continued momentum.
        """
        direction = candle_dir.get('direction')
        confidence = candle_dir.get('confidence', 0.0)
        streak = candle_dir.get('streak', 0)
        body_momentum = candle_dir.get('body_momentum', 'stable')
        wick_signal = candle_dir.get('wick_signal', 'neutral')
        velocity = candle_dir.get('candle_velocity', 0.0)
        
        if direction not in ('up', 'down'):
            return None
        
        # Adjust confidence based on additional factors
        adjusted_confidence = confidence
        
        # Boost if body momentum is accelerating (trend gaining strength)
        if body_momentum == 'accelerating' and streak >= 2:
            adjusted_confidence = min(adjusted_confidence + 0.10, 0.90)
        
        # Reduce if body momentum is decelerating (trend losing steam)
        if body_momentum == 'decelerating' and streak >= 3:
            adjusted_confidence = max(adjusted_confidence - 0.15, 0.0)
        
        # Boost if wick signal confirms direction
        if direction == 'up' and wick_signal == 'rejection_down':
            adjusted_confidence = min(adjusted_confidence + 0.10, 0.90)
        if direction == 'down' and wick_signal == 'rejection_up':
            adjusted_confidence = min(adjusted_confidence + 0.10, 0.90)
        
        # Reduce if wick signal contradicts direction (potential reversal)
        if direction == 'up' and wick_signal == 'rejection_up':
            adjusted_confidence = max(adjusted_confidence - 0.10, 0.0)
        if direction == 'down' and wick_signal == 'rejection_down':
            adjusted_confidence = max(adjusted_confidence - 0.10, 0.0)
        
        # Strong velocity confirms direction
        if abs(velocity) > 0.5 and streak >= 2:
            adjusted_confidence = min(adjusted_confidence + 0.05, 0.90)
        
        if adjusted_confidence >= 0.40:
            return {
                'direction': direction,
                'confidence': min(adjusted_confidence, 0.90)
            }
        
        return None
    
    def _process_ml_signal(self, ml_prediction: Dict) -> Optional[Dict]:
        """Process ML model prediction into signal.
        RAISED threshold from 0.55 to 0.65 to filter noisy predictions."""
        if not ml_prediction:
            return None
        
        direction = ml_prediction.get('direction')  # 'up', 'down', or None
        confidence = ml_prediction.get('confidence', 0.0)
        
        if direction and confidence >= 0.65:  # RAISED: was 0.55, now 0.65
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
        """
        Process technical indicators into signal.
        
        CRITICAL: Synthetic indices (R_10..R_100) are MOMENTUM-DRIVEN, not mean-reverting.
        Unlike forex/stocks, high RSI means momentum will CONTINUE higher, not reverse.
        Low RSI means momentum will CONTINUE lower.
        
        Therefore:
        - RSI > 60 = strong momentum UP → signal UP (NOT reversal DOWN)
        - RSI < 40 = strong momentum DOWN → signal DOWN (NOT reversal UP)
        - MACD histogram = trend direction
        - Momentum = trend direction
        - Bollinger Bands = volatility measure, not reversal signal
        """
        if not indicators:
            return None
        
        rsi = indicators.get('rsi', 50)
        macd_histogram = indicators.get('macd_histogram', 0)
        momentum = indicators.get('momentum', 0)
        bb_position = indicators.get('bb_position', 0.5)  # 0=lower band, 1=upper band
        
        # Use weighted voting system
        up_score = 0.0
        down_score = 0.0
        
        # RSI signals (MOMENTUM indicator for synthetic indices)
        # High RSI = strong upward momentum → continue UP
        # Low RSI = strong downward momentum → continue DOWN
        if rsi > 60:  # Strong upward momentum
            up_score += 0.30
        elif rsi < 40:  # Strong downward momentum
            down_score += 0.30
        elif rsi > 55:  # Moderate upward momentum
            up_score += 0.15
        elif rsi < 45:  # Moderate downward momentum
            down_score += 0.15
        
        # MACD signals (TREND indicator - follows momentum)
        if macd_histogram > 0.0001:  # Positive momentum
            up_score += 0.25
        elif macd_histogram < -0.0001:  # Negative momentum
            down_score += 0.25
        
        # Momentum signals (TREND indicator)
        if momentum > 0.0001:
            up_score += 0.20
        elif momentum < -0.0001:
            down_score += 0.20
        
        # Bollinger Bands (VOLATILITY indicator - not reversal for synthetic indices)
        # Near bands with strong momentum = trend continuation
        if bb_position > 0.8 and rsi > 55:
            up_score += 0.10  # Price at upper band + strong RSI = momentum UP
        elif bb_position < 0.2 and rsi < 45:
            down_score += 0.10  # Price at lower band + weak RSI = momentum DOWN
        
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
            'trending_up': 1.20 if direction == 'up' else 0.70,
            'trending_down': 1.20 if direction == 'down' else 0.70,
            'ranging': 0.90,  # Reduce in ranging markets
            'volatile': 0.85,  # Reduce in volatile markets
            'calm': 1.10,
            'unknown': 0.85
        }.get(market_state, 1.0)
        
        confidence = min(confidence * state_multiplier, 0.85)
        
        # Only return signal if confidence is reasonable
        if confidence >= 0.55:  # RAISED: was 0.50, now 0.55
            return {'direction': direction, 'confidence': confidence}
        
        return None
    
    def _calculate_ensemble_confidence(self, signals: Dict, confidences: Dict, multi_tf_trend: Optional[Dict] = None) -> float:
        """Calculate weighted ensemble confidence with dynamic adjustments.
        
        ENHANCED: 
        - Pattern weight increased, ML weight decreased
        - Sure trend bonus: +20% confidence when trend_confidence_score >= 80
        - Pattern confirmation bonus: +10% when patterns confirm trend
        """
        if not signals:
            return 0.0
        
        weighted_confidence = 0.0
        total_weight = 0.0
        
        # Weight each signal (trend gets highest weight, then candle_dir, patterns, ml, indicators)
        for signal_type, weight in [
            ('trend', self.trend_weight),
            ('candle_dir', self.candle_dir_weight),
            ('pattern', self.pattern_weight),
            ('ml', self.ml_weight),
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
        
        # ENHANCED: Sure trend bonus
        if multi_tf_trend and multi_tf_trend.get('is_sure_trend', False):
            trend_confidence = multi_tf_trend.get('trend_confidence_score', 0)
            sure_bonus = 0.10 + (trend_confidence - 80) / 200  # 10-20% bonus
            ensemble_conf = min(ensemble_conf * (1 + sure_bonus), 0.98)
            agent_logger.log_info(
                f"🎯 Sure trend bonus: +{sure_bonus*100:.0f}% confidence "
                f"(trend_confidence={trend_confidence}/100)"
            )
        
        # ENHANCED: Pattern confirmation bonus
        if multi_tf_trend and 'trend' in signals and 'pattern' in signals:
            if signals['trend'] == signals['pattern']:
                # Pattern confirms trend - significant boost
                ensemble_conf = min(ensemble_conf * 1.12, 0.98)
                agent_logger.log_info(
                    f"📊 Pattern confirms trend: +12% confidence boost"
                )
        
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
            'candle_dir': self.candle_dir_weight,
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