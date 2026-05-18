"""
Trading strategy for Rise/Fall contracts.
Manages stake, profit tracking, and risk management with optional martingale.
"""

from dataclasses import dataclass, field
from collections import deque


@dataclass
class Strategy:
    base_stake: float = 1.0
    enable_martingale: bool = False
    martingale_multiplier: float = 2.0
    max_martingale_steps: int = 3
    
    # Statistics
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    total_profit: float = 0.0
    trade_history: list = field(default_factory=list)
    
    # Dynamic confidence adjustment
    recent_losses: deque = field(default_factory=lambda: deque(maxlen=10))
    
    # Martingale tracking
    martingale_step: int = 0
    
    # Internal
    current_stake: float = field(init=False)

    def __post_init__(self):
        self.current_stake = self.base_stake

    @property
    def stake(self) -> float:
        return self.current_stake

    def get_contract_type(self, prediction: int) -> str:
        """
        Get contract type for prediction.
        prediction: 1 = RISE (CALL), 0 = FALL (PUT)
        """
        return "CALL" if prediction == 1 else "PUT"

    def on_win(self, profit: float):
        self.consecutive_losses = 0
        self.consecutive_wins += 1
        self.total_profit += profit
        self.recent_losses.append(False)
        
        # Reset martingale on win
        if self.enable_martingale and self.martingale_step > 0:
            print(f"🎯 Martingale WIN! Resetting stake from ${self.current_stake:.2f} to ${self.base_stake:.2f}")
            self.martingale_step = 0
            self.current_stake = self.base_stake
        
        self.trade_history.append({
            "result": "win",
            "profit": profit,
            "stake": self.current_stake,
            "martingale_step": self.martingale_step
        })
        
        martingale_info = f" (Martingale Step {self.martingale_step})" if self.martingale_step > 0 else ""
        print(f"✅ WIN{martingale_info} | Profit: ${profit:.2f} | Total: ${self.total_profit:.2f}")

    def on_loss(self, loss: float):
        self.consecutive_wins = 0
        self.consecutive_losses += 1
        self.total_profit -= loss
        self.recent_losses.append(True)
        
        self.trade_history.append({
            "result": "loss",
            "profit": -loss,
            "stake": self.current_stake,
            "martingale_step": self.martingale_step
        })
        
        martingale_info = f" (Martingale Step {self.martingale_step})" if self.martingale_step > 0 else ""
        print(f"❌ LOSS{martingale_info} | Loss: ${loss:.2f} | Total: ${self.total_profit:.2f}")
        
        # Apply martingale on loss
        if self.enable_martingale and self.martingale_step < self.max_martingale_steps:
            old_stake = self.current_stake
            self.martingale_step += 1
            self.current_stake = self.base_stake * (self.martingale_multiplier ** self.martingale_step)
            print(f"📈 Martingale: Increasing stake from ${old_stake:.2f} to ${self.current_stake:.2f} (Step {self.martingale_step}/{self.max_martingale_steps})")
        elif self.enable_martingale and self.martingale_step >= self.max_martingale_steps:
            print(f"⚠️ Martingale limit reached! Resetting to base stake ${self.base_stake:.2f}")
            self.martingale_step = 0
            self.current_stake = self.base_stake

    def get_dynamic_confidence(self) -> float:
        """
        Adaptive confidence threshold based on recent performance.
        """
        if len(self.recent_losses) < 3:
            return 0.60
        
        recent_loss_rate = sum(self.recent_losses) / len(self.recent_losses)
        
        if recent_loss_rate > 0.6:
            return 0.80  # Require higher confidence after many losses
        elif recent_loss_rate > 0.4:
            return 0.70
        else:
            return 0.60

    def summary(self) -> str:
        wins = sum(1 for t in self.trade_history if t["result"] == "win")
        losses = len(self.trade_history) - wins
        wr = (wins / len(self.trade_history) * 100) if self.trade_history else 0
        
        martingale_status = ""
        if self.enable_martingale:
            martingale_status = f" | Martingale: {'ON' if self.martingale_step == 0 else f'Step {self.martingale_step}/{self.max_martingale_steps}'}"
        
        return (
            f"Trades: {len(self.trade_history)} | "
            f"W/L: {wins}/{losses} | "
            f"Win rate: {wr:.1f}% | "
            f"P&L: ${self.total_profit:.2f}{martingale_status}"
        )
