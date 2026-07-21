"""
Market state analyzer - detects market conditions and assigns health scores.
Identifies: trending, ranging, volatile, calm markets.
"""

import numpy as np
from collections import deque
from typing import Dict, Tuple
from features.indicators import FeatureEngine
from logger import agent_logger


class MarketState:
    """Represents market conditions."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CALM = "calm"
    UNKNOWN = "unknown"


class MarketAnalyzer:
    """
    Analyze market conditions.
    Detects market regime and assigns health scores.
    """
    
    def __init__(self, window: int = 100):
        self.window = window
        self.feature_engine = FeatureEngine(window=window)
        self.price_history = deque(maxlen=window)
    
    def update(self, price: float, volume: float = 1.0):
        """Update analyzer with new price data."""
        self.feature_engine.add_price(price, volume)
        self.price_history.append(price)
    
    def detect_market_state(self) -> str:
        """
        Detect current market state tailored for synthetic indices (R_10..R_100).
        These are volatility-normalized indices with very different characteristics
        from forex/stocks — they oscillate rapidly and have persistent low-level momentum.
        
        Key improvements for synthetic indices:
        - Use price rate-of-change over fixed lookback (not raw momentum)
        - Require SUSTAINED directionality (price above/below both SMA-20 AND SMA-50)
        - Lower momentum thresholds since synthetic indices trend more subtly
        - Check ADX/trend_strength from features for confirmation
        - Stricter ranging detection (low momentum + price crossing SMA)
        Returns: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, CALM, or UNKNOWN
        """
        # Require at least 50 data points for reliable state detection
        if len(self.price_history) < 50:
            return MarketState.UNKNOWN
        
        try:
            # Check if feature engine has enough data
            if len(self.feature_engine.indicators.prices) < 30:
                agent_logger.log_warning(f"Feature engine has insufficient data: {len(self.feature_engine.indicators.prices)} prices")
                return MarketState.UNKNOWN
            
            # Extract key metrics
            volatility = self.feature_engine.indicators.volatility(20)
            momentum = self.feature_engine.indicators.momentum(20)
            sma_20 = self.feature_engine.indicators.sma(20)
            sma_50 = self.feature_engine.indicators.sma(50) if len(self.price_history) >= 50 else sma_20
            current_price = self.feature_engine.indicators.current_price()
            
            # Extract features for additional metrics
            features = self.feature_engine.extract_features()
            rsi = features.get('rsi', 50)
            bb_position = features.get('bb_position', 0.5)
            trend_strength = features.get('trend_strength', 0.0)
            
            # Validate we have valid data
            if current_price == 0 or sma_20 == 0:
                agent_logger.log_warning(f"Invalid price data: current={current_price}, sma_20={sma_20}")
                return MarketState.UNKNOWN
            
            volatility_norm = volatility if volatility >= 0 else 0
            momentum_norm = momentum if momentum is not None else 0
            momentum_abs = abs(momentum_norm)
            
            # === SYNTHETIC INDEX OPTIMIZED THRESHOLDS ===
            # These indices (R_10..R_100) move in smaller increments, so
            # we use lower thresholds and require SMA confirmation.
            
            # 1. Volatile market (highest priority - extreme volatility overrides all)
            if volatility_norm > 0.8:
                return MarketState.VOLATILE
            
            # 2. Trending market detection
            # Require: price above/below BOTH SMAs + sustained momentum + RSI confirmation
            price_above_sma20 = current_price > sma_20
            price_below_sma20 = current_price < sma_20
            price_above_sma50 = current_price > sma_50
            price_below_sma50 = current_price < sma_50
            
            # TRENDING UP: price above both SMAs, positive momentum, RSI > 55
            if (price_above_sma20 and price_above_sma50 
                and momentum_norm > 0.3 and rsi > 55
                and trend_strength > 0.02):
                return MarketState.TRENDING_UP
            
            # TRENDING DOWN: price below both SMAs, negative momentum, RSI < 45
            if (price_below_sma20 and price_below_sma50 
                and momentum_norm < -0.3 and rsi < 45
                and trend_strength > 0.02):
                return MarketState.TRENDING_DOWN
            
            # Weak trend detection (price above/below SMAs but lower conviction)
            # Still flag as trending to allow trading, but with reduced confidence
            if (price_above_sma20 and price_above_sma50 and momentum_norm > 0.1):
                return MarketState.TRENDING_UP
            if (price_below_sma20 and price_below_sma50 and momentum_norm < -0.1):
                return MarketState.TRENDING_DOWN
            
            # 3. Ranging market: price oscillating around SMAs, low momentum
            # For synthetic indices, this is the MOST common state
            # Only return ranging if momentum is truly low AND no clear SMA alignment
            if momentum_abs < 0.5 and trend_strength < 0.02:
                # Double-check: price crossing one of the SMAs confirms range
                sma_20_distance = abs(current_price - sma_20) / sma_20
                if sma_20_distance < 0.01:  # Price within 1% of SMA-20
                    return MarketState.RANGING
                if rsi < 45 or rsi > 55:  # RSI shows some directional bias
                    # Not truly ranging - has momentum
                    pass
                return MarketState.RANGING
            
            # 4. Calm market (very low volatility + low momentum)
            if volatility_norm < 0.15 and momentum_abs < 0.2:
                return MarketState.CALM
            
            # Default: if we have data but no clear classification,
            # return ranging as the safest default
            if len(self.price_history) >= 50:
                return MarketState.RANGING
            
            return MarketState.UNKNOWN
            
        except Exception as e:
            agent_logger.log_warning(f"Error in market state detection: {e}")
            import traceback
            agent_logger.log_warning(f"Traceback: {traceback.format_exc()}")
            return MarketState.UNKNOWN
    
    def calculate_market_health(self) -> float:
        """
        Calculate market health score (0-100).
        Score represents attractiveness for trading.
        Higher = better trading conditions.
        """
        if len(self.price_history) < 20:
            return 50.0
        
        features = self.feature_engine.extract_features()
        health = 50.0  # Base score
        
        # Volatility component (10-20 range)
        volatility = features.get('volatility', 0.5)
        if 0.25 < volatility < 0.75:  # Moderate volatility is good
            health += 10.0
        elif volatility < 0.25:
            health += 5.0
        elif volatility > 0.75:
            health += 3.0
        
        # Trend strength component (10-20 range)
        trend_strength = features.get('trend_strength', 0.0)
        if trend_strength > 0.05:
            health += 10.0
        elif trend_strength > 0.02:
            health += 5.0
        
        # Momentum component (5-15 range)
        momentum = features.get('momentum_positive', 0.0)
        if momentum > 0.5:
            health += 10.0
        
        # Price position component (5-10 range)
        bb_position = features.get('bb_position', 0.5)
        if 0.2 < bb_position < 0.8:  # Not at extremes
            health += 5.0
        
        # RSI component (5-10 range)
        rsi = features.get('rsi', 50.0)
        if 40 < rsi < 60:  # Neutral RSI is good
            health += 5.0
        elif 30 < rsi < 70:
            health += 2.0
        
        # MA alignment component (5-10 range)
        if features.get('ma_crossover', 0.0) > 0.5:
            health += 7.0
        
        # Cap at 100
        return min(health, 100.0)
    
    def get_market_regime(self) -> Dict[str, any]:
        """
        Get detailed market regime information.
        Returns dict with state, health, and components.
        """
        state = self.detect_market_state()
        health = self.calculate_market_health()
        features = self.feature_engine.extract_features()
        
        regime = {
            'state': state,
            'health': health,
            'volatility': features.get('volatility', 0.0),
            'momentum': features.get('momentum_10', 0.0),
            'rsi': features.get('rsi', 50.0),
            'trend_strength': features.get('trend_strength', 0.0),
            'price_current': features.get('price_current', 0.0),
            'ready_for_trading': health >= 50,
            'optimal_for_trading': health >= 70,
        }
        
        return regime
    
    def get_strategy_recommendation(self) -> Dict[str, any]:
        """
        Recommend best strategy based on market state.
        Returns dict with recommended strategy and confidence.
        """
        state = self.detect_market_state()
        features = self.feature_engine.extract_features()
        volatility = features.get('volatility', 0.5)
        momentum = features.get('momentum_10', 0.0)
        
        recommendation = {'strategy': None, 'confidence': 0.0}
        
        if state == MarketState.TRENDING_UP or state == MarketState.TRENDING_DOWN:
            # Accumulator works well in trending markets
            if volatility > 0.3:
                recommendation['strategy'] = 'accumulator'
                recommendation['confidence'] = 0.75
            else:
                # Higher/Lower in stable trends
                recommendation['strategy'] = 'higher_lower'
                recommendation['confidence'] = 0.70
        
        elif state == MarketState.VOLATILE:
            # Higher/Lower in volatile markets
            recommendation['strategy'] = 'higher_lower'
            recommendation['confidence'] = 0.65
        
        elif state == MarketState.RANGING:
            # Rise/Fall in ranging markets
            recommendation['strategy'] = 'rise_fall'
            recommendation['confidence'] = 0.60
        
        elif state == MarketState.CALM:
            # Take break in calm markets
            recommendation['strategy'] = 'hold'
            recommendation['confidence'] = 0.0
        
        else:  # UNKNOWN
            recommendation['strategy'] = 'hold'
            recommendation['confidence'] = 0.0
        
        return recommendation
    
    def get_price_trend(self, period: int = 20) -> float:
        """Get price trend (-1.0 to 1.0, where 1.0 = strong uptrend)."""
        if len(self.price_history) < period:
            return 0.0
        
        prices = list(self.price_history)[-period:]
        regression_slope = np.polyfit(range(len(prices)), prices, 1)[0]
        avg_price = np.mean(prices)
        
        if avg_price == 0:
            return 0.0
        
        normalized_slope = regression_slope / avg_price * 100
        return float(np.tanh(normalized_slope))  # Bound to [-1, 1]
    
    def get_volatility_trend(self) -> str:
        """Get volatility trend: increasing, decreasing, or stable."""
        if len(self.price_history) < 30:
            return "unknown"
        
        prices_recent = list(self.price_history)[-15:]
        prices_older = list(self.price_history)[-30:-15]
        
        vol_recent = np.std(np.diff(prices_recent))
        vol_older = np.std(np.diff(prices_older))
        
        if vol_recent > vol_older * 1.1:
            return "increasing"
        elif vol_recent < vol_older * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def get_support_resistance_levels(self) -> Dict[str, float]:
        """Identify key support and resistance levels."""
        if len(self.price_history) < 20:
            return {'support': 0.0, 'resistance': 0.0}
        
        prices = np.array(list(self.price_history))
        
        support = float(np.percentile(prices, 25))
        resistance = float(np.percentile(prices, 75))
        
        return {
            'support': support,
            'resistance': resistance,
            'current': float(prices[-1]),
            'range': resistance - support
        }
    
    def is_consolidating(self) -> bool:
        """Check if market is consolidating (tight range, low volatility)."""
        volatility = self.feature_engine.indicators.volatility(20)
        return volatility < 0.3
    
    def is_breaking_out(self) -> bool:
        """Check if market is breaking out (high volatility, strong momentum)."""
        volatility = self.feature_engine.indicators.volatility(20)
        momentum = abs(self.feature_engine.indicators.momentum(20))
        return volatility > 0.6 and momentum > 2.0
