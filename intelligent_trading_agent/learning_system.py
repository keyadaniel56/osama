"""
Learning system - continuous model training and adaptation.
Learns from trade outcomes and improves strategy parameters over time.
"""

import json
import os
import numpy as np
from datetime import datetime
from typing import Dict, List
from collections import deque
from logger import agent_logger
from config import MODELS_DIR


class LearningSystem:
    """
    Continuous learning system for the trading agent.
    Tracks performance and adapts parameters based on outcomes.
    """
    
    def __init__(self):
        self.trade_history = deque(maxlen=1000)
        self.performance_data = {}
        self.models_dir = MODELS_DIR
        self.last_save = datetime.now()
        
        # Load existing data if available
        self._load_performance_data()
    
    def record_trade(self, trade_data: Dict):
        """Record a trade for learning."""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'strategy': trade_data.get('strategy'),
            'market_state': trade_data.get('market_state'),
            'entry_price': trade_data.get('entry_price'),
            'exit_price': trade_data.get('exit_price'),
            'entry_confidence': trade_data.get('entry_confidence', 0.0),
            'profit': trade_data.get('profit', 0.0),
            'win': trade_data.get('win', False),
            'duration': trade_data.get('duration', 0),
        }
        
        self.trade_history.append(trade_record)
        
        # Update performance metrics
        self._update_performance_metrics(trade_record)
        
        # Periodic save
        if (datetime.now() - self.last_save).total_seconds() > 300:  # Save every 5 min
            self._save_performance_data()
            self.last_save = datetime.now()
    
    def _update_performance_metrics(self, trade_record: Dict):
        """Update performance metrics from trade."""
        strategy = trade_record['strategy']
        market_state = trade_record['market_state']
        win = trade_record['win']
        
        # Create key for this combination
        key = f"{strategy}_{market_state}"
        
        if key not in self.performance_data:
            self.performance_data[key] = {
                'strategy': strategy,
                'market_state': market_state,
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'total_profit': 0.0,
                'avg_profit_per_trade': 0.0,
                'win_rate': 0.0,
            }
        
        metrics = self.performance_data[key]
        metrics['total_trades'] += 1
        
        if win:
            metrics['wins'] += 1
        else:
            metrics['losses'] += 1
        
        metrics['total_profit'] += trade_record['profit']
        metrics['avg_profit_per_trade'] = metrics['total_profit'] / metrics['total_trades']
        metrics['win_rate'] = metrics['wins'] / metrics['total_trades'] if metrics['total_trades'] > 0 else 0.0
    
    def get_performance_summary(self) -> Dict:
        """Get summary of performance by strategy and market state."""
        summary = {}
        
        for key, metrics in self.performance_data.items():
            if metrics['total_trades'] >= 5:  # Only include if enough data
                summary[key] = metrics.copy()
        
        return summary
    
    def get_best_strategy_for_state(self, market_state: str) -> str:
        """Get best performing strategy for a market state."""
        best_strategy = None
        best_win_rate = 0.0
        
        for key, metrics in self.performance_data.items():
            if metrics['market_state'] == market_state and metrics['total_trades'] >= 3:
                if metrics['win_rate'] > best_win_rate:
                    best_win_rate = metrics['win_rate']
                    best_strategy = metrics['strategy']
        
        return best_strategy if best_strategy else 'higher_lower'
    
    def get_optimal_confidence_threshold(self, market_state: str) -> float:
        """
        Calculate optimal confidence threshold for a market state.
        Based on historical win rates at different confidence levels.
        """
        winning_confidences = []
        losing_confidences = []
        
        for trade in self.trade_history:
            if trade['market_state'] == market_state:
                if trade['win']:
                    winning_confidences.append(trade['entry_confidence'])
                else:
                    losing_confidences.append(trade['entry_confidence'])
        
        if not winning_confidences:
            return 0.60  # Default threshold
        
        # Find confidence level that maximizes win rate
        avg_winning = np.mean(winning_confidences) if winning_confidences else 0.5
        avg_losing = np.mean(losing_confidences) if losing_confidences else 0.5
        
        # Optimal threshold is between the two averages, biased toward winners
        optimal = avg_winning * 0.7 + avg_losing * 0.3
        
        return float(np.clip(optimal, 0.55, 0.85))
    
    def should_retrain_model(self) -> bool:
        """Determine if model should be retrained."""
        if len(self.trade_history) < 10:
            return False
        
        # Check if recent performance has degraded
        recent_trades = list(self.trade_history)[-20:]
        recent_win_rate = sum(1 for t in recent_trades if t['win']) / len(recent_trades)
        
        # Retrain if win rate drops below 55%
        return recent_win_rate < 0.55
    
    def get_adaptation_recommendations(self) -> Dict:
        """Get recommendations for parameter adaptation."""
        recommendations = {
            'adjust_stake': False,
            'new_stake_multiplier': 1.0,
            'pause_trading': False,
            'switch_strategy': False,
            'increase_confidence_threshold': False,
        }
        
        # Analyze recent performance
        if len(self.trade_history) < 5:
            return recommendations
        
        recent_trades = list(self.trade_history)[-20:]
        recent_profit = sum(t['profit'] for t in recent_trades)
        recent_win_rate = sum(1 for t in recent_trades if t['win']) / len(recent_trades)
        
        # Ensure we only use trades from the CURRENT session for pausing decisions
        # Check if any trades have a timestamp from today
        from datetime import datetime, timedelta
        now = datetime.now()
        recent_timestamps = [
            t.get('timestamp', '') for t in recent_trades
            if isinstance(t.get('timestamp', ''), str)
        ]
        has_current_session_trades = any(
            ts.startswith(now.strftime('%Y%m%d')) or 
            ts.startswith(now.strftime('%Y-%m-%d'))
            for ts in recent_timestamps
        )
        
        # Only recommend pausing if we have actual trades from today's session
        if not has_current_session_trades:
            return recommendations
        
        # Only consider for pausing if we have at least 10 recent trades (enough data)
        # This prevents pausing on just a few trades that happened to be unlucky
        if len(recent_trades) < 10:
            return recommendations
        
        # Require a LARGER sample before recommending pause
        # Small samples are unreliable - don't pause on just 5-9 trades
        # Only pause if win rate is significantly low AND we have meaningful data
        if recent_win_rate >= 0.40:
            return recommendations
        
        # Reduce stake if losing
        if recent_profit < 0 and recent_win_rate < 0.40:
            recommendations['adjust_stake'] = True
            recommendations['new_stake_multiplier'] = 0.75
            recommendations['pause_trading'] = True
            agent_logger.log_warning(f"Poor recent performance: {recent_win_rate:.1%} win rate, {recent_profit:.2f} profit")
        
        # Increase confidence threshold if win rate is low
        if recent_win_rate < 0.50:
            recommendations['increase_confidence_threshold'] = True
            agent_logger.log_warning("Recent win rate low, increasing confidence threshold")
        
        # Consider switching strategy if repeated losses
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            if not trade['win']:
                consecutive_losses += 1
            else:
                break
        
        if consecutive_losses >= 5:
            recommendations['switch_strategy'] = True
            agent_logger.log_warning(f"{consecutive_losses} consecutive losses, recommend strategy switch")
        
        return recommendations
    
    def _save_performance_data(self):
        """Save performance data to disk."""
        try:
            filepath = os.path.join(self.models_dir, 'performance_metrics.json')
            
            # Prepare data for JSON
            data_to_save = {
                'timestamp': datetime.now().isoformat(),
                'performance': self.performance_data,
                'recent_trades': list(self.trade_history)[-100:],  # Save last 100 trades
            }
            
            with open(filepath, 'w') as f:
                json.dump(data_to_save, f, indent=2)
            
            agent_logger.log_info(f"Performance data saved to {filepath}")
        except Exception as e:
            agent_logger.log_error(f"Failed to save performance data: {e}")
    
    def _load_performance_data(self):
        """Load performance data from disk."""
        try:
            filepath = os.path.join(self.models_dir, 'performance_metrics.json')
            
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                self.performance_data = data.get('performance', {})
                recent_trades = data.get('recent_trades', [])
                
                for trade in recent_trades:
                    self.trade_history.append(trade)
                
                agent_logger.log_info(f"Loaded {len(self.trade_history)} trades from disk")
        except Exception as e:
            agent_logger.log_error(f"Failed to load performance data: {e}")
    
    def export_learning_report(self) -> Dict:
        """Export comprehensive learning report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_trades': len(self.trade_history),
            'performance_summary': self.get_performance_summary(),
            'win_rate': self._calculate_overall_win_rate(),
            'total_profit': sum(t['profit'] for t in self.trade_history),
            'avg_trade_profit': self._calculate_avg_profit(),
            'best_performing_strategies': self._get_best_strategies(),
            'recommendations': self.get_adaptation_recommendations(),
        }
        
        return report
    
    def _calculate_overall_win_rate(self) -> float:
        """Calculate overall win rate."""
        if len(self.trade_history) == 0:
            return 0.0
        wins = sum(1 for t in self.trade_history if t['win'])
        return wins / len(self.trade_history)
    
    def _calculate_avg_profit(self) -> float:
        """Calculate average profit per trade."""
        if len(self.trade_history) == 0:
            return 0.0
        return sum(t['profit'] for t in self.trade_history) / len(self.trade_history)
    
    def _get_best_strategies(self) -> Dict:
        """Get best performing strategies."""
        strategy_stats = {}
        
        for key, metrics in self.performance_data.items():
            strategy = metrics['strategy']
            
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'total_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0.0,
                }
            
            strategy_stats[strategy]['total_trades'] += metrics['total_trades']
            strategy_stats[strategy]['wins'] += metrics['wins']
            strategy_stats[strategy]['losses'] += metrics['losses']
        
        # Calculate win rates
        for strategy, stats in strategy_stats.items():
            total = stats['total_trades']
            stats['win_rate'] = stats['wins'] / total if total > 0 else 0.0
        
        return strategy_stats
