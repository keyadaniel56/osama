"""
Accumulator strategy - multi-leg contract with anti-knockout protection.
Works well in trending markets.
"""

from typing import Dict
from datetime import datetime
from strategies import BaseStrategy, TradeSignal


class AccumulatorStrategy(BaseStrategy):
    """Accumulator contract strategy for sustained trends."""
    
    def __init__(self, base_stake: float = 1.0):
        super().__init__("accumulator", base_stake)
        self.min_trend_strength = 0.05
        self.min_confidence_threshold = 0.60
    
    def analyze(self, market_data: Dict) -> TradeSignal:
        """
        Analyze market for Accumulator opportunity.
        Strategy: Trade in the direction of strong trends.
        """
        features = market_data.get('features', {})
        
        # Extract trend signals
        trend_strength = features.get('trend_strength', 0.0)
        momentum = features.get('momentum_20', 0.0)
        sma_20 = features.get('sma_20', 0.0)
        sma_50 = features.get('sma_50', 0.0)
        price_current = features.get('price_current', 0.0)
        volatility = features.get('volatility', 0.5)
        
        # Determine direction
        action = 'HOLD'
        contract_type = None
        confidence = 0.0
        reasoning = ""
        
        # Check for uptrend
        if (price_current > sma_50 and 
            sma_20 > sma_50 and 
            momentum > 0 and 
            trend_strength > self.min_trend_strength):
            
            action = 'BUY'
            contract_type = 'RISE'
            confidence = 0.70
            reasoning = f"Strong uptrend: price>{sma_50:.2f}, momentum={momentum:.1f}"
        
        # Check for downtrend
        elif (price_current < sma_50 and 
              sma_20 < sma_50 and 
              momentum < 0 and 
              trend_strength > self.min_trend_strength):
            
            action = 'BUY'
            contract_type = 'FALL'
            confidence = 0.70
            reasoning = f"Strong downtrend: price<{sma_50:.2f}, momentum={momentum:.1f}"
        
        # Strengthen signal if indicators align
        if features.get('ma_crossover', 0.0) > 0.5:
            confidence += 0.05
            reasoning += " + MA aligned"
        
        # Reduce confidence if volatility is extreme
        if volatility > 0.8:
            confidence *= 0.85
            reasoning += " (high volatility risk)"
        
        # Cap confidence
        confidence = min(confidence, 1.0)
        
        signal = TradeSignal(
            strategy='accumulator',
            action=action,
            confidence=confidence,
            amount=self.base_stake,
            contract_type=contract_type or 'RISE',
            duration=300,  # 5 minutes
            timestamp=datetime.now(),
            reasoning=reasoning
        )
        
        return signal
    
    def get_confidence(self, market_data: Dict) -> float:
        """Get confidence score for current market."""
        signal = self.analyze(market_data)
        return signal.confidence if signal.action == 'BUY' else 0.0
