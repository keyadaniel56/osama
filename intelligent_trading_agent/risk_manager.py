"""
Risk management system - dynamic risk sizing, drawdown protection, position management.
"""

from typing import Dict, Optional
from logger import agent_logger
from config import (
    BASE_STAKE, MAX_DAILY_LOSS, MAX_CONSEC_LOSSES, 
    MAX_DRAWDOWN, MIN_CONFIDENCE, MIN_MARKET_HEALTH,
    MIN_STAKE_AMOUNT
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
        
        # Martingale settings
        self.use_martingale = True  # Enable/disable martingale
        self.martingale_multiplier = 2.0  # Double after loss
        self.max_martingale_steps = 3  # Max times to double (prevents huge losses)
        self.martingale_step = 0  # Current martingale step
        
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
        
        # Check market health (use config value)
        if market_health < MIN_MARKET_HEALTH:
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
        Calculate position size with Martingale strategy.
        
        Martingale: Double stake after each loss to recover losses + profit.
        Resets to base stake after a win.
        """
        if self.use_martingale and self.martingale_step > 0:
            # Apply martingale: multiply base stake by 2^step
            position_size = self.base_stake * (self.martingale_multiplier ** self.martingale_step)
            agent_logger.log_info(
                f"Martingale active: Step {self.martingale_step}, "
                f"Stake: ${position_size:.2f} (Base: ${self.base_stake})"
            )
        else:
            # Normal stake
            position_size = self.base_stake
        
        # Enforce Deriv minimum stake
        position_size = max(position_size, MIN_STAKE_AMOUNT)
        
        # Round to 2 decimal places
        position_size = round(position_size, 2)
        
        self.current_stake = position_size
        return position_size
    
    def record_trade_result(self, stake: float, result: bool, profit_loss: float):
        """Record trade outcome for risk tracking with Martingale."""
        self.trades_today += 1
        self.session_trades.append({
            'stake': stake,
            'result': 'WIN' if result else 'LOSS',
            'profit_loss': profit_loss
        })
        
        if result:
            # WIN: Reset martingale and record profit
            self.daily_profit += abs(profit_loss)
            self.consecutive_losses = 0
            
            if self.martingale_step > 0:
                agent_logger.log_info(
                    f"✓ Martingale WIN! Recovered from {self.martingale_step} losses. "
                    f"Resetting to base stake ${self.base_stake}"
                )
            
            self.martingale_step = 0  # Reset martingale on win
            
        else:
            # LOSS: Increase martingale step and record loss
            self.daily_loss += abs(profit_loss)
            self.consecutive_losses += 1
            
            if self.use_martingale and self.martingale_step < self.max_martingale_steps:
                self.martingale_step += 1
                next_stake = self.base_stake * (self.martingale_multiplier ** self.martingale_step)
                agent_logger.log_warning(
                    f"✗ Loss #{self.consecutive_losses}. "
                    f"Martingale step {self.martingale_step}/{self.max_martingale_steps}. "
                    f"Next stake: ${next_stake:.2f}"
                )
            else:
                if self.martingale_step >= self.max_martingale_steps:
                    agent_logger.log_warning(
                        f"✗ Max martingale steps reached ({self.max_martingale_steps}). "
                        f"Resetting to base stake."
                    )
                    self.martingale_step = 0
        
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
            # Martingale handles stake adjustments automatically
            agent_logger.log_info("Stake adjustment handled by Martingale system")
        
        if recommendations.get('pause_trading'):
            self._pause_trading("Recommended by learning system")
        
        if recommendations.get('increase_confidence_threshold'):
            # Don't increase confidence threshold - let martingale handle risk
            agent_logger.log_info("Confidence threshold adjustment disabled (Martingale active)")
    
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
        
        # Check consecutive losses (pause instead of reducing stake)
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._pause_trading(f"Consecutive loss limit reached ({self.consecutive_losses})")
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
        self.martingale_step = 0  # Reset martingale
        agent_logger.log_info("Daily stats reset")
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics."""
        return {
            'daily_profit': self.daily_profit,
            'daily_loss': self.daily_loss,
            'consecutive_losses': self.consecutive_losses,
            'trades_today': self.trades_today,
            'current_stake': self.current_stake,
            'base_stake': self.base_stake,
            'martingale_step': self.martingale_step,
            'martingale_active': self.martingale_step > 0,
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
