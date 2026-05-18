"""
Smart Money Concepts (SMC) Analysis
- Order Blocks (bullish/bearish)
- Support & Resistance zones
- Market Structure (Higher Highs, Lower Lows)
- Multi-timeframe trend analysis
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from collections import deque


@dataclass
class OrderBlock:
    """Represents an order block zone."""
    price_high: float
    price_low: float
    block_type: str  # 'bullish' or 'bearish'
    strength: float  # 0.0 to 1.0
    timestamp: float
    tested: bool = False


@dataclass
class SRZone:
    """Support/Resistance zone."""
    price: float
    zone_type: str  # 'support' or 'resistance'
    strength: int  # Number of touches
    last_test: float


class SMCAnalyzer:
    """Smart Money Concepts analyzer."""
    
    def __init__(self, lookback: int = 100):
        self.lookback = lookback
        self.prices_1m = deque(maxlen=lookback)  # 1-minute timeframe
        self.prices_5m = deque(maxlen=lookback)  # 5-minute timeframe
        self.prices_15m = deque(maxlen=lookback)  # 15-minute timeframe
        
        self.order_blocks: List[OrderBlock] = []
        self.support_zones: List[SRZone] = []
        self.resistance_zones: List[SRZone] = []
        
        self.swing_highs = []
        self.swing_lows = []
        
        # Candle building for higher timeframes
        self.current_5m_candle = None
        self.current_15m_candle = None
        self.candle_5m_start = None
        self.candle_15m_start = None
    
    def add_tick(self, price: float, timestamp: float):
        """Add new tick and update all timeframes."""
        self.prices_1m.append(price)
        
        # Build 5-minute candles
        if self.candle_5m_start is None or (timestamp - self.candle_5m_start) >= 300:
            if self.current_5m_candle is not None:
                self.prices_5m.append(self.current_5m_candle['close'])
            self.current_5m_candle = {'open': price, 'high': price, 'low': price, 'close': price}
            self.candle_5m_start = timestamp
        else:
            self.current_5m_candle['high'] = max(self.current_5m_candle['high'], price)
            self.current_5m_candle['low'] = min(self.current_5m_candle['low'], price)
            self.current_5m_candle['close'] = price
        
        # Build 15-minute candles
        if self.candle_15m_start is None or (timestamp - self.candle_15m_start) >= 900:
            if self.current_15m_candle is not None:
                self.prices_15m.append(self.current_15m_candle['close'])
            self.current_15m_candle = {'open': price, 'high': price, 'low': price, 'close': price}
            self.candle_15m_start = timestamp
        else:
            self.current_15m_candle['high'] = max(self.current_15m_candle['high'], price)
            self.current_15m_candle['low'] = min(self.current_15m_candle['low'], price)
            self.current_15m_candle['close'] = price
        
        # Update analysis periodically
        if len(self.prices_1m) >= 50:
            self._update_swing_points()
            self._update_order_blocks(timestamp)
            self._update_sr_zones()
    
    def _update_swing_points(self):
        """Identify swing highs and lows."""
        if len(self.prices_1m) < 10:
            return
        
        prices = np.array(list(self.prices_1m))
        
        # Find swing highs (local maxima)
        self.swing_highs = []
        for i in range(5, len(prices) - 5):
            if prices[i] == max(prices[i-5:i+6]):
                self.swing_highs.append((i, prices[i]))
        
        # Find swing lows (local minima)
        self.swing_lows = []
        for i in range(5, len(prices) - 5):
            if prices[i] == min(prices[i-5:i+6]):
                self.swing_lows.append((i, prices[i]))
    
    def _update_order_blocks(self, timestamp: float):
        """Identify order blocks (last bearish candle before bullish move, etc.)."""
        if len(self.prices_1m) < 20:
            return
        
        prices = list(self.prices_1m)
        
        # Clear old order blocks (older than 50 ticks)
        self.order_blocks = [ob for ob in self.order_blocks if timestamp - ob.timestamp < 50]
        
        # Look for bullish order blocks
        # (Last red candle before strong green move)
        for i in range(len(prices) - 15, len(prices) - 5):
            if i < 5:
                continue
            
            # Check if this was a down move followed by strong up move
            down_move = prices[i] < prices[i-1]
            strong_up = prices[i+5] > prices[i] * 1.0005  # 0.05% up
            
            if down_move and strong_up:
                # This is a bullish order block
                ob = OrderBlock(
                    price_high=prices[i],
                    price_low=prices[i] * 0.9995,
                    block_type='bullish',
                    strength=0.8,
                    timestamp=timestamp
                )
                
                # Check if not duplicate
                if not any(abs(ob.price_high - existing.price_high) < prices[i] * 0.0001 
                          for existing in self.order_blocks):
                    self.order_blocks.append(ob)
        
        # Look for bearish order blocks
        for i in range(len(prices) - 15, len(prices) - 5):
            if i < 5:
                continue
            
            up_move = prices[i] > prices[i-1]
            strong_down = prices[i+5] < prices[i] * 0.9995  # 0.05% down
            
            if up_move and strong_down:
                ob = OrderBlock(
                    price_high=prices[i] * 1.0005,
                    price_low=prices[i],
                    block_type='bearish',
                    strength=0.8,
                    timestamp=timestamp
                )
                
                if not any(abs(ob.price_low - existing.price_low) < prices[i] * 0.0001 
                          for existing in self.order_blocks):
                    self.order_blocks.append(ob)
    
    def _update_sr_zones(self):
        """Update support and resistance zones based on swing points."""
        if not self.swing_highs or not self.swing_lows:
            return
        
        # Group swing highs into resistance zones
        self.resistance_zones = []
        high_prices = [price for _, price in self.swing_highs[-10:]]
        
        for price in high_prices:
            # Check if close to existing zone
            found = False
            for zone in self.resistance_zones:
                if abs(price - zone.price) / zone.price < 0.001:  # Within 0.1%
                    zone.strength += 1
                    found = True
                    break
            
            if not found:
                self.resistance_zones.append(SRZone(
                    price=price,
                    zone_type='resistance',
                    strength=1,
                    last_test=0
                ))
        
        # Group swing lows into support zones
        self.support_zones = []
        low_prices = [price for _, price in self.swing_lows[-10:]]
        
        for price in low_prices:
            found = False
            for zone in self.support_zones:
                if abs(price - zone.price) / zone.price < 0.001:
                    zone.strength += 1
                    found = True
                    break
            
            if not found:
                self.support_zones.append(SRZone(
                    price=price,
                    zone_type='support',
                    strength=1,
                    last_test=0
                ))
    
    def get_market_structure(self) -> dict:
        """Analyze market structure (HH, HL, LH, LL)."""
        if len(self.swing_highs) < 3 or len(self.swing_lows) < 3:
            return {'structure': 'unknown', 'trend': 'ranging'}
        
        # Check recent swing highs
        recent_highs = [price for _, price in self.swing_highs[-3:]]
        recent_lows = [price for _, price in self.swing_lows[-3:]]
        
        # Higher Highs and Higher Lows = Uptrend
        hh = all(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs)))
        hl = all(recent_lows[i] > recent_lows[i-1] for i in range(1, len(recent_lows)))
        
        # Lower Highs and Lower Lows = Downtrend
        lh = all(recent_highs[i] < recent_highs[i-1] for i in range(1, len(recent_highs)))
        ll = all(recent_lows[i] < recent_lows[i-1] for i in range(1, len(recent_lows)))
        
        # ONLY accept perfect HH+HL or LH+LL - anything else is ranging
        if hh and hl:
            return {'structure': 'HH+HL', 'trend': 'uptrend', 'strength': 0.9}
        elif lh and ll:
            return {'structure': 'LH+LL', 'trend': 'downtrend', 'strength': 0.9}
        else:
            # Everything else is ranging (including HH alone, LL alone, mixed)
            return {'structure': 'mixed', 'trend': 'ranging', 'strength': 0.3}
    
    def get_multi_timeframe_trend(self) -> dict:
        """Get trend across multiple timeframes."""
        trends = {}
        
        # 1-minute trend
        if len(self.prices_1m) >= 20:
            prices_1m = np.array(list(self.prices_1m))
            sma_20 = np.mean(prices_1m[-20:])
            sma_50 = np.mean(prices_1m[-50:]) if len(prices_1m) >= 50 else sma_20
            
            if prices_1m[-1] > sma_20 > sma_50:
                trends['1m'] = 'up'
            elif prices_1m[-1] < sma_20 < sma_50:
                trends['1m'] = 'down'
            else:
                trends['1m'] = 'ranging'
        
        # 5-minute trend
        if len(self.prices_5m) >= 10:
            prices_5m = np.array(list(self.prices_5m))
            sma_10 = np.mean(prices_5m[-10:])
            
            if prices_5m[-1] > sma_10:
                trends['5m'] = 'up'
            elif prices_5m[-1] < sma_10:
                trends['5m'] = 'down'
            else:
                trends['5m'] = 'ranging'
        
        # 15-minute trend
        if len(self.prices_15m) >= 5:
            prices_15m = np.array(list(self.prices_15m))
            sma_5 = np.mean(prices_15m[-5:])
            
            if prices_15m[-1] > sma_5:
                trends['15m'] = 'up'
            elif prices_15m[-1] < sma_5:
                trends['15m'] = 'down'
            else:
                trends['15m'] = 'ranging'
        
        # Overall alignment
        if all(t == 'up' for t in trends.values()):
            trends['aligned'] = 'strong_up'
        elif all(t == 'down' for t in trends.values()):
            trends['aligned'] = 'strong_down'
        elif trends.get('5m') == trends.get('15m'):
            trends['aligned'] = f"moderate_{trends.get('5m')}"
        else:
            trends['aligned'] = 'mixed'
        
        return trends
    
    def get_trade_signal(self) -> Tuple[int, float, str]:
        """
        Get trading signal based on SMC analysis.
        Returns: (signal, confidence, reason)
        - signal: 1 = RISE, -1 = FALL, 0 = no trade
        """
        if len(self.prices_1m) < 50:
            return 0, 0.0, "Insufficient data"
        
        current_price = list(self.prices_1m)[-1]
        
        # Get market structure
        structure = self.get_market_structure()
        
        # NEVER trade ranging markets - this prevents most consecutive losses
        if structure['trend'] == 'ranging':
            return 0, 0.0, f"Ranging market - no trade (Structure: {structure['structure']})"
        
        # Get multi-timeframe trend
        mtf_trend = self.get_multi_timeframe_trend()
        
        # Check order blocks
        bullish_ob_near = any(
            ob.block_type == 'bullish' and 
            ob.price_low <= current_price <= ob.price_high * 1.001
            for ob in self.order_blocks
        )
        
        bearish_ob_near = any(
            ob.block_type == 'bearish' and 
            ob.price_high >= current_price >= ob.price_low * 0.999
            for ob in self.order_blocks
        )
        
        # Check support/resistance
        at_support = any(
            abs(current_price - zone.price) / zone.price < 0.0015
            for zone in self.support_zones
        )
        
        at_resistance = any(
            abs(current_price - zone.price) / zone.price < 0.0015
            for zone in self.resistance_zones
        )
        
        # BULLISH SIGNALS - ONLY trade perfect HH+HL structure
        
        # 1. Perfect structure + strong uptrend + bullish order block
        if (structure['structure'] == 'HH+HL' and
            mtf_trend.get('aligned') == 'strong_up' and 
            bullish_ob_near):
            return 1, 0.90, "Strong Uptrend + Bullish Order Block"
        
        # 2. Perfect structure + bounce from support
        if (structure['structure'] == 'HH+HL' and
            at_support and 
            mtf_trend.get('5m') == 'up' and 
            mtf_trend.get('1m') == 'up'):
            return 1, 0.85, "Uptrend + Support Bounce"
        
        # 3. Perfect structure + all timeframes aligned up
        if (structure['structure'] == 'HH+HL' and 
            mtf_trend.get('15m') == 'up' and
            mtf_trend.get('5m') == 'up' and
            mtf_trend.get('1m') == 'up'):
            return 1, 0.80, "Bullish Market Structure + HTF Uptrend"
        
        # BEARISH SIGNALS - ONLY trade perfect LH+LL structure
        
        # 1. Perfect structure + strong downtrend + bearish order block
        if (structure['structure'] == 'LH+LL' and
            mtf_trend.get('aligned') == 'strong_down' and 
            bearish_ob_near):
            return -1, 0.90, "Strong Downtrend + Bearish Order Block"
        
        # 2. Perfect structure + rejection from resistance
        if (structure['structure'] == 'LH+LL' and
            at_resistance and 
            mtf_trend.get('5m') == 'down' and 
            mtf_trend.get('1m') == 'down'):
            return -1, 0.85, "Downtrend + Resistance Rejection"
        
        # 3. Perfect structure + all timeframes aligned down
        if (structure['structure'] == 'LH+LL' and 
            mtf_trend.get('15m') == 'down' and
            mtf_trend.get('5m') == 'down' and
            mtf_trend.get('1m') == 'down'):
            return -1, 0.80, "Bearish Market Structure + HTF Downtrend"
        
        # NO CLEAR SIGNAL - only trade perfect structures
        return 0, 0.0, f"No perfect setup (Structure: {structure['structure']}, MTF: {mtf_trend.get('aligned')})"
    
    def get_analysis_summary(self) -> dict:
        """Get complete analysis summary."""
        current_price = list(self.prices_1m)[-1] if self.prices_1m else 0
        
        return {
            'current_price': current_price,
            'market_structure': self.get_market_structure(),
            'mtf_trend': self.get_multi_timeframe_trend(),
            'order_blocks': {
                'bullish': len([ob for ob in self.order_blocks if ob.block_type == 'bullish']),
                'bearish': len([ob for ob in self.order_blocks if ob.block_type == 'bearish'])
            },
            'support_zones': len(self.support_zones),
            'resistance_zones': len(self.resistance_zones),
            'swing_highs': len(self.swing_highs),
            'swing_lows': len(self.swing_lows)
        }
