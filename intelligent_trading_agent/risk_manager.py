"""
Risk management system - dynamic risk sizing, drawdown protection, position management.
Features:
- Kelly Criterion position sizing (as multiplier on base stake)
- Profit target / trailing stop
- Adaptive confidence thresholds
- Recent performance smoothing
- Drawdown-based stake reduction
"""

from typing import Dict, Optional
from logger import agent_logger
from config import (
    BASE_STAKE, MAX_DAILY_LOSS, MAX_CONSEC_LOSSES, 
    MAX_DRAWDOWN, MIN_CONFIDENCE, MIN_MARKET_HEALTH,
    MIN_STAKE_AMOUNT, MAX_GLOBAL_CONSEC_LOSSES,
    USE_MARTINGALE, TAKE_PROFIT, STOP_LOSS
)


class RiskManager:
    """
    Intelligent risk management system.
    Dynamically adjusts position size and enforces risk constraints.
    Features:
    - Kelly Criterion for optimal position sizing (as multiplier on base stake)
    - Profit target with trailing stop
    - Adaptive confidence based on recent performance
    - Drawdown-based stake reduction
    """
    
    def __init__(self):
        self.base_stake = BASE_STAKE
        self.current_stake = BASE_STAKE
        self.stake_multiplier = 1.0
        
        # Martingale settings (controlled by USE_MARTINGALE in .env)
        self.use_martingale = USE_MARTINGALE
        self.martingale_multiplier = 2.0  # Double after loss
        self.max_martingale_steps = 3  # Max times to double (prevents huge losses)
        self.martingale_step = 0  # Current martingale step
        
        # === PROFIT TARGET / STOP LOSS SYSTEM ===
        self.take_profit = TAKE_PROFIT      # Stop trading after this profit
        self.stop_loss = STOP_LOSS           # Stop trading after this loss
        self.session_profit = 0.0            # Running profit for current session
        self.peak_profit = 0.0               # Highest profit reached (for trailing stop)
        self.trailing_stop_activated = False  # Has trailing stop been triggered?
        self.trailing_stop_distance = 0.3    # Trail stop at 30% below peak
        
        # === KELLY CRITERION TRACKING ===
        # Kelly is applied as a MULTIPLIER on top of the user's base_stake.
        # For example, if base_stake=$0.35 and Kelly suggests 0.14× → position=$0.35*1.14=$0.40
        # This ensures the bot starts at the user's configured stake and adjusts slightly.
        self.kelly_history = []              # Track last N trades for Kelly calc
        self.kelly_window = 50               # Number of trades for Kelly calculation
        self.kelly_base_multiplier = 1.0     # Multiplier applied to base_stake (1.0 = use base_stake as-is)
        
        # === RECENT PERFORMANCE TRACKING ===
        self.recent_results = []             # Last 20 trade results (True=win, False=loss)
        self.recent_window = 20              # Window for adaptive confidence
        self.adapt_confidence = False        # Whether to adapt confidence
        
        # Daily tracking
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.trades_today = 0
        
        # === GLOBAL consecutive loss tracking (across market switches) ===
        self.global_consecutive_losses = 0
        self.max_global_consecutive_losses = MAX_GLOBAL_CONSEC_LOSSES
        
        # Session tracking
        self.max_portfolio_value = BASE_STAKE * 100
        self.current_portfolio_value = self.max_portfolio_value
        self.session_trades = []
        self.total_wins = 0
        self.total_losses = 0
        
        # Risk parameters
        self.max_daily_loss = MAX_DAILY_LOSS
        self.max_consecutive_losses = MAX_CONSEC_LOSSES
        self.max_drawdown = MAX_DRAWDOWN
        self.min_confidence_threshold = MIN_CONFIDENCE
        
        # Trading pause state
        self.trading_paused = False
        self.pause_reason = None
        self.pause_tick_count = 0
        self.auto_resume_after_ticks = 500
        self.learning_system_pause = False
    
    def should_trade(self, confidence: float, market_health: float) -> bool:
        """Check if trading should be allowed."""
        if self.trading_paused:
            agent_logger.log_warning(f"Trading paused: {self.pause_reason}")
            return False
        
        if confidence < self.min_confidence_threshold:
            return False
        
        if market_health < MIN_MARKET_HEALTH:
            return False
        
        if self.daily_loss >= self.max_daily_loss:
            self._pause_trading("Daily loss limit reached")
            return False
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._pause_trading("Consecutive loss limit reached (same market)")
            return False
        
        if self.global_consecutive_losses >= self.max_global_consecutive_losses:
            self._pause_trading(
                f"Global consecutive loss limit reached: "
                f"{self.global_consecutive_losses} losses across all markets "
                f"(max: {self.max_global_consecutive_losses})"
            )
            return False
        
        # === CHECK PROFIT TARGET ===
        if self.take_profit > 0 and self.session_profit >= self.take_profit:
            self._pause_trading(f"Profit target reached: ${self.session_profit:.2f} >= ${self.take_profit}")
            return False
        
        # === CHECK STOP LOSS ===
        if self.stop_loss > 0 and self.session_profit <= -self.stop_loss:
            self._pause_trading(f"Stop loss reached: ${self.session_profit:.2f} <= -${self.stop_loss}")
            return False
        
        # === CHECK TRAILING STOP ===
        if self.trailing_stop_activated:
            current_drawdown_from_peak = self.peak_profit - self.session_profit
            if current_drawdown_from_peak >= self.peak_profit * self.trailing_stop_distance:
                self._pause_trading(
                    f"Trailing stop triggered: Dropped {current_drawdown_from_peak:.2f} from "
                    f"peak ${self.peak_profit:.2f} (threshold: {self.trailing_stop_distance*100:.0f}%)"
                )
                return False
        
        # Check drawdown
        drawdown = self._calculate_drawdown()
        if drawdown >= self.max_drawdown:
            self._pause_trading("Maximum drawdown reached")
            return False
        
        return True
    
    def calculate_position_size(self, confidence: float, market_volatility: float, 
                                trade_direction: str = None, trend_direction: str = None) -> float:
        """
        Calculate position size using Kelly Criterion applied as a multiplier
        on the user's configured base stake.
        
        Kelly Criterion: f* = (p * b - q) / b
        where p = win probability (confidence), q = 1-p, b = odds (assumed 1:1 for Rise/Fall)
        
        For 1:1 binary options: f* = 2p - 1 (optimal fraction)
        
        KEY CHANGE: Kelly is a PERCENTAGE MULTIPLIER on base_stake, not a fraction of a
        virtual bankroll. This ensures the bot starts at the user's configured stake
        and only makes small adjustments based on performance.
        """
        historical_win_rate = self._get_recent_win_rate()
        
        # Blend historical win rate with current confidence
        if self.total_wins + self.total_losses >= 10:
            blended_confidence = 0.6 * historical_win_rate + 0.4 * confidence
        else:
            blended_confidence = confidence  # Rely on signal confidence when new
        
        # Kelly fraction for binary options with ~1:1 payout
        kelly_fraction = max(0, 2 * blended_confidence - 1)
        
        # Use conservative Kelly (25% of full Kelly)
        conservative_kelly = kelly_fraction * 0.25
        
        # Calculate Kelly-based multiplier on base_stake (range: 1.0 to ~1.25)
        # This means: Kelly adjusts stake by at most ~25% above base_stake
        # Example: base_stake=$0.35, kelly_mult=1.14 → position=$0.40
        kelly_multiplier = 1.0 + conservative_kelly
        
        # Start from the user's configured base_stake
        position_size = self.base_stake
        
        # Apply Kelly multiplier (slight adjustment above base)
        position_size *= kelly_multiplier
        
        # Apply volatility adjustment: reduce stake in high volatility
        if market_volatility > 1.0:
            position_size *= 0.5  # Half position in high volatility
        elif market_volatility > 0.7:
            position_size *= 0.75 # 75% in elevated volatility
        
        # Apply drawdown adjustment: reduce stake if in drawdown
        drawdown = self._calculate_drawdown()
        if drawdown > 5:
            drawdown_penalty = max(0.5, 1 - (drawdown / self.max_drawdown))
            position_size *= drawdown_penalty
            agent_logger.log_info(
                f"📉 Drawdown adjustment: {drawdown:.1f}% → stake multiplier {drawdown_penalty:.2f}"
            )
        
        # === MARTINGALE OVERRIDE ===
        if self.use_martingale and self.martingale_step > 0:
            # Only apply martingale if trading WITH the trend
            if trade_direction and trend_direction and trade_direction != trend_direction:
                # Trading against trend - use Kelly-based position, not doubled
                agent_logger.log_warning(
                    f"⚠️ Martingale step {self.martingale_step} but trading AGAINST trend "
                    f"(trade={trade_direction}, trend={trend_direction}) — "
                    f"Using base-based stake ${position_size:.2f} instead of doubled"
                )
            else:
                # Martingale doubles from base, but cap at reasonable level
                martingale_stake = self.base_stake * (self.martingale_multiplier ** self.martingale_step)
                # Use the higher of martingale and Kelly-based, but cap at 4× base
                position_size = max(position_size, martingale_stake)
                position_size = min(position_size, self.base_stake * 4)
                agent_logger.log_info(
                    f"🎰 Martingale: Step {self.martingale_step}, "
                    f"Stake: ${position_size:.2f} (Martingale: ${martingale_stake:.2f})"
                )
        
        # Enforce minimum stake
        position_size = max(position_size, MIN_STAKE_AMOUNT)
        
        # Round to 2 decimal places
        position_size = round(position_size, 2)
        
        self.current_stake = position_size
        
        # Log for debugging
        if position_size != self.base_stake:
            agent_logger.log_info(
                f"💰 Position size: ${position_size:.2f} (base=${self.base_stake:.2f}, "
                f"kelly_mult={kelly_multiplier:.3f}, volatility_adj={market_volatility:.2f})"
            )
        
        return position_size
    
    def _get_recent_win_rate(self) -> float:
        """Get win rate from recent trades (sliding window)."""
        if not self.recent_results:
            return 0.5  # Default 50% when no data
        
        window = min(len(self.recent_results), self.recent_window)
        recent = self.recent_results[-window:]
        wins = sum(1 for r in recent if r)
        return wins / window if window > 0 else 0.5
    
    def _update_kelly_statistics(self, result: bool, profit_loss: float):
        """Update Kelly Criterion statistics after each trade."""
        # Add to recent results for win rate calculation
        self.recent_results.append(result)
        if len(self.recent_results) > self.recent_window:
            self.recent_results.pop(0)
        
        # Update session profit tracking
        self.session_profit += profit_loss
        if self.session_profit > self.peak_profit:
            self.peak_profit = self.session_profit
            self.trailing_stop_activated = True  # Activate once we've been profitable
    
    def record_trade_result(self, stake: float, result: bool, profit_loss: float):
        """Record trade outcome for risk tracking."""
        self.trades_today += 1
        self.session_trades.append({
            'stake': stake,
            'result': 'WIN' if result else 'LOSS',
            'profit_loss': profit_loss
        })
        
        # Update Kelly statistics
        self._update_kelly_statistics(result, profit_loss)
        
        if result:
            self.daily_profit += abs(profit_loss)
            self.total_wins += 1
            self.consecutive_losses = 0
            self.global_consecutive_losses = 0
            
            if self.martingale_step > 0:
                agent_logger.log_info(
                    f"✓ Martingale WIN! Recovered from {self.martingale_step} losses. "
                    f"Resetting to base stake ${self.base_stake}"
                )
            
            self.martingale_step = 0
            
        else:
            self.daily_loss += abs(profit_loss)
            self.total_losses += 1
            self.consecutive_losses += 1
            self.global_consecutive_losses += 1
            
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
            
            if self.global_consecutive_losses >= self.max_global_consecutive_losses - 1:
                agent_logger.log_warning(
                    f"⚠️ GLOBAL LOSS STREAK: {self.global_consecutive_losses}/{self.max_global_consecutive_losses} "
                    f"losses across all markets. Trading will be stopped if this continues."
                )
        
        self.current_portfolio_value += profit_loss
        self.max_portfolio_value = max(self.max_portfolio_value, self.current_portfolio_value)
        
        # Log detailed stats
        agent_logger.log_trade({
            'result': 'WIN' if result else 'LOSS',
            'profit_loss': profit_loss,
            'daily_profit': self.daily_profit,
            'daily_loss': self.daily_loss,
            'session_profit': self.session_profit,
            'peak_profit': self.peak_profit,
            'consecutive_losses': self.consecutive_losses,
            'global_consecutive_losses': self.global_consecutive_losses,
            'win_rate': f"{self._get_recent_win_rate():.1%}",
            'kelly_fraction': self._calculate_kelly_fraction(),
            'drawdown': f"{self._calculate_drawdown():.1f}%"
        })
        
        self._check_pause_conditions()
    
    def _calculate_kelly_fraction(self) -> float:
        """Calculate the current Kelly fraction for a 1:1 bet (as multiplier)."""
        win_rate = self._get_recent_win_rate()
        kelly = max(0, 2 * win_rate - 1)
        return kelly * 0.25
    
    def set_martingale_enabled(self, enabled: bool):
        """Enable or disable martingale strategy."""
        old_value = self.use_martingale
        self.use_martingale = enabled
        if enabled != old_value:
            if not enabled:
                self.martingale_step = 0
                agent_logger.log_info("⚙️ Martingale DISABLED by user - reset to base stake")
            else:
                agent_logger.log_info("⚙️ Martingale ENABLED by user")
    
    def adapt_risk_parameters(self, recommendations: Dict):
        """Adapt risk parameters based on learning system recommendations."""
        if recommendations.get('adjust_stake'):
            agent_logger.log_info("Stake adjustment handled by Martingale + Kelly system")
        
        if recommendations.get('pause_trading'):
            self._pause_trading("Recommended by learning system", from_learning_system=True)
        
        if recommendations.get('increase_confidence_threshold'):
            # Dynamically adjust confidence threshold based on recent performance
            win_rate = self._get_recent_win_rate()
            if win_rate < 0.4:
                # Increase threshold when losing - be more selective
                self.min_confidence_threshold = min(MIN_CONFIDENCE + 0.1, 0.85)
                agent_logger.log_info(
                    f"⚠️ Win rate low ({win_rate:.1%}) - Raising confidence threshold "
                    f"to {self.min_confidence_threshold:.2f}"
                )
            elif win_rate > 0.6:
                # Lower threshold when winning - can be more aggressive
                self.min_confidence_threshold = max(MIN_CONFIDENCE - 0.05, 0.55)
                agent_logger.log_info(
                    f"✅ Win rate high ({win_rate:.1%}) - Lowering confidence threshold "
                    f"to {self.min_confidence_threshold:.2f}"
                )
    
    def resume_trading(self):
        """Resume trading after pause."""
        if self.trading_paused:
            self.trading_paused = False
            self.pause_reason = None
            self.learning_system_pause = False
            self.pause_tick_count = 0
            agent_logger.log_info("▶ Trading resumed")
    
    def check_auto_resume(self, tick_count: int):
        """Auto-resume learning system pauses after cooldown."""
        if not self.trading_paused:
            return
        
        if not self.learning_system_pause:
            return
        
        if self.pause_tick_count == 0:
            self.pause_tick_count = tick_count
            agent_logger.log_info(
                f"⏸ Learning system pause started at tick {tick_count}. "
                f"Will auto-resume after {self.auto_resume_after_ticks} ticks."
            )
            return
        
        ticks_since_pause = tick_count - self.pause_tick_count
        if ticks_since_pause >= self.auto_resume_after_ticks:
            agent_logger.log_info(
                f"▶ Auto-resuming after learning system pause "
                f"({ticks_since_pause} ticks elapsed, threshold={self.auto_resume_after_ticks})"
            )
            self.resume_trading()
    
    def _pause_trading(self, reason: str, from_learning_system: bool = False):
        """Pause trading with reason."""
        if not self.trading_paused:
            self.trading_paused = True
            self.pause_reason = reason
            self.learning_system_pause = from_learning_system
            agent_logger.log_warning(f"Trading paused: {reason}")
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage."""
        if self.max_portfolio_value <= 0:
            return 0.0
        
        drawdown = (self.max_portfolio_value - self.current_portfolio_value) / self.max_portfolio_value * 100
        return max(0.0, drawdown)
    
    def _check_pause_conditions(self):
        """Check if any pause conditions are met."""
        if self.daily_loss >= self.max_daily_loss:
            self._pause_trading("Daily loss limit reached")
            return
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._pause_trading(f"Consecutive loss limit reached ({self.consecutive_losses})")
            return
        
        if self.global_consecutive_losses >= self.max_global_consecutive_losses:
            self._pause_trading(
                f"Global consecutive loss limit reached "
                f"({self.global_consecutive_losses} losses across all markets)"
            )
            return
        
        # Profit target reached
        if self.take_profit > 0 and self.session_profit >= self.take_profit:
            self._pause_trading(f"Profit target reached: ${self.session_profit:.2f}")
            return
        
        # Stop loss reached
        if self.stop_loss > 0 and self.session_profit <= -self.stop_loss:
            self._pause_trading(f"Stop loss reached: ${self.session_profit:.2f}")
            return
        
        if self._calculate_drawdown() >= self.max_drawdown:
            self._pause_trading("Maximum drawdown reached")
            return
    
    def reset_daily_stats(self):
        """Reset daily statistics."""
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.global_consecutive_losses = 0
        self.trades_today = 0
        self.session_profit = 0.0
        self.peak_profit = 0.0
        self.trailing_stop_activated = False
        self.trading_paused = False
        self.pause_reason = None
        self.martingale_step = 0
        agent_logger.log_info("Daily stats reset")
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics."""
        return {
            'daily_profit': self.daily_profit,
            'daily_loss': self.daily_loss,
            'session_profit': self.session_profit,
            'peak_profit': self.peak_profit,
            'trailing_stop_active': self.trailing_stop_activated,
            'consecutive_losses': self.consecutive_losses,
            'global_consecutive_losses': self.global_consecutive_losses,
            'trades_today': self.trades_today,
            'current_stake': self.current_stake,
            'base_stake': self.base_stake,
            'martingale_step': self.martingale_step,
            'martingale_active': self.martingale_step > 0,
            'use_martingale': self.use_martingale,
            'kelly_fraction': self._calculate_kelly_fraction(),
            'recent_win_rate': self._get_recent_win_rate(),
            'drawdown': self._calculate_drawdown(),
            'max_drawdown': self.max_drawdown,
            'portfolio_value': self.current_portfolio_value,
            'trading_paused': self.trading_paused,
            'pause_reason': self.pause_reason,
            'adaptive_confidence_threshold': self.min_confidence_threshold,
        }
    
    def get_status_report(self) -> str:
        """Get formatted status report."""
        metrics = self.get_risk_metrics()
        
        report = f"""
        === Risk Manager Status ===
        Daily P&L: ${metrics['daily_profit']:.2f} / ${metrics['daily_loss']:.2f}
        Session P&L: ${metrics['session_profit']:.2f} (Peak: ${metrics['peak_profit']:.2f})
        Consecutive Losses: {metrics['consecutive_losses']}/{self.max_consecutive_losses}
        Global Consecutive Losses: {metrics['global_consecutive_losses']}/{self.max_global_consecutive_losses}
        Trades Today: {metrics['trades_today']}
        Win Rate (recent): {metrics['recent_win_rate']:.1%}
        Drawdown: {metrics['drawdown']:.1f}%
        Current Stake: ${metrics['current_stake']:.2f} (base: ${metrics['base_stake']:.2f})
        Martingale: {'ENABLED' if metrics.get('use_martingale', True) else 'DISABLED'} (step {metrics['martingale_step']})
        Confidence Threshold: {metrics['adaptive_confidence_threshold']:.2f}
        Trailing Stop: {'ACTIVE' if metrics['trailing_stop_active'] else 'NOT YET'}
        Trading Paused: {metrics['trading_paused']}
        """
        
        if metrics['trading_paused']:
            report += f"Pause Reason: {metrics['pause_reason']}\n"
        
        return report