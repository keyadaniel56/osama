"""
Trading strategy logic.
Cycles between three trading phases:
Phase 1: OVER 0 / UNDER 9 (4 trades each)
Phase 2: OVER 1 / UNDER 8 (2 trades each)
Recovery: UNDER 5 / OVER 4 (3 trades each) with martingale strategy

Recovery mode is triggered after 1 loss in the last 8 trades for immediate recovery.
Uses martingale to recover losses. Stakes double after each loss up to 8x base stake.
After completing recovery phase, returns to the previous phase.
"""

from dataclasses import dataclass, field
from enum import Enum
from theme import print_recovery_trigger


class TradingPhase(Enum):
    PHASE_2 = "phase_2"  # Only phase now: OVER 1 / UNDER 8
    RECOVERY = "recovery"  # UNDER 5 / OVER 4 with martingale


class TradeType(Enum):
    OVER = "over"
    UNDER = "under"


@dataclass
class Strategy:
    base_stake: float = 1.0
    phase: TradingPhase = TradingPhase.PHASE_2  # Start with PHASE_2 only
    current_trade_type: TradeType = TradeType.OVER
    
    # Trade counters for current phase
    over_trades_completed: int = 0
    under_trades_completed: int = 0
    
    # Phase targets - only PHASE_2 now
    phase_2_target: int = 2  # 2 trades each for OVER 1 / UNDER 8
    recovery_target: int = 3  # 3 trades each for UNDER 5 / OVER 4
    
    # Recovery phase settings
    recovery_trigger_losses: int = 1  # Trigger recovery after 1 loss (immediate)
    recovery_lookback_window: int = 3  # Look at last 3 trades for loss count
    recovery_max_stake_multiplier: float = 8.0  # Max 8x base stake
    recovery_stake_multiplier: float = 1.0  # Current martingale multiplier
    recovery_max_total_trades: int = 10  # Max total trades in recovery before forced exit
    recovery_start_profit: float = field(init=False, default=0.0)  # Profit when recovery started
    
    # Trading statistics
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    total_profit: float = 0.0
    trade_history: list = field(default_factory=list)
    
    # Phase barriers - only PHASE_2 and RECOVERY
    PHASE_2_OVER = 4
    PHASE_2_UNDER = 5
    RECOVERY_OVER = 4
    RECOVERY_UNDER = 5
    
    # Internal
    current_stake: float = field(init=False)
    needs_market_reanalysis: bool = field(init=False, default=False)
    _pre_recovery_phase: TradingPhase = field(init=False, default=None)

    def __post_init__(self):
        self.current_stake = self.base_stake
        self._pre_recovery_phase = None

    @property
    def stake(self) -> float:
        return self.current_stake

    def get_current_target(self) -> int:
        """Get the target number of trades for current phase"""
        if self.phase == TradingPhase.PHASE_2:
            return self.phase_2_target
        else:  # RECOVERY
            return self.recovery_target

    def get_barriers(self) -> dict:
        """Get current phase barriers"""
        if self.phase == TradingPhase.PHASE_2:
            return {"over": self.PHASE_2_OVER, "under": self.PHASE_2_UNDER}
        else:  # RECOVERY
            return {"over": self.RECOVERY_OVER, "under": self.RECOVERY_UNDER}

    def should_trade_type(self, prediction: int) -> bool:
        """Check if we should trade this prediction type based on current targets"""
        target = self.get_current_target()
        
        if prediction == 1:  # OVER trade
            return self.over_trades_completed < target
        else:  # UNDER trade
            return self.under_trades_completed < target

    def get_contract_type(self, prediction: int) -> str:
        """Get contract type for prediction"""
        barriers = self.get_barriers()
        if prediction == 1:
            return f"DIGITOVER_{barriers['over']}"
        return f"DIGITUNDER_{barriers['under']}"

    def _check_recovery_trigger(self) -> bool:
        """Check if we should enter recovery mode based on recent losses"""
        if self.phase == TradingPhase.RECOVERY:
            return False  # Already in recovery
            
        # Count losses in recent trades
        recent_trades = self.trade_history[-self.recovery_lookback_window:] if len(self.trade_history) >= self.recovery_lookback_window else self.trade_history
        recent_losses = sum(1 for trade in recent_trades if trade["result"] == "loss")
        
        print(f"[Strategy] Checking recovery trigger: {recent_losses} losses in last {len(recent_trades)} trades (trigger at {self.recovery_trigger_losses})")
            
        if recent_losses >= self.recovery_trigger_losses:
            print(f"[Strategy] 🚨 RECOVERY TRIGGERED! {recent_losses} >= {self.recovery_trigger_losses}")
            print_recovery_trigger()
            
            # Save current phase and profit level to return to later
            self._pre_recovery_phase = self.phase
            self.recovery_start_profit = self.total_profit  # Track profit when recovery started
            
            # Switch to recovery phase
            self.phase = TradingPhase.RECOVERY
            self.over_trades_completed = 0
            self.under_trades_completed = 0
            self.recovery_stake_multiplier = 2.0  # Start with 2x base stake
            self.current_stake = self.base_stake * self.recovery_stake_multiplier
            self.needs_market_reanalysis = True
            
            print(f"[Strategy] ✅ Switched to RECOVERY mode - stake now ${self.current_stake:.2f}")
            print(f"[Strategy] 📊 Recovery baseline profit: ${self.recovery_start_profit:.2f}")
            return True
        else:
            print(f"[Strategy] ❌ Recovery not triggered - need {self.recovery_trigger_losses - recent_losses} more losses")
        return False

    def _exit_recovery_mode(self):
        """Exit recovery mode and return to previous phase"""
        previous_phase = self._pre_recovery_phase.value if self._pre_recovery_phase else "UNKNOWN"
        print(f"[Strategy] 🎯 RECOVERY COMPLETED - returning to {previous_phase}")
        
        # Return to previous phase
        if self._pre_recovery_phase:
            self.phase = self._pre_recovery_phase
            print(f"[Strategy] ✅ Successfully returned to {self.phase.value.upper()}")
        else:
            # Fallback to Phase 2 if no previous phase saved
            self.phase = TradingPhase.PHASE_2
            print(f"[Strategy] ⚠️ No previous phase saved, defaulting to PHASE_2")
            
        self.over_trades_completed = 0
        self.under_trades_completed = 0
        self.recovery_stake_multiplier = 1.0
        self.current_stake = self.base_stake
        self.consecutive_losses = 0  # Reset loss counter
        self.needs_market_reanalysis = True
        
        print(f"[Strategy] 🔄 Phase reset: OVER: 0/{self.get_current_target()} | UNDER: 0/{self.get_current_target()} | Stake: ${self.current_stake:.2f}")

    def _apply_martingale(self):
        """Apply martingale strategy in recovery mode"""
        if self.phase != TradingPhase.RECOVERY:
            return
            
        # Double the stake multiplier after each loss, up to max
        old_multiplier = self.recovery_stake_multiplier
        self.recovery_stake_multiplier = min(
            self.recovery_stake_multiplier * 2.0,
            self.recovery_max_stake_multiplier
        )
        old_stake = self.current_stake
        self.current_stake = self.base_stake * self.recovery_stake_multiplier
        
        print(f"[Strategy] Martingale: Stake increased from ${old_stake:.2f} to ${self.current_stake:.2f} (multiplier: {old_multiplier}x → {self.recovery_stake_multiplier}x)")

    def _reset_martingale(self):
        """Reset martingale after a win in recovery mode"""
        if self.phase != TradingPhase.RECOVERY:
            return
            
        self.recovery_stake_multiplier = 2.0  # Reset to initial recovery multiplier
        self.current_stake = self.base_stake * self.recovery_stake_multiplier
        
        print(f"[Strategy] Martingale reset after win: Stake reset to ${self.current_stake:.2f}")
    def _check_phase_completion(self) -> bool:
        """Check if current phase is completed and switch if needed"""
        target = self.get_current_target()
        
        # Special recovery exit logic - exit when recovered OR all trades completed
        if self.phase == TradingPhase.RECOVERY:
            total_recovery_trades = self.over_trades_completed + self.under_trades_completed
            recovery_profit = self.total_profit - self.recovery_start_profit
            
            # Exit if we've recovered the losses (profit since recovery started > 0)
            if recovery_profit > 0:
                print(f"[Strategy] 💰 Recovery successful! Recovery profit: ${recovery_profit:.2f} (Total: ${self.total_profit:.2f})")
                self._exit_recovery_mode()
                return True
            # Exit if maximum recovery trades reached (safety limit)
            elif total_recovery_trades >= self.recovery_max_total_trades:
                print(f"[Strategy] ⚠️ Recovery limit reached ({total_recovery_trades} trades)")
                self._exit_recovery_mode()
                return True
            # Exit if all trades completed (original logic)
            elif self.over_trades_completed >= target and self.under_trades_completed >= target:
                print(f"[Strategy] 🔄 Recovery trades completed (recovery profit: ${recovery_profit:.2f})")
                self._exit_recovery_mode()
                return True
            # Safety exit: if one side is complete and we have significant losses, exit recovery
            elif (self.over_trades_completed >= target or self.under_trades_completed >= target) and recovery_profit < -1.5:
                print(f"[Strategy] 🚨 Recovery safety exit - one side complete with significant losses")
                print(f"[Strategy] 📊 OVER: {self.over_trades_completed}/{target} | UNDER: {self.under_trades_completed}/{target}")
                print(f"[Strategy] 💸 Recovery profit: ${recovery_profit:.2f} - exiting to prevent further losses")
                self._exit_recovery_mode()
                return True
            return False
        
        # Normal phase completion logic - since we only have PHASE_2, just reset counters
        if self.over_trades_completed >= target and self.under_trades_completed >= target:
            print(f"[Strategy] 🔄 PHASE_2 cycle completed - resetting counters")
            # Reset counters to continue PHASE_2
            self.over_trades_completed = 0
            self.under_trades_completed = 0
            self.needs_market_reanalysis = True
            return True
        return False

    def on_win(self, profit: float):
        self.consecutive_losses = 0
        self.consecutive_wins += 1
        self.total_profit += profit
        
        # Reset martingale in recovery mode
        if self.phase == TradingPhase.RECOVERY:
            self._reset_martingale()
        
        # Update trade counters based on last trade type
        if hasattr(self, '_last_trade_type'):
            if self._last_trade_type == TradeType.OVER:
                self.over_trades_completed += 1
            else:
                self.under_trades_completed += 1
        
        self.trade_history.append({
            "result": "win", "profit": profit,
            "phase": self.phase.value, "stake": self.current_stake,
            "over_completed": self.over_trades_completed,
            "under_completed": self.under_trades_completed
        })

        phase_name = f"{self.phase.value.upper()}"
        if self.phase == TradingPhase.RECOVERY:
            phase_name += f" (UNDER {self.RECOVERY_UNDER} / OVER {self.RECOVERY_OVER})"
        else:  # PHASE_2
            phase_name += f" (OVER {self.PHASE_2_OVER} / UNDER {self.PHASE_2_UNDER})"

        print(f"[Strategy] WIN — {phase_name} | "
              f"OVER: {self.over_trades_completed}/{self.get_current_target()} | "
              f"UNDER: {self.under_trades_completed}/{self.get_current_target()}")
        
        # Check if phase should switch
        self._check_phase_completion()

    def on_loss(self, loss: float):
        self.consecutive_wins = 0
        self.consecutive_losses += 1
        self.total_profit -= loss
        
        # Update trade counters based on last trade type
        if hasattr(self, '_last_trade_type'):
            if self._last_trade_type == TradeType.OVER:
                self.over_trades_completed += 1
            else:
                self.under_trades_completed += 1
        
        self.trade_history.append({
            "result": "loss", "profit": -loss,
            "phase": self.phase.value, "stake": self.current_stake,
            "over_completed": self.over_trades_completed,
            "under_completed": self.under_trades_completed
        })

        phase_name = f"{self.phase.value.upper()}"
        if self.phase == TradingPhase.RECOVERY:
            phase_name += f" (UNDER {self.RECOVERY_UNDER} / OVER {self.RECOVERY_OVER})"
        else:  # PHASE_2
            phase_name += f" (OVER {self.PHASE_2_OVER} / UNDER {self.PHASE_2_UNDER})"

        print(f"[Strategy] LOSS — {phase_name} | "
              f"OVER: {self.over_trades_completed}/{self.get_current_target()} | "
              f"UNDER: {self.under_trades_completed}/{self.get_current_target()}")
        
        # Apply martingale in recovery mode
        if self.phase == TradingPhase.RECOVERY:
            self._apply_martingale()
        
        # Recovery mode disabled — flat staking only
        # Martingale on even-money contracts is mathematically ruinous
        recovery_triggered = False
        
        # Only check phase completion if recovery wasn't triggered
        if not recovery_triggered:
            self._check_phase_completion()

    def force_exit_recovery(self, reason: str = "Manual exit"):
        """Force exit from recovery mode - use when bot is stuck"""
        if self.phase == TradingPhase.RECOVERY:
            recovery_profit = self.total_profit - self.recovery_start_profit
            print(f"[Strategy] 🚨 FORCED RECOVERY EXIT: {reason}")
            print(f"[Strategy] 📊 Recovery profit: ${recovery_profit:.2f}")
            print(f"[Strategy] 📊 OVER: {self.over_trades_completed}/{self.get_current_target()} | UNDER: {self.under_trades_completed}/{self.get_current_target()}")
            self._exit_recovery_mode()
            return True
        return False

    def record_trade_attempt(self, prediction: int):
        """Record which trade type we're attempting"""
        self._last_trade_type = TradeType.OVER if prediction == 1 else TradeType.UNDER

    def summary(self) -> str:
        wins = sum(1 for t in self.trade_history if t["result"] == "win")
        losses = len(self.trade_history) - wins
        wr = (wins / len(self.trade_history) * 100) if self.trade_history else 0
        target = self.get_current_target()
        
        phase_info = f"{self.phase.value}"
        if self.phase == TradingPhase.RECOVERY:
            phase_info += f" (martingale: {self.recovery_stake_multiplier}x)"
        
        return (
            f"Phase: {phase_info} | "
            f"OVER: {self.over_trades_completed}/{target} | "
            f"UNDER: {self.under_trades_completed}/{target} | "
            f"Trades: {len(self.trade_history)} | "
            f"W/L: {wins}/{losses} | "
            f"Win rate: {wr:.1f}% | "
            f"Stake: ${self.current_stake:.2f} | "
            f"P&L: {self.total_profit:.2f}"
        )
