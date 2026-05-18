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
        self.feature_engine = FeatureEngine(window=30)
        self.price_history = deque(maxlen=window)
    
    def update(self, price: float, volume: float = 1.0):
        """Update analyzer with new price data."""
        self.feature_engine.add_price(price, volume)
        self.price_history.append(price)
    
    def detect_market_state(self) -> str:
        """
        Detect current market state with more reliable thresholds.
        Returns: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, CALM, or UNKNOWN
        """
        if len(self.price_history) < 20:
            return MarketState.UNKNOWN
        
        try:
            # Extract key metrics
            volatility = self.feature_engine.indicators.volatility(20)
            momentum = self.feature_engine.indicators.momentum(20)
            sma_20 = self.feature_engine.indicators.sma(20)
            sma_50 = self.feature_engine.indicators.sma(50)
            current_price = self.feature_engine.indicators.current_price()
            
            # Normalize momentum to 0-1 range
            momentum_abs = abs(momentum) if momentum != 0 else 0
            volatility_norm = volatility if volatility >= 0 else 0
            
            # IMPROVED THRESHOLDS:
            
            # Check for volatile market FIRST (highest priority)
            if volatility_norm > 0.5:
                return MarketState.VOLATILE
            
            # Check for trending market (momentum + price action)
            if momentum > 1.0 and current_price > sma_20:
                if current_price > sma_50:
                    return MarketState.TRENDING_UP
                else:
                    return MarketState.RANGING  # Mixed signals
            elif momentum < -1.0 and current_price < sma_20:
                if current_price < sma_50:
                    return MarketState.TRENDING_DOWN
                else:
                    return MarketState.RANGING  # Mixed signals
            
            # Check for ranging market (low momentum, moderate volatility)
            if volatility_norm < 0.4 and momentum_abs < 1.0:
                return MarketState.RANGING
            
            # Check for calm market (very low volatility)
            if volatility_norm < 0.2:
                return MarketState.CALM
            
            # Default to ranging for unclear signals
            return MarketState.RANGING
            
        except Exception as e:
            agent_logger.log_warning(f"Error in market state detection: {e}")
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
