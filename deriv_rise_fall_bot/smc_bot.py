"""
Smart Money Concepts (SMC) Trading Bot
Uses order blocks, support/resistance, and multi-timeframe analysis.
"""

import time
import os
from dotenv import load_dotenv

from deriv_client import DerivClient
from smc_analysis import SMCAnalyzer
from strategy import Strategy
from dashboard_server import DashboardServer

load_dotenv()

# Configuration
API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
APP_ID = os.getenv("DERIV_APP_ID", "1089")
SYMBOL = os.getenv("SYMBOL", "R_100")
STAKE = float(os.getenv("STAKE", "0.50"))
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "5"))
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", "20.0"))
STOP_LOSS = float(os.getenv("STOP_LOSS", "10.0"))

# Martingale
ENABLE_MARTINGALE = os.getenv("ENABLE_MARTINGALE", "false").lower() == "true"
MARTINGALE_MULTIPLIER = float(os.getenv("MARTINGALE_MULTIPLIER", "2.0"))
MAX_MARTINGALE_STEPS = int(os.getenv("MAX_MARTINGALE_STEPS", "2"))

# SMC Settings
MIN_CONFIDENCE = 0.75  # Only trade setups with 75%+ confidence


class SMCBot:
    """Smart Money Concepts trading bot."""
    
    def __init__(self):
        self.client = DerivClient(APP_ID, API_TOKEN, SYMBOL)
        self.smc = SMCAnalyzer(lookback=100)
        self.strategy = Strategy(
            base_stake=STAKE,
            enable_martingale=ENABLE_MARTINGALE,
            martingale_multiplier=MARTINGALE_MULTIPLIER,
            max_martingale_steps=MAX_MARTINGALE_STEPS
        )
        
        # Dashboard server
        self.dashboard = DashboardServer(port=8080)
        
        # Trading state
        self.in_trade = False
        self.last_trade_time = 0
        self.trade_cooldown = 120  # 2 minutes between trades
        self.tick_count = 0
        
        # Stats
        self.setups_by_type = {}
        
        self.client.on_tick = self._handle_tick
        self.client.on_contract_result = self._handle_result
    
    def run(self):
        """Start the bot."""
        print("=" * 80)
        print("🎯 SMART MONEY CONCEPTS (SMC) BOT")
        print("=" * 80)
        
        # Start dashboard server
        self.dashboard.start()
        
        self.client.connect()
        
        timeout = 15
        while not self.client.authorized and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
        
        if not self.client.authorized:
            raise RuntimeError("❌ Authorization failed")
        
        print(f"✅ Connected")
        print(f"🎯 Symbol: {SYMBOL}")
        print(f"💰 Stake: ${STAKE}")
        print(f"⏱️  Duration: {DURATION_MINUTES} minutes")
        print(f"🛑 Stop Loss: ${STOP_LOSS} | Take Profit: ${TAKE_PROFIT}")
        print(f"📊 Min Confidence: {MIN_CONFIDENCE:.0%}")
        print("\n📚 SMC Strategy:")
        print("  • Order Blocks (Bullish/Bearish)")
        print("  • Support & Resistance Zones")
        print("  • Market Structure (HH, HL, LH, LL)")
        print("  • Multi-Timeframe Trend (1m, 5m, 15m)")
        print("=" * 80)
        print("\n⏳ Collecting data... (wait 2-3 minutes for analysis)\n")
        
        try:
            while True:
                time.sleep(5)
                self._print_status()
                
                if self.strategy.total_profit <= -STOP_LOSS:
                    print(f"\n🛑 STOP LOSS HIT: ${self.strategy.total_profit:.2f}")
                    break
                
                if self.strategy.total_profit >= TAKE_PROFIT:
                    print(f"\n🎯 TAKE PROFIT HIT: ${self.strategy.total_profit:.2f}")
                    break
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Bot stopped by user")
        
        finally:
            self._print_final_summary()
            self.dashboard.stop()
    
    def _handle_tick(self, price: float):
        """Process each tick."""
        self.tick_count += 1
        timestamp = time.time()
        
        # Add to SMC analyzer
        self.smc.add_tick(price, timestamp)
        
        # Update dashboard every 10 ticks
        if self.tick_count % 10 == 0:
            self._update_dashboard(price)
        
        # Check for trade every 20 ticks (reduce CPU usage)
        if self.tick_count % 20 == 0 and not self.in_trade:
            self._check_for_trade()
    
    def _check_for_trade(self):
        """Check for SMC trading setup."""
        
        # Cooldown check
        if time.time() - self.last_trade_time < self.trade_cooldown:
            return
        
        # Get analysis first
        analysis = self.smc.get_analysis_summary()
        
        # NEVER trade ranging/mixed markets - this is the main cause of consecutive losses
        if analysis['market_structure']['trend'] == 'ranging':
            if self.tick_count % 100 == 0:
                print(f"   ⏭️  Skipping - ranging market (no clear trend)")
            return
        
        # Check consecutive losses - increase requirements after losses
        consecutive_losses = 0
        if len(self.strategy.trade_history) >= 2:
            if (self.strategy.trade_history[-1]["result"] == "loss" and 
                self.strategy.trade_history[-2]["result"] == "loss"):
                consecutive_losses = 2
            elif self.strategy.trade_history[-1]["result"] == "loss":
                consecutive_losses = 1
        
        # Get SMC signal
        signal, confidence, reason = self.smc.get_trade_signal()
        
        if signal == 0:
            return
        
        # Adjust confidence threshold based on consecutive losses
        required_confidence = MIN_CONFIDENCE
        if consecutive_losses >= 2:
            required_confidence = 0.90  # Require 90%+ after 2 losses (very strict)
            if self.tick_count % 100 == 0:
                print(f"   ⚠️  2 losses in a row - requiring 90%+ confidence")
        elif consecutive_losses == 1:
            required_confidence = 0.85  # Require 85%+ after 1 loss
        
        # Check confidence threshold
        if confidence < required_confidence:
            if self.tick_count % 100 == 0:
                print(f"   ⏭️  Setup detected but low confidence: {reason} ({confidence:.0%} < {required_confidence:.0%})")
            return
        
        # After 2 losses, ONLY trade if all timeframes align AND have data
        if consecutive_losses >= 2:
            mtf_trend = analysis['mtf_trend']
            mtf_aligned = mtf_trend.get('aligned', '')
            
            # Check if we have data for all timeframes
            has_5m = mtf_trend.get('5m') != 'N/A' and '5m' in mtf_trend
            has_15m = mtf_trend.get('15m') != 'N/A' and '15m' in mtf_trend
            
            if not (has_5m and has_15m):
                if self.tick_count % 100 == 0:
                    print(f"   ⏭️  After 2 losses - need 5m and 15m data (5m: {mtf_trend.get('5m', 'N/A')}, 15m: {mtf_trend.get('15m', 'N/A')})")
                return
            
            if mtf_aligned not in ['strong_up', 'strong_down']:
                if self.tick_count % 100 == 0:
                    print(f"   ⏭️  After 2 losses - need strong MTF alignment (got: {mtf_aligned})")
                return
        
        # Analysis already retrieved above
        
        # Trade the setup
        direction = "RISE" if signal == 1 else "FALL"
        contract_type = "CALL" if signal == 1 else "PUT"
        
        # Track setup performance
        if reason not in self.setups_by_type:
            self.setups_by_type[reason] = {"count": 0, "wins": 0}
        self.setups_by_type[reason]["count"] += 1
        self.current_setup = reason
        
        martingale_info = ""
        if ENABLE_MARTINGALE and self.strategy.martingale_step > 0:
            martingale_info = f" | 📈 Step {self.strategy.martingale_step}/{MAX_MARTINGALE_STEPS}"
        
        print(f"\n{'='*80}")
        print(f"🎯 SMC TRADE SETUP")
        print(f"{'='*80}")
        print(f"📊 Setup: {reason}")
        print(f"🎲 Direction: {direction}")
        print(f"💪 Confidence: {confidence:.0%}")
        print(f"\n📈 Market Structure: {analysis['market_structure']['structure']} "
              f"({analysis['market_structure']['trend']})")
        print(f"🕐 MTF Trend: 1m={analysis['mtf_trend'].get('1m', 'N/A')} | "
              f"5m={analysis['mtf_trend'].get('5m', 'N/A')} | "
              f"15m={analysis['mtf_trend'].get('15m', 'N/A')}")
        print(f"📍 Order Blocks: {analysis['order_blocks']['bullish']} bullish, "
              f"{analysis['order_blocks']['bearish']} bearish")
        print(f"🎯 S/R Zones: {analysis['support_zones']} support, "
              f"{analysis['resistance_zones']} resistance")
        print(f"\n💰 Stake: ${self.strategy.stake:.2f}{martingale_info}")
        print(f"{'='*80}\n")
        
        self.in_trade = True
        self.last_trade_time = time.time()
        
        self.client.buy_contract(contract_type, self.strategy.stake, DURATION_MINUTES)
    
    def _handle_result(self, status: str, profit: float):
        """Handle trade result."""
        self.in_trade = False
        
        won = profit > 0
        
        # Update setup stats
        if hasattr(self, 'current_setup') and self.current_setup in self.setups_by_type:
            if won:
                self.setups_by_type[self.current_setup]["wins"] += 1
        
        # Update strategy
        if won:
            self.strategy.on_win(abs(profit))
        else:
            self.strategy.on_loss(abs(profit))
        
        print()  # Spacing
    
    def _update_dashboard(self, price: float):
        """Update dashboard with current data."""
        wins = sum(1 for t in self.strategy.trade_history if t["result"] == "win")
        losses = len(self.strategy.trade_history) - wins
        wr = (wins / len(self.strategy.trade_history) * 100) if self.strategy.trade_history else 0
        
        # Get current analysis
        analysis = self.smc.get_analysis_summary()
        
        # Get current signal
        signal, confidence, reason = self.smc.get_trade_signal()
        signal_direction = "RISE" if signal == 1 else ("FALL" if signal == -1 else "NONE")
        
        # Prepare order blocks data
        order_blocks_data = []
        for ob in self.smc.order_blocks:
            order_blocks_data.append({
                'type': ob.block_type,
                'high': ob.price_high,
                'low': ob.price_low,
                'strength': ob.strength
            })
        
        # Prepare support/resistance zones
        support_zones_data = [{'price': z.price, 'strength': z.strength} for z in self.smc.support_zones]
        resistance_zones_data = [{'price': z.price, 'strength': z.strength} for z in self.smc.resistance_zones]
        
        # Send to dashboard
        dashboard_data = {
            'price': price,
            'stats': {
                'total_trades': len(self.strategy.trade_history),
                'win_rate': wr,
                'profit_loss': self.strategy.total_profit
            },
            'analysis': analysis,
            'signal': {
                'direction': signal_direction,
                'confidence': confidence,
                'reason': reason
            },
            'order_blocks': order_blocks_data,
            'support_zones': support_zones_data,
            'resistance_zones': resistance_zones_data
        }
        
        self.dashboard.update(dashboard_data)
    
    def _print_status(self):
        """Print current status."""
        if self.tick_count < 100:
            print(f"⏳ LOADING DATA... ({self.tick_count}/100 ticks)")
            return
        
        wins = sum(1 for t in self.strategy.trade_history if t["result"] == "win")
        losses = len(self.strategy.trade_history) - wins
        wr = (wins / len(self.strategy.trade_history) * 100) if self.strategy.trade_history else 0
        
        # Get current analysis
        analysis = self.smc.get_analysis_summary()
        structure = analysis['market_structure']
        mtf = analysis['mtf_trend']
        
        # Status emoji
        if structure['trend'] == 'uptrend':
            trend_emoji = "📈"
        elif structure['trend'] == 'downtrend':
            trend_emoji = "📉"
        else:
            trend_emoji = "📊"
        
        martingale_info = ""
        if ENABLE_MARTINGALE and self.strategy.martingale_step > 0:
            martingale_info = f" | 📈 Martingale: Step {self.strategy.martingale_step}/{MAX_MARTINGALE_STEPS}"
        
        print(f"{trend_emoji} {structure['structure']} | MTF: {mtf.get('aligned', 'N/A')} | "
              f"Trades: {len(self.strategy.trade_history)} | "
              f"W/L: {wins}/{losses} | "
              f"WR: {wr:.1f}% | "
              f"P&L: ${self.strategy.total_profit:.2f}{martingale_info}")
    
    def _print_final_summary(self):
        """Print final summary."""
        print("\n" + "=" * 80)
        print("📊 FINAL SUMMARY")
        print("=" * 80)
        
        wins = sum(1 for t in self.strategy.trade_history if t["result"] == "win")
        losses = len(self.strategy.trade_history) - wins
        wr = (wins / len(self.strategy.trade_history) * 100) if self.strategy.trade_history else 0
        
        print(f"Total Trades: {len(self.strategy.trade_history)}")
        print(f"Wins: {wins} | Losses: {losses}")
        print(f"Win Rate: {wr:.1f}%")
        print(f"Final P&L: ${self.strategy.total_profit:.2f}")
        
        if self.strategy.trade_history:
            total_won = sum(t["profit"] for t in self.strategy.trade_history if t["result"] == "win")
            total_lost = sum(abs(t["profit"]) for t in self.strategy.trade_history if t["result"] == "loss")
            
            if total_lost > 0:
                profit_factor = total_won / total_lost
                print(f"Profit Factor: {profit_factor:.2f}")
        
        if self.setups_by_type:
            print("\n📈 Setup Performance:")
            print("-" * 80)
            for setup, stats in sorted(self.setups_by_type.items(), 
                                      key=lambda x: x[1]["wins"]/max(x[1]["count"], 1), 
                                      reverse=True):
                setup_wr = (stats["wins"] / stats["count"] * 100) if stats["count"] > 0 else 0
                print(f"  {setup:50s} | Trades: {stats['count']:2d} | "
                      f"Wins: {stats['wins']:2d} | WR: {setup_wr:5.1f}%")
        
        # Final analysis
        analysis = self.smc.get_analysis_summary()
        print(f"\n📊 Final Market Analysis:")
        print(f"  Structure: {analysis['market_structure']['structure']} "
              f"({analysis['market_structure']['trend']})")
        print(f"  MTF Alignment: {analysis['mtf_trend'].get('aligned', 'N/A')}")
        print(f"  Order Blocks: {analysis['order_blocks']['bullish']} bullish, "
              f"{analysis['order_blocks']['bearish']} bearish")
        
        print("=" * 80)


if __name__ == "__main__":
    bot = SMCBot()
    bot.run()
