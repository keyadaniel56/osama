"""
Strategy selector - chooses best strategy based on market conditions.
Matches market state to strategy and tracks performance per condition.
"""

from typing import Dict, Tuple, Optional
from market_analyzer import MarketAnalyzer
from strategies.higher_lower import HigherLowerStrategy
from strategies.accumulator import AccumulatorStrategy
from strategies.rise_fall import RiseFallStrategy
from logger import agent_logger


class StrategySelector:
    """
    Intelligent strategy selection based on market conditions.
    Tracks performance of each strategy in different market states.
    """
    
    def __init__(self, base_stake: float = 1.0):
        self.base_stake = base_stake
        
        # Initialize strategies
        self.strategies = {
            'higher_lower': HigherLowerStrategy(base_stake),
            'accumulator': AccumulatorStrategy(base_stake),
            'rise_fall': RiseFallStrategy(base_stake),
        }
        
        # Market analyzer
        self.market_analyzer = MarketAnalyzer(window=100)
        
        # Performance tracking per market state
        self.performance_by_state = {
            'trending_up': {'wins': 0, 'losses': 0},
            'trending_down': {'wins': 0, 'losses': 0},
            'ranging': {'wins': 0, 'losses': 0},
            'volatile': {'wins': 0, 'losses': 0},
            'calm': {'wins': 0, 'losses': 0},
        }
        
        # Strategy performance per market state
        self.strategy_performance = {}
        for market_state in self.performance_by_state.keys():
            self.strategy_performance[market_state] = {
                'higher_lower': {'wins': 0, 'losses': 0},
                'accumulator': {'wins': 0, 'losses': 0},
                'rise_fall': {'wins': 0, 'losses': 0},
            }
        
        self.current_market_state = None
        self.strategy_switch_cooldown = 0
    
    def update_market_data(self, price: float, volume: float = 1.0):
        """Update market analyzer with new price."""
        self.market_analyzer.update(price, volume)
        if self.strategy_switch_cooldown > 0:
            self.strategy_switch_cooldown -= 1
    
    def get_market_state(self) -> str:
        """Get current market state."""
        if not self.current_market_state:
            self.current_market_state = self.market_analyzer.detect_market_state()
        return self.current_market_state
    
    def select_strategy(self, market_data: Dict) -> Tuple[str, float]:
        """
        Select best strategy for current market.
        Returns: (strategy_name, confidence)
        """
        market_state = self.get_market_state()
        regime = self.market_analyzer.get_market_regime()
        
        agent_logger.log_info(
            f"Market state: {market_state}, Health: {regime['health']:.1f}"
        )
        
        # Get recommendations from market analyzer
        recommendation = self.market_analyzer.get_strategy_recommendation()
        recommended_strategy = recommendation['strategy']
        
        # If recommendation is 'hold', return hold
        if recommended_strategy == 'hold' or regime['health'] < 50:
            return 'hold', 0.0
        
        # Get confidence from each strategy
        strategy_scores = {}
        for name, strategy in self.strategies.items():
            confidence = strategy.get_confidence(market_data)
            strategy_scores[name] = confidence
        
        # Use recommendation as primary signal
        if recommended_strategy in self.strategies:
            strategy_scores[recommended_strategy] += 0.1
        
        # Select strategy with highest confidence
        selected_strategy = max(strategy_scores.items(), key=lambda x: x[1])
        strategy_name = selected_strategy[0]
        confidence = selected_strategy[1]
        
        # Check if we should switch strategies
        if self.strategy_switch_cooldown > 0:
            # Stick with current strategy during cooldown
            return strategy_name, confidence
        
        agent_logger.log_decision({
            'event': 'strategy_selected',
            'strategy': strategy_name,
            'confidence': confidence,
            'market_state': market_state,
            'scores': strategy_scores
        })
        
        return strategy_name, confidence
    
    def record_trade_result(self, strategy: str, market_state: str, win: bool, amount: float):
        """Record trade outcome for learning."""
        # Update overall performance
        if win:
            self.performance_by_state[market_state]['wins'] += 1
            self.strategies[strategy].record_win(amount)
        else:
            self.performance_by_state[market_state]['losses'] += 1
            self.strategies[strategy].record_loss(amount)
        
        # Update strategy performance per market state
        if win:
            self.strategy_performance[market_state][strategy]['wins'] += 1
        else:
            self.strategy_performance[market_state][strategy]['losses'] += 1
        
        agent_logger.log_trade({
            'strategy': strategy,
            'market_state': market_state,
            'result': 'WIN' if win else 'LOSS',
            'amount': amount
        })
    
    def get_strategy_stats_by_market_state(self, market_state: str) -> Dict:
        """Get performance stats for strategies in a market state."""
        stats = {}
        for strategy_name, performance in self.strategy_performance[market_state].items():
            total = performance['wins'] + performance['losses']
            win_rate = performance['wins'] / total if total > 0 else 0.5
            stats[strategy_name] = {
                'wins': performance['wins'],
                'losses': performance['losses'],
                'total': total,
                'win_rate': win_rate
            }
        return stats
    
    def get_overall_stats(self) -> Dict:
        """Get overall performance statistics."""
        stats = {}
        for market_state, performance in self.performance_by_state.items():
            total = performance['wins'] + performance['losses']
            win_rate = performance['wins'] / total if total > 0 else 0.0
            stats[market_state] = {
                'wins': performance['wins'],
                'losses': performance['losses'],
                'total': total,
                'win_rate': win_rate
            }
        return stats
    
    def get_market_regime(self) -> Dict:
        """Get detailed market regime information."""
        return self.market_analyzer.get_market_regime()
    
    def get_best_strategy_for_market_state(self, market_state: str) -> str:
        """Get best performing strategy for a market state."""
        stats = self.get_strategy_stats_by_market_state(market_state)
        
        if not stats:
            return 'higher_lower'  # Default fallback
        
        best_strategy = max(stats.items(), key=lambda x: x[1]['win_rate'])
        return best_strategy[0]
