"""
Rise/Fall strategy - predict if price will rise or fall within a timeframe.
Works well in ranging and consolidating markets.
"""

from typing import Dict
from datetime import datetime
from strategies import BaseStrategy, TradeSignal


class RiseFallStrategy(BaseStrategy):
    """Rise/Fall strategy for consolidation trades."""
    
    def __init__(self, base_stake: float = 1.0):
        super().__init__("rise_fall", base_stake)
        self.min_confidence_threshold = 0.58
    
    def analyze(self, market_data: Dict) -> TradeSignal:
        """
        Analyze market for Rise/Fall opportunity.
        Strategy: Trade mean-reversion in ranging markets.
        """
        features = market_data.get('features', {})
        
        # Extract signals
        bb_position = features.get('bb_position', 0.5)
        bb_upper = features.get('bb_upper', 0.0)
        bb_lower = features.get('bb_lower', 0.0)
        bb_middle = features.get('bb_middle', 0.0)
        rsi = features.get('rsi', 50.0)
        price_current = features.get('price_current', 0.0)
        momentum = features.get('momentum_10', 0.0)
        volatility = features.get('volatility', 0.5)
        
        # Determine direction
        action = 'HOLD'
        contract_type = None
        confidence = 0.0
        reasoning = ""
        
        # Price at lower Bollinger Band - expect rise
        if bb_position < 0.3 and rsi < 40:
            action = 'BUY'
            contract_type = 'RISE'
            confidence = 0.65
            reasoning = f"Price at lower BB (pos={bb_position:.1f}), RSI={rsi:.1f} - expecting mean reversion UP"
        
        # Price at upper Bollinger Band - expect fall
        elif bb_position > 0.7 and rsi > 60:
            action = 'BUY'
            contract_type = 'FALL'
            confidence = 0.65
            reasoning = f"Price at upper BB (pos={bb_position:.1f}), RSI={rsi:.1f} - expecting mean reversion DOWN"
        
        # Mid-range, use momentum
        elif 0.35 < bb_position < 0.65:
            if momentum > 1.0:
                action = 'BUY'
                contract_type = 'RISE'
                confidence = 0.55
                reasoning = f"Mid-range with positive momentum ({momentum:.1f})"
            elif momentum < -1.0:
                action = 'BUY'
                contract_type = 'FALL'
                confidence = 0.55
                reasoning = f"Mid-range with negative momentum ({momentum:.1f})"
        
        # Adjust for volatility
        if volatility < 0.25:
            # Low volatility, good for mean reversion
            confidence += 0.05
            reasoning += " + low volatility (favorable)"
        elif volatility > 0.7:
            # High volatility, risky
            confidence *= 0.8
            reasoning += " (high volatility risk)"
        
        # Cap confidence
        confidence = min(confidence, 1.0)
        
        signal = TradeSignal(
            strategy='rise_fall',
            action=action,
            confidence=confidence,
            amount=self.base_stake,
            contract_type=contract_type or 'RISE',
            duration=180,  # 3 minutes
            timestamp=datetime.now(),
            reasoning=reasoning
        )
        
        return signal
    
    def get_confidence(self, market_data: Dict) -> float:
        """Get confidence score for current market."""
        signal = self.analyze(market_data)
        return signal.confidence if signal.action == 'BUY' else 0.0
