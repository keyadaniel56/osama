"""
Risk management system - dynamic risk sizing, drawdown protection, position management.
"""

from typing import Dict, Optional
from logger import agent_logger
from config import (
    BASE_STAKE, MAX_DAILY_LOSS, MAX_CONSEC_LOSSES, 
    MAX_DRAWDOWN, MIN_CONFIDENCE
)


class RiskManager:
    """
    Intelligent risk management system.
    Dynamically adjusts position size and enforces risk constraints.
    """
    
    def __init__(self):
        self.base_stake = BASE_STAKE
        self.current_stake = BASE_STAKE
        self.stake_multiplier = 1.0
        
        # Daily tracking
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.trades_today = 0
        
        # Session tracking
        self.max_portfolio_value = BASE_STAKE * 100  # Initial max
        self.current_portfolio_value = self.max_portfolio_value
        self.session_trades = []
        
        # Risk parameters
        self.max_daily_loss = MAX_DAILY_LOSS
        self.max_consecutive_losses = MAX_CONSEC_LOSSES
        self.max_drawdown = MAX_DRAWDOWN
        self.min_confidence_threshold = MIN_CONFIDENCE
        
        # Trading pause state
        self.trading_paused = False
        self.pause_reason = None
    
    def should_trade(self, confidence: float, market_health: float) -> bool:
        """Check if trading should be allowed."""
        # Check pause state
        if self.trading_paused:
            agent_logger.log_warning(f"Trading paused: {self.pause_reason}")
            return False
        
        # Check confidence threshold
        if confidence < self.min_confidence_threshold:
            return False
        
        # Check market health
        if market_health < 50:
            return False
        
        # Check daily loss limit
        if self.daily_loss >= self.max_daily_loss:
            self._pause_trading("Daily loss limit reached")
            return False
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._pause_trading("Consecutive loss limit reached")
            return False
        
        # Check drawdown
        drawdown = self._calculate_drawdown()
        if drawdown >= self.max_drawdown:
            self._pause_trading("Maximum drawdown reached")
            return False
        
        return True
    
    def calculate_position_size(self, confidence: float, market_volatility: float) -> float:
        """
        Calculate position size based on confidence and volatility.
        Returns stake amount.
        """
        # Base position size
        position_size = self.base_stake
        
        # Adjust for confidence
        confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5 to 1.0
        position_size *= confidence_multiplier
        
        # Reduce position size in high volatility
        volatility_multiplier = max(0.5, 1.0 - (market_volatility * 0.5))
        position_size *= volatility_multiplier
        
        # Apply overall stake multiplier
        position_size *= self.stake_multiplier
        
        # Cap position size
        position_size = min(position_size, self.base_stake * 2)
        position_size = max(position_size, self.base_stake * 0.25)
        
        self.current_stake = position_size
        return position_size
    
    def record_trade_result(self, stake: float, result: bool, profit_loss: float):
        """Record trade outcome for risk tracking."""
        self.trades_today += 1
        self.session_trades.append({
            'stake': stake,
            'result': 'WIN' if result else 'LOSS',
            'profit_loss': profit_loss
        })
        
        if result:
            self.daily_profit += profit_loss
            self.consecutive_losses = 0
        else:
            self.daily_loss += abs(profit_loss)
            self.consecutive_losses += 1
        
        # Update portfolio value
        self.current_portfolio_value += profit_loss
        self.max_portfolio_value = max(self.max_portfolio_value, self.current_portfolio_value)
        
        # Log for debugging
        agent_logger.log_trade({
            'result': 'WIN' if result else 'LOSS',
            'profit_loss': profit_loss,
            'daily_profit': self.daily_profit,
            'daily_loss': self.daily_loss,
            'consecutive_losses': self.consecutive_losses,
            'drawdown': f"{self._calculate_drawdown():.1f}%"
        })
        
        # Check if pause is needed
        self._check_pause_conditions()
    
    def adapt_risk_parameters(self, recommendations: Dict):
        """Adapt risk parameters based on learning system recommendations."""
        if recommendations.get('adjust_stake'):
            multiplier = recommendations.get('new_stake_multiplier', 1.0)
            self.stake_multiplier = multiplier
            agent_logger.log_warning(f"Adjusted stake multiplier to {multiplier}")
        
        if recommendations.get('pause_trading'):
            self._pause_trading("Recommended by learning system")
        
        if recommendations.get('increase_confidence_threshold'):
            old_threshold = self.min_confidence_threshold
            self.min_confidence_threshold = min(0.80, old_threshold + 0.05)
            agent_logger.log_warning(
                f"Increased confidence threshold from {old_threshold} to {self.min_confidence_threshold}"
            )
    
    def resume_trading(self):
        """Resume trading after pause."""
        if self.trading_paused:
            self.trading_paused = False
            agent_logger.log_info("Trading resumed")
    
    def _pause_trading(self, reason: str):
        """Pause trading with reason."""
        if not self.trading_paused:
            self.trading_paused = True
            self.pause_reason = reason
            agent_logger.log_warning(f"Trading paused: {reason}")
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage."""
        if self.max_portfolio_value <= 0:
            return 0.0
        
        drawdown = (self.max_portfolio_value - self.current_portfolio_value) / self.max_portfolio_value * 100
        return max(0.0, drawdown)
    
    def _check_pause_conditions(self):
        """Check if any pause conditions are met."""
        # Check daily loss
        if self.daily_loss >= self.max_daily_loss:
            self._pause_trading("Daily loss limit reached")
            return
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._pause_trading("Consecutive loss limit reached")
            return
        
        # Check drawdown
        if self._calculate_drawdown() >= self.max_drawdown:
            self._pause_trading("Maximum drawdown reached")
            return
    
    def reset_daily_stats(self):
        """Reset daily statistics."""
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.trades_today = 0
        self.trading_paused = False
        self.pause_reason = None
        agent_logger.log_info("Daily stats reset")
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics."""
        return {
            'daily_profit': self.daily_profit,
            'daily_loss': self.daily_loss,
            'consecutive_losses': self.consecutive_losses,
            'trades_today': self.trades_today,
            'current_stake': self.current_stake,
            'stake_multiplier': self.stake_multiplier,
            'drawdown': f"{self._calculate_drawdown():.2f}%",
            'portfolio_value': self.current_portfolio_value,
            'trading_paused': self.trading_paused,
            'pause_reason': self.pause_reason,
        }
    
    def get_status_report(self) -> str:
        """Get formatted status report."""
        metrics = self.get_risk_metrics()
        
        report = f"""
        === Risk Manager Status ===
        Daily Profit: ${metrics['daily_profit']:.2f}
        Daily Loss: ${metrics['daily_loss']:.2f}
        Consecutive Losses: {metrics['consecutive_losses']}/{self.max_consecutive_losses}
        Trades Today: {metrics['trades_today']}
        Drawdown: {metrics['drawdown']}
        Portfolio Value: ${metrics['portfolio_value']:.2f}
        Current Stake: ${metrics['current_stake']:.2f}
        Trading Paused: {metrics['trading_paused']}
        """
        
        if metrics['trading_paused']:
            report += f"Pause Reason: {metrics['pause_reason']}\n"
        
        return report
