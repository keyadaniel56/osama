"""
Multi-Market Accumulator Bot for Deriv.

Monitors multiple synthetic indices simultaneously and trades the one
with the best entry conditions at any given moment.

Features:
- Parallel monitoring of multiple markets (R_10, R_25, R_50, R_75, R_100)
- Independent volatility analysis per market
- Trades whichever market shows best conditions
- Can have one active trade at a time across all markets
- Maximizes trading opportunities
"""

import time
import os
import threading
from collections import deque
from typing import Dict, Optional
from dotenv import load_dotenv

from client import DerivClient
from volatility import VolatilityAnalyzer

load_dotenv()

# --- Config ---
API_TOKEN   = os.getenv("DERIV_API_TOKEN", "")
APP_ID      = os.getenv("DERIV_APP_ID", "1089")
STAKE       = float(os.getenv("STAKE", "1.0"))
GROWTH_RATE = float(os.getenv("GROWTH_RATE", "0.01"))
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", "10.0"))
STOP_LOSS   = float(os.getenv("STOP_LOSS", "5.0"))
TARGET_TICKS = int(os.getenv("TARGET_TICKS", "3"))
KNOCKOUT_COOLDOWN = 20
WARMUP_TICKS = 30
WIN_TARGET = int(os.getenv("WIN_TARGET", "3"))

# Markets to monitor
SYMBOLS = ["R_10", "R_25", "R_50", "R_75", "R_100"]


class MarketMonitor:
    """Monitors a single market and tracks its conditions."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.analyzer = VolatilityAnalyzer(window=30)
        self.tick_count = 0
        self.last_price = 0.0
        self.ready = False
        
    def add_tick(self, price: float):
        self.tick_count += 1
        self.last_price = price
        self.analyzer.add_tick(price)
        
        if self.tick_count >= WARMUP_TICKS:
            self.ready = True
    
    def get_entry_score(self) -> tuple[bool, float, dict]:
        """
        Returns (can_enter, score, metrics)
        Score: higher = better conditions (0-100)
        """
        if not self.ready:
            return False, 0.0, {}
        
        metrics = self.analyzer.analyze()
        safe, reason = self.analyzer.is_safe_to_enter(metrics, GROWTH_RATE)
        
        if not safe:
            return False, 0.0, metrics
        
        # Calculate entry score (higher = better)
        score = 0.0
        
        # Lower volatility = better (max 40 points)
        vol_score = max(0, 40 * (1 - metrics["vol_short"] / 0.0003))
        score += vol_score
        
        # Higher consistency = better (max 30 points)
        consistency_score = (metrics["consistency"] - 0.6) * 75  # 0.6->0, 1.0->30
        score += max(0, min(30, consistency_score))
        
        # Decreasing volatility = better (max 20 points)
        if metrics["vol_trend"] < 0:
            vol_trend_score = min(20, abs(metrics["vol_trend"]) * 100000)
            score += vol_trend_score
        
        # Higher Hurst = better (max 10 points)
        hurst_score = (metrics["hurst"] - 0.5) * 20  # 0.5->0, 1.0->10
        score += max(0, min(10, hurst_score))
        
        return True, score, metrics


class MultiMarketBot:
    """Manages multiple market monitors and executes trades."""
    
    def __init__(self):
        # Create monitors for each symbol
        self.monitors: Dict[str, MarketMonitor] = {
            symbol: MarketMonitor(symbol) for symbol in SYMBOLS
        }
        
        # Create WebSocket clients for each symbol
        self.clients: Dict[str, DerivClient] = {}
        
        # Trading state
        self.session_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.knockouts = 0
        self._stopped = False
        
        # Active trade tracking
        self._active_symbol: Optional[str] = None
        self._in_trade = False
        self._ticks_in_trade = 0
        self._current_profit = 0.0
        self._sell_triggered = False
        self._trade_lock = threading.Lock()
        self._cooldown_until = {}  # symbol -> tick_count when cooldown ends
        
        # Authorization tracking
        self._authorized_count = 0
        self._auth_lock = threading.Lock()
        
    def run(self):
        print("=" * 70)
        print("   MULTI-MARKET ACCUMULATOR BOT")
        print(f"   Markets: {', '.join(SYMBOLS)}")
        print(f"   Stake: ${STAKE:.2f} | Growth: {GROWTH_RATE*100:.0f}%")
        print(f"   TP: ${TAKE_PROFIT} | SL: -${STOP_LOSS} | Win Target: {WIN_TARGET}")
        print("=" * 70)
        
        # Connect to all markets
        for symbol in SYMBOLS:
            client = DerivClient(APP_ID, API_TOKEN, symbol)
            client.on_tick = lambda price, sym=symbol: self._on_tick(sym, price)
            client.on_contract_update = self._on_contract_update
            client.on_contract_sold = self._on_contract_sold
            client.on_buy_error = self._on_buy_error
            client.on_authorized = self._on_authorized
            
            self.clients[symbol] = client
            self._cooldown_until[symbol] = 0
            
            # Connect in separate thread
            threading.Thread(target=client.connect, daemon=True).start()
            time.sleep(0.5)  # Stagger connections
        
        # Wait for all to authorize
        print(f"[Bot] Connecting to {len(SYMBOLS)} markets...")
        timeout = 30
        while self._authorized_count < len(SYMBOLS) and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
        
        if self._authorized_count < len(SYMBOLS):
            print(f"[Bot] Warning: Only {self._authorized_count}/{len(SYMBOLS)} markets connected")
        else:
            print(f"[Bot] All {len(SYMBOLS)} markets connected successfully!")
        
        print(f"[Bot] Warming up — collecting {WARMUP_TICKS} ticks per market...")
        
        # Main loop
        try:
            while not self._stopped:
                time.sleep(5)
                self._print_status()
                
                # Check for best entry opportunity
                if not self._in_trade:
                    self._check_entry_opportunities()
                    
        except KeyboardInterrupt:
            print("\n[Bot] Stopped by user.")
            if self._in_trade and self._active_symbol:
                print(f"[Bot] Selling active contract on {self._active_symbol}...")
                self.clients[self._active_symbol].sell_contract()
                time.sleep(3)
            self._print_summary()
    
    def _on_tick(self, symbol: str, price: float):
        """Called when a tick arrives for any market."""
        monitor = self.monitors[symbol]
        monitor.add_tick(price)
        
        # Track ticks in active trade
        with self._trade_lock:
            if self._in_trade and self._active_symbol == symbol:
                self._ticks_in_trade += 1
                
                # Emergency exit after TARGET_TICKS
                if self._ticks_in_trade >= TARGET_TICKS and not self._sell_triggered:
                    self._sell_triggered = True
                    print(f"[Bot] ⏱ Max ticks reached on {symbol}. Selling...")
                    self.clients[symbol].sell_contract()
    
    def _check_entry_opportunities(self):
        """Scan all markets and enter the best one."""
        # Don't enter new trades if session is stopped
        if self._stopped:
            return
        
        # ULTRA-STRICT MINIMUM SCORE - only enter perfect setups
        MIN_ENTRY_SCORE = 70.0  # Increased from 55.0 - only excellent conditions
            
        best_symbol = None
        best_score = 0.0
        best_metrics = {}
        
        for symbol, monitor in self.monitors.items():
            # Skip if in cooldown
            if monitor.tick_count < self._cooldown_until.get(symbol, 0):
                continue
            
            can_enter, score, metrics = monitor.get_entry_score()
            
            if can_enter and score > best_score:
                best_score = score
                best_symbol = symbol
                best_metrics = metrics
        
        # Enter the best market if found AND score meets minimum threshold
        if best_symbol and best_score >= MIN_ENTRY_SCORE and not self._stopped:
            self._enter_trade(best_symbol, best_metrics, best_score)
    
    def _enter_trade(self, symbol: str, metrics: dict, score: float):
        """Enter a trade on the specified symbol."""
        with self._trade_lock:
            if self._in_trade:
                return
            
            self._in_trade = True
            self._active_symbol = symbol
            self._ticks_in_trade = 0
            self._current_profit = 0.0
            self._sell_triggered = False
        
        print(
            f"[Bot] 🚀 Entering {symbol} (score={score:.1f}) | "
            f"vol={metrics['vol_short']:.5f} | "
            f"consistency={metrics['consistency']:.3f} | "
            f"hurst={metrics['hurst']:.3f}"
        )
        
        self.clients[symbol].buy_accumulator(STAKE, GROWTH_RATE)
    
    def _on_contract_update(self, status: str, profit: float, current_value: float):
        """Called on every tick while contract is alive."""
        with self._trade_lock:
            self._current_profit = profit
        
        profit_pct = (profit / STAKE) * 100 if STAKE > 0 else 0
        
        # Exit at 1% profit
        if profit_pct >= 1.0 and not self._sell_triggered:
            self._sell_triggered = True
            print(f"[Bot] 💰 Quick profit ({profit_pct:.1f}%) on {self._active_symbol}. Selling...")
            self.clients[self._active_symbol].sell_contract()
        
        # Exit with any profit after 2 ticks
        elif profit > 0.01 and self._ticks_in_trade >= 2 and not self._sell_triggered:
            self._sell_triggered = True
            print(f"[Bot] ⚡ Locking in ${profit:.4f} on {self._active_symbol}")
            self.clients[self._active_symbol].sell_contract()
        
        # Emergency exit at 3 ticks - RETRY if previous sell failed
        elif self._ticks_in_trade >= 3:
            if not self._sell_triggered:
                self._sell_triggered = True
                print(f"[Bot] ⚠️ Emergency exit on {self._active_symbol} - P&L: ${profit:.4f}")
                self.clients[self._active_symbol].sell_contract()
            # If we're past tick 4 and still in trade, force retry
            elif self._ticks_in_trade >= 4:
                print(f"[Bot] 🔄 Retry selling {self._active_symbol} at tick {self._ticks_in_trade} - P&L: ${profit:.4f}")
                self.clients[self._active_symbol].sell_contract(force_retry=True)
    
    def _on_contract_sold(self, profit: float):
        """Called when contract closes."""
        symbol = self._active_symbol
        
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
            result = f"❌ LOSS  ${profit:.4f}"
            # Set cooldown for this symbol
            self._cooldown_until[symbol] = self.monitors[symbol].tick_count + KNOCKOUT_COOLDOWN
            print(f"[Bot] Cooldown on {symbol} for {KNOCKOUT_COOLDOWN} ticks...")
            
            # LEARN FROM KNOCKOUT - improve future predictions
            self.monitors[symbol].analyzer.learn_from_knockout()
            print(f"[Bot] Learning from knockout pattern on {symbol}")
        
        print(f"[Bot] {result} on {symbol} | Session P&L: ${self.session_profit:.4f} | Trades: {self.total_trades}")
        
        # Check session targets
        if self.wins >= WIN_TARGET:
            print(f"[Bot] 🎯 {WIN_TARGET} wins reached! Session complete.")
            self._stopped = True
            self._force_close_active_trade()
            self._print_summary()
        elif self.session_profit >= TAKE_PROFIT:
            print(f"[Bot] 🎯 Take profit reached! Session P&L: ${self.session_profit:.4f}")
            self._stopped = True
            self._force_close_active_trade()
            self._print_summary()
        elif self.session_profit <= -STOP_LOSS:
            print(f"[Bot] 🛑 Stop loss hit! Session P&L: ${self.session_profit:.4f}")
            self._stopped = True
            self._force_close_active_trade()
            self._print_summary()
        
        self._active_symbol = None
    
    def _on_authorized(self):
        """Called when a client successfully authorizes."""
        with self._auth_lock:
            self._authorized_count += 1
    
    def _on_buy_error(self):
        """Called when buy fails."""
        with self._trade_lock:
            self._in_trade = False
            self._ticks_in_trade = 0
            self._current_profit = 0.0
            self._sell_triggered = False
        
        if self._active_symbol:
            self._cooldown_until[self._active_symbol] = self.monitors[self._active_symbol].tick_count + 10
        
        self._active_symbol = None
    
    def _force_close_active_trade(self):
        """Force close any active trade when session ends."""
        with self._trade_lock:
            if self._in_trade and self._active_symbol:
                print(f"[Bot] 🔒 Force closing active trade on {self._active_symbol}...")
                self.clients[self._active_symbol].sell_contract(force_retry=True)
                time.sleep(2)  # Give it time to process
    
    def _print_status(self):
        """Print current status of all markets."""
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        trade_status = f"IN TRADE ({self._active_symbol})" if self._in_trade else "WATCHING"
        pnl_sign = "+" if self.session_profit >= 0 else ""
        
        # Count ready markets
        ready_markets = sum(1 for m in self.monitors.values() if m.ready)
        
        print(
            f"[Status] {trade_status} | "
            f"Markets: {ready_markets}/{len(SYMBOLS)} ready | "
            f"Trades: {self.total_trades} | "
            f"Wins: {self.wins} | Losses: {self.knockouts} | "
            f"WR: {win_rate:.0f}% | "
            f"P&L: {pnl_sign}${self.session_profit:.4f}"
        )
        
        if self._in_trade:
            pnl = self._current_profit
            sign = "+" if pnl >= 0 else ""
            print(f"         └─ {self._active_symbol} tick #{self._ticks_in_trade} | P&L: {sign}${pnl:.4f}")
        else:
            # Show best current opportunity and why others are rejected
            best_sym = None
            best_score = 0.0
            rejection_reasons = {}
            
            for symbol, monitor in self.monitors.items():
                if monitor.tick_count < self._cooldown_until.get(symbol, 0):
                    rejection_reasons[symbol] = "cooldown"
                    continue
                    
                can_enter, score, metrics = monitor.get_entry_score()
                if can_enter and score > best_score:
                    best_score = score
                    best_sym = symbol
                elif not can_enter and metrics:
                    # Get rejection reason from analyzer
                    _, reason = monitor.analyzer.is_safe_to_enter(metrics, GROWTH_RATE)
                    rejection_reasons[symbol] = reason
            
            if best_sym:
                print(f"         └─ Best opportunity: {best_sym} (score={best_score:.1f})")
            else:
                # Show why no trades available (sample 2-3 markets)
                sample_reasons = list(rejection_reasons.items())[:3]
                if sample_reasons:
                    reasons_str = " | ".join([f"{sym}: {reason}" for sym, reason in sample_reasons])
                    print(f"         └─ No entries: {reasons_str}")
    
    def _print_summary(self):
        """Print session summary."""
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        print("\n" + "=" * 70)
        print("   MULTI-MARKET SESSION SUMMARY")
        print("=" * 70)
        print(f"   Markets monitored : {len(SYMBOLS)}")
        print(f"   Total trades      : {self.total_trades}")
        print(f"   Wins              : {self.wins}")
        print(f"   Losses            : {self.knockouts}")
        print(f"   Win rate          : {win_rate:.1f}%")
        print(f"   Session P&L       : ${self.session_profit:.4f}")
        print("=" * 70)


if __name__ == "__main__":
    bot = MultiMarketBot()
    bot.run()
