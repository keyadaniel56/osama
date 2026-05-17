"""
Higher/Lower strategy - bet if price will go higher or lower in next 15-60 seconds.
Works well in ranging and volatile markets.
"""

from typing import Dict
from datetime import datetime
from strategies import BaseStrategy, TradeSignal


class HigherLowerStrategy(BaseStrategy):
    """Higher/Lower binary options strategy."""
    
    def __init__(self, base_stake: float = 1.0):
        super().__init__("higher_lower", base_stake)
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.min_confidence_threshold = 0.55
    
    def analyze(self, market_data: Dict) -> TradeSignal:
        """
        Analyze market for Higher/Lower opportunity.
        Strategy: Look for RSI extremes and momentum.
        """
        features = market_data.get('features', {})
        
        # Extract key signals
        rsi = features.get('rsi', 50.0)
        momentum = features.get('momentum_10', 0.0)
        volatility = features.get('volatility', 0.5)
        
        # Determine direction
        action = 'HOLD'
        contract_type = None
        confidence = 0.0
        reasoning = ""
        
        # RSI-based signal
        if rsi < self.rsi_oversold:
            action = 'BUY'
            contract_type = 'HIGHER'  # Price likely to go up
            confidence = 0.65
            reasoning = f"RSI oversold ({rsi:.1f}), expecting recovery"
        elif rsi > self.rsi_overbought:
            action = 'BUY'
            contract_type = 'LOWER'  # Price likely to go down
            confidence = 0.65
            reasoning = f"RSI overbought ({rsi:.1f}), expecting pullback"
        
        # Momentum confirmation
        if momentum > 2.0 and contract_type == 'HIGHER':
            confidence += 0.1
            reasoning += " + positive momentum"
        elif momentum < -2.0 and contract_type == 'LOWER':
            confidence += 0.1
            reasoning += " + negative momentum"
        
        # Volatility adjustment
        if volatility > 0.6:
            # High volatility reduces confidence
            confidence *= 0.9
            reasoning += " (adjusted for volatility)"
        
        # Cap confidence
        confidence = min(confidence, 1.0)
        
        signal = TradeSignal(
            strategy='higher_lower',
            action=action,
            confidence=confidence,
            amount=self.base_stake,
            contract_type=contract_type or 'HIGHER',
            duration=60,  # 60 seconds
            timestamp=datetime.now(),
            reasoning=reasoning
        )
        
        return signal
    
    def get_confidence(self, market_data: Dict) -> float:
        """Get confidence score for current market."""
        signal = self.analyze(market_data)
        return signal.confidence if signal.action == 'BUY' else 0.0
