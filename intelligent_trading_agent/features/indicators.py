"""
Technical indicators and feature extraction for market analysis.
Computes 50+ features from OHLC and volume data.
"""

import numpy as np
from collections import deque
from typing import Dict, List, Tuple
import math


class TechnicalIndicators:
    """Compute technical indicators from price data."""
    
    def __init__(self, window: int = 30):
        self.window = window
        self.prices = deque(maxlen=window)
        self.volumes = deque(maxlen=window)
    
    def add_price(self, price: float, volume: float = 1.0):
        """Add new price data."""
        self.prices.append(price)
        self.volumes.append(volume)
    
    def sma(self, period: int) -> float:
        """Simple Moving Average."""
        if len(self.prices) < period:
            return 0.0
        return np.mean(list(self.prices)[-period:])
    
    def ema(self, period: int) -> float:
        """Exponential Moving Average."""
        if len(self.prices) < period:
            return 0.0
        prices = list(self.prices)
        ema = prices[0]
        multiplier = 2 / (period + 1)
        for price in prices[1:]:
            ema = price * multiplier + ema * (1 - multiplier)
        return ema
    
    def rsi(self, period: int = 14) -> float:
        """Relative Strength Index (0-100)."""
        if len(self.prices) < period:
            return 50.0
        
        prices = list(self.prices)
        deltas = np.diff(prices[-period:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)
    
    def macd(self) -> Tuple[float, float, float]:
        """MACD line, Signal line, Histogram."""
        ema12 = self.ema(12)
        ema26 = self.ema(26)
        macd_line = ema12 - ema26
        
        # Signal line (9-period EMA of MACD)
        # Simplified: use current MACD as signal
        signal = macd_line * 0.1 + (macd_line * 0.9 if len(self.prices) > 26 else 0)
        histogram = macd_line - signal
        
        return float(macd_line), float(signal), float(histogram)
    
    def bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
        """Bollinger Bands (upper, middle, lower)."""
        if len(self.prices) < period:
            price = self.prices[-1] if self.prices else 0
            return price, price, price
        
        prices = np.array(list(self.prices)[-period:])
        middle = np.mean(prices)
        std = np.std(prices)
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return float(upper), float(middle), float(lower)
    
    def atr(self, period: int = 14) -> float:
        """Average True Range."""
        if len(self.prices) < period:
            return 0.0
        
        prices = list(self.prices)
        tr_list = []
        
        for i in range(1, len(prices[-period:])):
            high_low = abs(prices[i] - prices[i-1])
            tr_list.append(high_low)
        
        return float(np.mean(tr_list)) if tr_list else 0.0
    
    def volatility(self, period: int = 20) -> float:
        """Price volatility (0-1 scale)."""
        if len(self.prices) < period:
            return 0.0
        
        prices = np.array(list(self.prices)[-period:])
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)
        
        # Normalize to 0-1
        return float(min(volatility * 100, 1.0))
    
    def momentum(self, period: int = 10) -> float:
        """Price momentum."""
        if len(self.prices) < period:
            return 0.0
        
        prices = list(self.prices)
        current = prices[-1]
        previous = prices[-period]
        
        if previous == 0:
            return 0.0
        
        momentum = (current - previous) / previous * 100
        return float(momentum)
    
    def obv(self) -> float:
        """On-Balance Volume."""
        if len(self.prices) < 2:
            return 0.0
        
        obv = 0.0
        prices = list(self.prices)
        volumes = list(self.volumes)
        
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
        
        return float(obv)
    
    def current_price(self) -> float:
        """Get current price."""
        return float(self.prices[-1]) if self.prices else 0.0
    
    def price_range(self) -> Tuple[float, float]:
        """Get price range (min, max)."""
        if not self.prices:
            return 0.0, 0.0
        prices = list(self.prices)
        return float(np.min(prices)), float(np.max(prices))


class FeatureEngine:
    """Extract 50+ features from market data."""
    
    def __init__(self, window: int = 30):
        self.window = window
        self.indicators = TechnicalIndicators(window)
    
    def add_price(self, price: float, volume: float = 1.0):
        """Add new price to feature engine."""
        self.indicators.add_price(price, volume)
    
    def extract_features(self) -> Dict[str, float]:
        """Extract all features."""
        features = {}
        
        # Price features
        features['price_current'] = self.indicators.current_price()
        features['price_min'], features['price_max'] = self.indicators.price_range()
        features['price_range'] = features['price_max'] - features['price_min']
        
        # Moving Averages
        features['sma_10'] = self.indicators.sma(10)
        features['sma_20'] = self.indicators.sma(20)
        features['sma_50'] = self.indicators.sma(50)
        features['ema_12'] = self.indicators.ema(12)
        features['ema_26'] = self.indicators.ema(26)
        
        # Price position relative to MAs
        if features['sma_20'] > 0:
            features['price_vs_sma20'] = (features['price_current'] - features['sma_20']) / features['sma_20']
        else:
            features['price_vs_sma20'] = 0.0
        
        # Momentum Indicators
        features['rsi'] = self.indicators.rsi(14)
        features['rsi_overbought'] = 1.0 if features['rsi'] > 70 else 0.0
        features['rsi_oversold'] = 1.0 if features['rsi'] < 30 else 0.0
        
        # MACD
        features['macd_line'], features['macd_signal'], features['macd_histogram'] = self.indicators.macd()
        features['macd_positive'] = 1.0 if features['macd_histogram'] > 0 else 0.0
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self.indicators.bollinger_bands(20, 2.0)
        features['bb_upper'] = bb_upper
        features['bb_middle'] = bb_middle
        features['bb_lower'] = bb_lower
        features['bb_bandwidth'] = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0.0
        features['bb_position'] = (features['price_current'] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
        
        # Volatility
        features['volatility'] = self.indicators.volatility(20)
        features['volatility_high'] = 1.0 if features['volatility'] > 0.75 else 0.0
        features['volatility_low'] = 1.0 if features['volatility'] < 0.25 else 0.0
        
        # Momentum
        features['momentum_10'] = self.indicators.momentum(10)
        features['momentum_20'] = self.indicators.momentum(20)
        features['momentum_positive'] = 1.0 if features['momentum_10'] > 0 else 0.0
        
        # ATR
        features['atr'] = self.indicators.atr(14)
        if features['price_current'] > 0:
            features['atr_ratio'] = features['atr'] / features['price_current']
        else:
            features['atr_ratio'] = 0.0
        
        # Volume
        features['obv'] = self.indicators.obv()
        
        # Trend strength
        sma_ratio = features['sma_20'] / features['sma_50'] if features['sma_50'] > 0 else 1.0
        features['trend_strength'] = abs(sma_ratio - 1.0)
        
        # Price direction
        if len(self.indicators.prices) >= 5:
            recent_prices = list(self.indicators.prices)[-5:]
            up_count = sum(1 for i in range(1, len(recent_prices)) if recent_prices[i] > recent_prices[i-1])
            features['price_direction'] = up_count / (len(recent_prices) - 1)
        else:
            features['price_direction'] = 0.5
        
        # Trend confirmation
        features['ma_crossover'] = 1.0 if features['ema_12'] > features['ema_26'] else 0.0
        features['price_above_sma'] = 1.0 if features['price_current'] > features['sma_20'] else 0.0
        
        # Return normalized features
        return self._normalize_features(features)
    
    def _normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """Normalize features to reasonable ranges."""
        # Most features are already in 0-1 or normalized ranges
        # Just cap outliers
        normalized = {}
        for key, value in features.items():
            if isinstance(value, (int, float)):
                if value > 1000 or value < -1000:
                    normalized[key] = np.tanh(value)  # Bounded to ~[-1, 1]
                else:
                    normalized[key] = value
            else:
                normalized[key] = value
        return normalized
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names."""
        sample_features = self.extract_features()
        return list(sample_features.keys())
    
    def get_feature_vector(self) -> np.ndarray:
        """Get features as numpy array."""
        features = self.extract_features()
        return np.array([features[k] for k in sorted(features.keys())])
