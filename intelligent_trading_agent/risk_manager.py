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
        # WARNING: Martingale is dangerous in random-walk markets.
        # Default is controlled by .env file (USE_MARTINGALE=true in current config)
        self.use_martingale = USE_MARTINGALE  # Respect .env setting
        self.martingale_multiplier = 1.5  # Gentler: 1.5x instead of 2.0x
        self.max_martingale_steps = 2  # Max times to double (prevents huge losses)
        self.martingale_step = 0  # Current martingale step
        
        # === PROFIT TARGET / STOP LOSS SYSTEM ===
        self.take_profit = TAKE_PROFIT      # Stop trading after this profit
        self.stop_loss = STOP_LOSS           # Stop trading after this loss
        self.session_profit = 0.0            # Running profit for current session
        self.peak_profit = 0.0               # Highest profit reached (for trailing stop)
        self.trailing_stop_activated = False  # Has trailing stop been triggered?
        self.trailing_stop_distance = 0.3    # Trail stop at 30% below peak
        
        # === KELLY CRITERION TRACKING ===
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
        
        # Maximum daily trades to prevent over-trading
        self.max_daily_trades = 20
        self.daily_trade_count = 0
        
        # Track whether we've been profitable in the current session
        self.made_profit_this_session = False
        
        # Trading pause state
        self.trading_paused = False
        self.pause_reason = None
        self.pause_tick_count = 0
        self.auto_resume_after_ticks = 500
        self.learning_system_pause = False
    
    def should_trade(self, confidence: float, market_health: float, 
                     is_sure_trend: bool = False, trend_confidence_score: int = 0) -> bool:
        """
        Check if trading should be allowed.
        
        ENHANCED:
        - Hard 2-loss limit: after 2 consecutive losses, MUST pause
        - Sure trend override: if trend is very strong, can trade with slightly lower confidence
        - Trend confidence bonus: high trend confidence reduces the market health requirement
        """
        if self.trading_paused:
            agent_logger.log_warning(f"Trading paused: {self.pause_reason}")
            return False
        
        # === SURE TREND OVERRIDE ===
        # When a "sure trend" is detected (all 5 timeframes aligned, persistent),
        # we can be slightly more lenient with confidence and health requirements
        effective_confidence = confidence
        effective_market_health = market_health
        
        if is_sure_trend and trend_confidence_score >= 80:
            # Sure trend: reduce minimum confidence by 0.05, reduce health requirement by 5
            effective_min_confidence = max(self.min_confidence_threshold - 0.05, 0.60)
            effective_min_health = max(MIN_MARKET_HEALTH - 5, 50)
            agent_logger.log_info(
                f"🎯 Sure trend override: confidence threshold {self.min_confidence_threshold:.2f}→{effective_min_confidence:.2f}, "
                f"health threshold {MIN_MARKET_HEALTH}→{effective_min_health}"
            )
        else:
            effective_min_confidence = self.min_confidence_threshold
            effective_min_health = MIN_MARKET_HEALTH
        
        if effective_confidence < effective_min_confidence:
            return False
        
        if effective_market_health < effective_min_health:
            return False
        
        # Daily trade count limit
        if self.daily_trade_count >= self.max_daily_trades:
            self._pause_trading(f"Daily trade limit reached ({self.max_daily_trades} trades)")
            return False
        
        if self.daily_loss >= self.max_daily_loss:
            self._pause_trading("Daily loss limit reached")
            return False
        
        # === HARD 2-LOSS LIMIT ===
        # After 2 consecutive losses, MUST pause trading regardless of other conditions
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._pause_trading(
                f"HARD LIMIT: {self.consecutive_losses} consecutive losses reached "
                f"(max: {self.max_consecutive_losses}). Must pause to prevent further losses."
            )
            return False
        
        # === GLOBAL 2-LOSS LIMIT ===
        # Tracks losses across market switches to prevent loss-chaining
        if self.global_consecutive_losses >= self.max_global_consecutive_losses:
            self._pause_trading(
                f"HARD GLOBAL LIMIT: {self.global_consecutive_losses} consecutive losses "
                f"across all markets (max: {self.max_global_consecutive_losses}). "
                f"Must pause to prevent further losses."
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
                                trade_direction: str = None, trend_direction: str = None,
                                is_sure_trend: bool = False, trend_confidence_score: int = 0) -> float:
        """
        Calculate position size — starts EXACTLY at the user's configured base_stake.
        
        ENHANCED:
        - Sure trend bonus: increase stake by up to 20% when trend is very strong
        - After 1 loss: reduce stake by 50% (prevent second loss from being bigger)
        - After 2 losses: trading is blocked entirely (handled by should_trade)
        
        The user's base_stake ($0.35 from .env) is the MAX default. The following
        REDUCTIONS are applied only when conditions warrant:
        - Low confidence: reduce stake proportionally to confidence deficit
        - High volatility: reduce stake in turbulent markets  
        - Drawdown: reduce stake when in a losing streak
        - Consecutive losses: reduce stake aggressively after first loss
        """
        # Start EXACTLY at the user's configured base_stake
        position_size = self.base_stake
        
        # === SURE TREND BONUS ===
        # When trend is very strong, we can increase stake slightly
        if is_sure_trend and trend_confidence_score >= 80:
            trend_bonus = 1.0 + min((trend_confidence_score - 80) / 100, 0.20)  # 0-20% bonus
            position_size *= trend_bonus
            agent_logger.log_info(
                f"🎯 Sure trend stake bonus: +{((trend_bonus-1)*100):.0f}% "
                f"(trend_confidence={trend_confidence_score}/100)"
            )
        
        # === LOW CONFIDENCE REDUCTION ===
        if confidence < self.min_confidence_threshold:
            reduction_ratio = confidence / self.min_confidence_threshold
            position_size *= max(0.5, reduction_ratio)
            agent_logger.log_info(
                f"📉 Low confidence reduction: conf={confidence:.2f} < threshold={self.min_confidence_threshold:.2f} "
                f"→ stake ${position_size:.2f} ({(reduction_ratio*100):.0f}% of base)"
            )
        
        # === VOLATILITY REDUCTION ===
        if market_volatility > 1.0:
            position_size *= 0.5
        elif market_volatility > 0.7:
            position_size *= 0.75
        
        # === DRAWDOWN REDUCTION ===
        drawdown = self._calculate_drawdown()
        if drawdown > 5:
            drawdown_penalty = max(0.5, 1 - (drawdown / self.max_drawdown))
            position_size *= drawdown_penalty
            agent_logger.log_info(
                f"📉 Drawdown adjustment: {drawdown:.1f}% → stake multiplier {drawdown_penalty:.2f}"
            )
        
        # === CONSECUTIVE LOSS REDUCTION ===
        # After 1 loss, reduce stake by 50% to prevent the second loss from being bigger
        # After 2 losses, trading is blocked entirely (handled by should_trade)
        if self.consecutive_losses == 1:
            position_size *= 0.50  # Cut stake in half after first loss
            agent_logger.log_info(
                f"⚠️ First loss protection: reducing stake by 50% to ${position_size:.2f}"
            )
        
        # === MARTINGALE OVERRIDE ===
        if self.use_martingale and self.martingale_step > 0:
            if trade_direction and trend_direction and trade_direction != trend_direction:
                agent_logger.log_warning(
                    f"⚠️ Martingale step {self.martingale_step} but trading AGAINST trend "
                    f"(trade={trade_direction}, trend={trend_direction}) — "
                    f"Using base stake ${self.base_stake:.2f}"
                )
                position_size = self.base_stake
            else:
                martingale_stake = self.base_stake * (self.martingale_multiplier ** self.martingale_step)
                position_size = martingale_stake
                position_size = min(position_size, self.base_stake * 4)
                agent_logger.log_info(
                    f"🎰 Martingale: Step {self.martingale_step}, "
                    f"Stake: ${position_size:.2f} (base=${self.base_stake:.2f})"
                )
        
        # Ensure we never go below minimum
        position_size = max(position_size, MIN_STAKE_AMOUNT)
        
        # Round to 2 decimal places
        position_size = round(position_size, 2)
        
        self.current_stake = position_size
        
        if position_size != self.base_stake:
            agent_logger.log_info(
                f"💰 Position size: ${position_size:.2f} (base=${self.base_stake:.2f}, "
                f"conf={confidence:.2f}, vol={market_volatility:.2f})"
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
        self.recent_results.append(result)
        if len(self.recent_results) > self.recent_window:
            self.recent_results.pop(0)
        
        # Update session profit tracking
        self.session_profit += profit_loss
        if self.session_profit > self.peak_profit:
            self.peak_profit = self.session_profit
            self.trailing_stop_activated = True
    
    def record_trade_result(self, stake: float, result: bool, profit_loss: float):
        """Record trade outcome for risk tracking."""
        self.trades_today += 1
        self.daily_trade_count += 1
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
            self.made_profit_this_session = True
            
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
        """Auto-resume pauses after cooldown.
        
        Handles both learning system pauses AND trailing stop pauses.
        Trailing stop pauses auto-resume after a cooldown so the bot
        doesn't stay paused forever after a single drawdown event.
        """
        if not self.trading_paused:
            return
        
        if self.pause_tick_count == 0:
            self.pause_tick_count = tick_count
            pause_type = "learning system" if self.learning_system_pause else "trailing stop"
            agent_logger.log_info(
                f"⏸ {pause_type.capitalize()} pause started at tick {tick_count}. "
                f"Will auto-resume after {self.auto_resume_after_ticks} ticks."
            )
            return
        
        ticks_since_pause = tick_count - self.pause_tick_count
        if ticks_since_pause >= self.auto_resume_after_ticks:
            pause_type = "learning system" if self.learning_system_pause else "trailing stop"
            agent_logger.log_info(
                f"▶ Auto-resuming after {pause_type} pause "
                f"({ticks_since_pause} ticks elapsed, threshold={self.auto_resume_after_ticks})"
            )
            # Reset trailing stop state on auto-resume so the bot can trade again
            self.trailing_stop_activated = False
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
        self.daily_trade_count = 0
        self.session_profit = 0.0
        self.peak_profit = 0.0
        self.trailing_stop_activated = False
        self.trading_paused = False
        self.pause_reason = None
        self.martingale_step = 0
        self.made_profit_this_session = False
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
            'daily_trade_count': self.daily_trade_count,
            'max_daily_trades': self.max_daily_trades,
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
        Trades Today: {metrics['trades_today']} (max: {metrics['max_daily_trades']})
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