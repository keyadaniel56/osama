"""
Strategy base class and interfaces for trading strategies.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TradeSignal:
    """Represents a trading signal."""
    strategy: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float  # 0.0-1.0
    amount: float
    contract_type: str  # e.g., 'HIGHER', 'LOWER', 'RISE', 'FALL'
    duration: int  # seconds
    timestamp: datetime
    reasoning: str


class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, name: str, base_stake: float = 1.0):
        self.name = name
        self.base_stake = base_stake
        self.trades_count = 0
        self.wins = 0
        self.losses = 0
        self.performance_history = []
    
    @abstractmethod
    def analyze(self, market_data: Dict) -> TradeSignal:
        """Analyze market and generate signal."""
        pass
    
    @abstractmethod
    def get_confidence(self, market_data: Dict) -> float:
        """Get confidence score (0.0-1.0) for current market."""
        pass
    
    def record_win(self, amount: float):
        """Record a winning trade."""
        self.wins += 1
        self.trades_count += 1
        self.performance_history.append({'result': 'win', 'amount': amount})
    
    def record_loss(self, amount: float):
        """Record a losing trade."""
        self.losses += 1
        self.trades_count += 1
        self.performance_history.append({'result': 'loss', 'amount': -amount})
    
    def get_win_rate(self) -> float:
        """Get win rate (0.0-1.0)."""
        if self.trades_count == 0:
            return 0.5
        return self.wins / self.trades_count
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'total_trades': self.trades_count,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.get_win_rate(),
        }
