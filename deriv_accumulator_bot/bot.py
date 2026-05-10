"""
Accumulator Bot for Deriv.

Strategy:
- Wait for low-volatility, trending (Hurst > 0.5) market conditions
- Enter accumulator at configured growth rate (default 1%)
- Exit when:
    1. Target tick count reached (take profit by selling)
    2. Accumulated profit % target hit (sell early)
    3. Contract knocked out (loss — wait for cooldown before re-entry)
- Risk management: stop loss on total session P&L, daily trade limit
"""

import time
import os
import threading
from collections import deque
from dotenv import load_dotenv

from client import DerivClient
from volatility import VolatilityAnalyzer

load_dotenv()

# --- Config ---
API_TOKEN   = os.getenv("DERIV_API_TOKEN", "")
APP_ID      = os.getenv("DERIV_APP_ID", "1089")
SYMBOL      = os.getenv("SYMBOL", "R_10")
STAKE       = float(os.getenv("STAKE", "1.0"))
GROWTH_RATE = float(os.getenv("GROWTH_RATE", "0.01"))   # 1% default
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", "10.0"))   # session P&L target
STOP_LOSS   = float(os.getenv("STOP_LOSS", "5.0"))      # session max loss
TARGET_TICKS = int(os.getenv("TARGET_TICKS", "3"))      # sell after this many ticks

# Cooldown ticks after a knockout before re-entering
KNOCKOUT_COOLDOWN = 50
# Minimum ticks to observe before entering after session start
WARMUP_TICKS = 30
# Stop after this many winning trades per session
WIN_TARGET = int(os.getenv("WIN_TARGET", "3"))


class AccumulatorBot:
    def __init__(self):
        self.client   = DerivClient(APP_ID, API_TOKEN, SYMBOL)
        self.analyzer = VolatilityAnalyzer(window=30)

        self.tick_count        = 0
        self.session_profit    = 0.0
        self.total_trades      = 0
        self.wins              = 0   # trades sold for profit
        self.knockouts         = 0   # contracts knocked out

        self._in_trade         = False
        self._ticks_in_trade   = 0
        self._current_profit   = 0.0
        self._cooldown_ticks   = 0
        self._stopped          = False
        self._sell_triggered   = False   # prevents repeated sell calls per trade
        self._trade_lock       = threading.Lock()

        # Recent trade history for display
        self._history          = deque(maxlen=20)

        self.client.on_tick             = self._on_tick
        self.client.on_contract_update  = self._on_contract_update
        self.client.on_contract_sold    = self._on_contract_sold
        self.client.on_buy_error        = self._on_buy_error

    def run(self):
        print("=" * 60)
        print("   DERIV ACCUMULATOR BOT")
        print(f"   Symbol: {SYMBOL} | Growth: {GROWTH_RATE*100:.0f}% | Stake: ${STAKE:.2f}")
        print(f"   Target: {TARGET_TICKS} ticks | TP: ${TAKE_PROFIT} | SL: -${STOP_LOSS}")
        print(f"   Win target: {WIN_TARGET} wins then stop")
        print("=" * 60)

        self.client.connect()

        timeout = 15
        while not self.client.authorized and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5

        if not self.client.authorized:
            raise RuntimeError("Authorization failed. Check your API token.")

        print(f"[Bot] Warming up — collecting {WARMUP_TICKS} ticks before trading...")

        try:
            while not self._stopped:
                time.sleep(5)
                self._print_status()
        except KeyboardInterrupt:
            print("\n[Bot] Stopped by user.")
            if self._in_trade:
                print("[Bot] Selling active contract before exit...")
                self.client.sell_contract()
                time.sleep(3)
            self._print_summary()

    # ------------------------------------------------------------------ #
    #  Tick handler                                                        #
    # ------------------------------------------------------------------ #

    def _on_tick(self, price: float):
        self.tick_count += 1
        self.analyzer.add_tick(price)

        # Cooldown countdown after knockout
        if self._cooldown_ticks > 0:
            self._cooldown_ticks -= 1
            return

        # Session-level risk checks
        if self._stopped:
            return

        if self.session_profit >= TAKE_PROFIT:
            print(f"[Bot] 🎯 Take profit reached! Session P&L: ${self.session_profit:.4f}")
            self._stopped = True
            return

        if self.session_profit <= -STOP_LOSS:
            print(f"[Bot] 🛑 Stop loss hit! Session P&L: ${self.session_profit:.4f}")
            self._stopped = True
            return

        # Track ticks inside active trade
        with self._trade_lock:
            if self._in_trade:
                self._ticks_in_trade += 1

                # Exit after TARGET_TICKS — sell to lock in profit (only once)
                if self._ticks_in_trade >= TARGET_TICKS and not self._sell_triggered:
                    self._sell_triggered = True
                    print(f"[Bot] ⏱ Target ticks reached ({TARGET_TICKS}). Selling to lock profit...")
                    self.client.sell_contract()
                return

        # Not in trade — check if we should enter
        if self.tick_count < WARMUP_TICKS:
            return

        metrics = self.analyzer.analyze()
        safe, reason = self.analyzer.is_safe_to_enter(metrics, GROWTH_RATE)

        if safe:
            self._enter_trade(metrics)
        else:
            if self.tick_count % 15 == 0:
                print(f"[Bot] Waiting — {reason}")

    # ------------------------------------------------------------------ #
    #  Contract callbacks                                                  #
    # ------------------------------------------------------------------ #

    def _on_contract_update(self, status: str, profit: float, current_value: float):
        """Called on every tick while contract is alive."""
        with self._trade_lock:
            self._current_profit = profit

        # ULTRA DEFENSIVE - exit at the slightest profit to avoid knockouts
        profit_pct = (profit / STAKE) * 100 if STAKE > 0 else 0
        
        # Exit at just 1% profit - extremely fast
        if profit_pct >= 1.0 and not self._sell_triggered:
            self._sell_triggered = True
            print(f"[Bot] 💰 Quick profit ({profit_pct:.1f}%). Selling...")
            self.client.sell_contract()
        
        # Exit with ANY profit after just 2 ticks - don't wait at all
        elif profit > 0.01 and self._ticks_in_trade >= 2 and not self._sell_triggered:
            self._sell_triggered = True
            print(f"[Bot] ⚡ Locking in ${profit:.4f} after {self._ticks_in_trade} ticks")
            self.client.sell_contract()
        
        # Emergency exit: if we're at 3 ticks, exit anyway - RETRY if previous sell failed
        elif self._ticks_in_trade >= 3:
            if not self._sell_triggered:
                self._sell_triggered = True
                print(f"[Bot] ⚠️ Emergency exit at tick {self._ticks_in_trade} - P&L: ${profit:.4f}")
                self.client.sell_contract()
            # If we're past tick 4 and still in trade, force retry
            elif self._ticks_in_trade >= 4:
                print(f"[Bot] 🔄 Retry selling at tick {self._ticks_in_trade} - P&L: ${profit:.4f}")
                self.client.sell_contract(force_retry=True)

    def _on_contract_sold(self, profit: float):
        """Called when contract closes (sold or knocked out)."""
        with self._trade_lock:
            self._in_trade = False
            self._ticks_in_trade = 0
            self._current_profit = 0.0
            self._sell_triggered = False

        self.session_profit += profit
        self.total_trades += 1

        if profit > 0:
            self.wins += 1
            result = f"✅ WIN  +${profit:.4f}"
        else:
            self.knockouts += 1
            result = f"❌ KNOCKOUT  ${profit:.4f}"
            self._cooldown_ticks = KNOCKOUT_COOLDOWN
            print(f"[Bot] Knockout! Cooling down for {KNOCKOUT_COOLDOWN} ticks...")

        self._history.append({"profit": profit, "result": "win" if profit > 0 else "knockout"})
        print(f"[Bot] {result} | Session P&L: ${self.session_profit:.4f} | Trades: {self.total_trades}")

        # Stop after WIN_TARGET wins
        if self.wins >= WIN_TARGET:
            print(f"[Bot] 🎯 {WIN_TARGET} wins reached! Session complete.")
            self._stopped = True
            self._force_close_active_trade()
            self._print_summary()

    def _on_buy_error(self):
        """Called when a buy request fails — reset trade state so bot can retry."""
        with self._trade_lock:
            self._in_trade = False
            self._ticks_in_trade = 0
            self._current_profit = 0.0
            self._sell_triggered = False
        # Short cooldown to let server-side state settle before retrying
        self._cooldown_ticks = 10
        print("[Bot] Buy failed — resetting trade state. Cooling down 10 ticks...")
    
    def _force_close_active_trade(self):
        """Force close any active trade when session ends."""
        with self._trade_lock:
            if self._in_trade:
                print(f"[Bot] 🔒 Force closing active trade...")
                self.client.sell_contract(force_retry=True)
                time.sleep(2)  # Give it time to process

    # ------------------------------------------------------------------ #
    #  Trade entry                                                         #
    # ------------------------------------------------------------------ #

    def _enter_trade(self, metrics: dict):
        with self._trade_lock:
            if self._in_trade:
                return
            self._in_trade = True
            self._ticks_in_trade = 0
            self._current_profit = 0.0
            self._sell_triggered = False

        print(
            f"[Bot] 🚀 Entering accumulator | "
            f"vol={metrics['vol_short']:.5f} | "
            f"hurst={metrics['hurst']:.3f} | "
            f"entropy={metrics['entropy']:.3f} | "
            f"consistency={metrics['consistency']:.3f} | "
            f"stake=${STAKE:.2f} | growth={GROWTH_RATE*100:.0f}%"
        )
        self.client.buy_accumulator(STAKE, GROWTH_RATE)

    # ------------------------------------------------------------------ #
    #  Display                                                             #
    # ------------------------------------------------------------------ #

    def _print_status(self):
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        trade_status = "IN TRADE" if self._in_trade else "WATCHING"
        pnl_sign = "+" if self.session_profit >= 0 else ""
        print(
            f"[Status] {trade_status} | "
            f"Ticks: {self.tick_count} | "
            f"Trades: {self.total_trades} | "
            f"Wins: {self.wins} | KOs: {self.knockouts} | "
            f"WR: {win_rate:.0f}% | "
            f"P&L: {pnl_sign}${self.session_profit:.4f}"
        )
        if self._in_trade:
            pnl = self._current_profit
            sign = "+" if pnl >= 0 else ""
            print(f"         └─ Active trade tick #{self._ticks_in_trade} | Current P&L: {sign}${pnl:.4f}")

    def _print_summary(self):
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        print("\n" + "=" * 60)
        print("   SESSION SUMMARY")
        print("=" * 60)
        print(f"   Total trades  : {self.total_trades}")
        print(f"   Wins (sold)   : {self.wins}")
        print(f"   Knockouts     : {self.knockouts}")
        print(f"   Win rate      : {win_rate:.1f}%")
        print(f"   Session P&L   : ${self.session_profit:.4f}")
        print("=" * 60)


if __name__ == "__main__":
    bot = AccumulatorBot()
    bot.run()
