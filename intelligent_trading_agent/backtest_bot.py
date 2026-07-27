"""
Backtest the fixed trading agent against historical market data.
Tests the new MOMENTUM-FOLLOWING strategy (replaced old mean-reversion).

Usage: python backtest_bot.py
"""

import json
import os
import sys
import numpy as np
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, List, Optional, Tuple

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the fixed subsystems
from features.indicators import FeatureEngine
from features.pattern_recognition import ChartPatternRecognizer
from market_analyzer import MarketAnalyzer
from decision_engine import DecisionEngine
from risk_manager import RiskManager
from strategies.rise_fall import RiseFallStrategy
from config import MODELS_DIR


class BacktestRunner:
    """
    Replays historical price data through the bot's subsystems.
    Tests: market analysis, the NEW momentum-following strategy, decision engine, risk management.
    Does NOT connect to Deriv or place real trades.
    """
    
    def __init__(self, initial_stake: float = 0.35):
        self.initial_stake = initial_stake
        
        # Initialize bot subsystems
        self.market_analyzer = MarketAnalyzer(window=100)
        self.pattern_recognizer = ChartPatternRecognizer(window=100)
        self.rise_fall_strategy = RiseFallStrategy(base_stake=initial_stake)
        self.decision_engine = DecisionEngine()
        self.risk_manager = RiskManager()
        
        # Override risk manager's base stake
        self.risk_manager.base_stake = initial_stake
        self.risk_manager.current_stake = initial_stake
        
        # Performance tracking
        self.trades = []
        self.pnl_history = []
        self.equity = initial_stake * 100  # Starting equity
        self.peak_equity = self.equity
        
        # Session data
        self.session_files = []
        self.load_session_files()
    
    def load_session_files(self):
        """Load historical session files for price data."""
        sessions_dir = MODELS_DIR
        if not os.path.exists(sessions_dir):
            print(f"⚠️ Models directory not found: {sessions_dir}")
            return
        
        files = sorted([f for f in os.listdir(sessions_dir) if f.startswith('session_agent_') and f.endswith('.json')])
        self.session_files = [os.path.join(sessions_dir, f) for f in files]
        print(f"📂 Found {len(self.session_files)} historical session files")
    
    def load_latest_session_prices(self) -> List[float]:
        """Extract all price data from the most recent session files."""
        all_prices = []
        
        # Only take the most recent 10 sessions (to avoid stale old data)
        recent_files = self.session_files[-10:] if len(self.session_files) > 10 else self.session_files
        
        for session_file in recent_files:
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                trades = data.get('trades', [])
                for trade in trades:
                    market_data = trade.get('market_data', {})
                    if market_data:
                        price = market_data.get('price', 0)
                        if price > 0:
                            all_prices.append(price)
                    
                    entry_price = trade.get('entry_price', 0)
                    if entry_price > 0 and isinstance(entry_price, (int, float)):
                        all_prices.append(entry_price)
            except Exception as e:
                print(f"  ⚠️ Error extracting from {session_file}: {e}")
        
        if all_prices:
            print(f"📊 Extracted {len(all_prices)} price points from {len(recent_files)} sessions")
            # Return sorted by time (oldest first)
            return all_prices
        
        return []
    
    def generate_synthetic_prices(self, n_ticks: int = 5000, base_price: float = 4885.0) -> List[float]:
        """
        Generate realistic synthetic index prices.
        Models R_100 behavior with momentum persistence.
        """
        np.random.seed(42)
        prices = [base_price]
        
        for i in range(1, n_ticks):
            # Random walk with momentum persistence
            mean = 0.0
            std = 0.5  # ~$0.50 per tick volatility for R_100
            
            # Add momentum persistence (key characteristic of synthetic indices)
            if len(prices) >= 5:
                recent_trend = prices[-1] - prices[-5]
                mean += recent_trend * 0.15  # 15% momentum persistence
            
            # Add occasional stronger trends (every ~300 ticks)
            if i % 300 < 40:  # 40-tick trend
                mean += 0.4 if (i // 300) % 2 == 0 else -0.4
            
            # Add mean-reversion resistance (prevents clean reversals at extremes)
            if abs(mean) > 0.3:
                mean *= 0.9  # Momentum resists fading
            
            # Generate next price
            change = np.random.normal(mean, std)
            new_price = prices[-1] + change
            
            # Keep prices in realistic range
            new_price = max(base_price - 50, min(base_price + 50, new_price))
            prices.append(new_price)
        
        return prices
    
    def run(self, n_ticks: int = 3000, price_data: Optional[List[float]] = None, scenario_name: str = "default"):
        """Run backtest simulation with momentum-following strategy."""
        if price_data is None:
            print(f"\n🔄 Generating {n_ticks} ticks of synthetic price data...")
            price_data = self.generate_synthetic_prices(n_ticks)
        else:
            n_ticks = len(price_data)
            print(f"\n🔄 Using {n_ticks} historical price points")
        
        print(f"   Price range: ${min(price_data):.2f} - ${max(price_data):.2f}")
        
        WARMUP_TICKS = 200
        cooldown = 0
        trade_count = 0
        win_count = 0
        loss_count = 0
        
        # Track performance by market state
        state_perf = {}
        
        for tick in range(n_ticks):
            price = price_data[tick]
            
            # Update market analyzer
            self.market_analyzer.update(price, volume=1.0)
            self.pattern_recognizer.add_price(price)
            
            if tick < WARMUP_TICKS:
                continue
            
            # Extract features
            features = self.market_analyzer.feature_engine.extract_features()
            market_state = self.market_analyzer.detect_market_state()
            market_health = self.market_analyzer.calculate_market_health()
            
            # Track state performance counters
            if market_state not in state_perf:
                state_perf[market_state] = {'opportunities': 0, 'trades': 0, 'wins': 0, 'profit': 0.0}
            state_perf[market_state]['opportunities'] += 1
            
            # Detect patterns
            patterns = self.pattern_recognizer.detect_all_patterns()
            
            # Get indicators
            indicators = features
            rsi = indicators.get('rsi', 50)
            bb_position = indicators.get('bb_position', 0.5)
            macd = indicators.get('macd_histogram', 0)
            momentum_10 = indicators.get('momentum_10', 0.0)
            price_vs_sma20 = indicators.get('price_vs_sma20', 0.0)
            trend_strength = indicators.get('trend_strength', 0.0)
            
            # ===== NEW MOMENTUM-FOLLOWING STRATEGY =====
            # The strategy now follows momentum (not mean-reversion):
            # - RSI > 58 + momentum > 0.2 + price above SMA → BUY RISE
            # - RSI < 42 + momentum < -0.2 + price below SMA → BUY FALL
            trade_dir = None
            confidence = 0.0
            
            # Use the rise_fall strategy
            signal = self.rise_fall_strategy.analyze({'features': features, 'price': price})
            
            if signal.action == 'BUY':
                trade_dir = 'up' if signal.contract_type == 'RISE' else 'down'
                confidence = signal.confidence
                
                # Momentum consistency check (same as agent.py)
                if rsi > 60 and momentum_10 < -0.1 and trade_dir == 'up':
                    trade_dir = None
                    confidence = 0.0
                elif rsi < 40 and momentum_10 > 0.1 and trade_dir == 'down':
                    trade_dir = None
                    confidence = 0.0
            
            # Get pattern data for decision engine
            pattern_data = None
            if patterns:
                pattern_data = {'patterns': {}}
                for pname, pinfo in patterns.items():
                    sig = pinfo.get('signal', '')
                    ptype = None
                    if 'bullish' in sig or 'up' in sig:
                        ptype = 'bullish'
                    elif 'bearish' in sig or 'down' in sig:
                        ptype = 'bearish'
                    else:
                        ptype = 'neutral'
                    pattern_data['patterns'][pname] = {
                        'type': ptype,
                        'confidence': pinfo.get('confidence', 0.5)
                    }
            
            # Build ML prediction from indicators (simplified)
            ml_dir = None
            ml_conf = 0.0
            if rsi > 60 and macd > 0 and momentum_10 > 0.2:
                ml_dir = 'up'
                ml_conf = min(0.5 + abs(momentum_10), 0.85)
            elif rsi < 40 and macd < 0 and momentum_10 < -0.2:
                ml_dir = 'down'
                ml_conf = min(0.5 + abs(momentum_10), 0.85)
            
            ml_prediction = {'direction': ml_dir, 'confidence': ml_conf}
            
            # Use decision engine
            de_trade_dir, de_confidence = self.decision_engine.make_decision(
                ml_prediction=ml_prediction,
                patterns=pattern_data,
                indicators=indicators,
                market_state=market_state,
                market_health=market_health
            )
            
            # Use decision engine's direction if it's confident
            if de_trade_dir and de_confidence > confidence:
                trade_dir = de_trade_dir
                confidence = de_confidence
            
            # Ranging market guard
            if trade_dir and 'ranging' in market_state:
                if confidence < 0.80:
                    trade_dir = None
                    confidence = 0.0
            
            # Check risk constraints
            can_trade = self.risk_manager.should_trade(confidence, market_health)
            
            # Decrement cooldown
            if cooldown > 0:
                cooldown -= 1
            
            # Simulate trade
            if (trade_dir and confidence >= 0.65 and can_trade and cooldown == 0 
                and len(self.trades) < 50):  # Limit trades for backtest
                
                contract_type = 'CALL' if trade_dir == 'up' else 'PUT'
                
                # Calculate position size
                volatility = features.get('volatility', 0.5)
                position_size = self.risk_manager.calculate_position_size(
                    confidence, volatility, trade_direction=trade_dir
                )
                
                # Look ahead to see outcome (300 ticks ≈ 5 min contract)
                contract_duration_ticks = 300
                end_tick = min(tick + contract_duration_ticks, n_ticks - 1)
                future_price = price_data[end_tick]
                
                # Determine if trade wins
                # Real Deriv payout: ~80% of stake on win, lose stake on loss
                price_moved_up = future_price > price
                if contract_type == 'CALL':
                    won = price_moved_up
                else:
                    won = not price_moved_up
                
                # Calculate profit with realistic Deriv payout structure
                if won:
                    profit = position_size * 0.80  # ~80% payout (standard for Rise/Fall)
                    win_count += 1
                else:
                    profit = -position_size  # Lose entire stake
                    loss_count += 1
                
                # Update equity
                self.equity += profit
                if self.equity > self.peak_equity:
                    self.peak_equity = self.equity
                
                # Record trade
                self.trades.append({
                    'tick': tick,
                    'price': price,
                    'direction': trade_dir,
                    'confidence': confidence,
                    'position': position_size,
                    'won': won,
                    'profit': profit,
                    'state': market_state,
                    'rsi': rsi,
                    'bb_pos': bb_position,
                    'momentum': momentum_10,
                    'volatility': volatility,
                    'trend_strength': trend_strength,
                    'price_vs_sma20': price_vs_sma20,
                    'patterns': list(patterns.keys()) if patterns else [],
                })
                
                # Track state performance
                state_perf[market_state]['trades'] += 1
                state_perf[market_state]['wins'] += 1 if won else 0
                state_perf[market_state]['profit'] += profit
                
                self.pnl_history.append(self.equity)
                trade_count += 1
                
                # Update risk manager
                self.risk_manager.record_trade_result(position_size, won, profit)
                
                # Set cooldown
                cooldown = 50  # ticks
        
        # Print results
        self.print_results(scenario_name, state_perf)
        
        return self.trades, self.pnl_history
    
    def print_results(self, scenario_name: str, state_perf: Dict):
        """Print backtest results."""
        print("\n" + "="*80)
        print(f"📊 BACKTEST RESULTS: {scenario_name}")
        print("="*80)
        
        # Trade summary
        total = len(self.trades)
        wins = sum(1 for t in self.trades if t['won'])
        losses = sum(1 for t in self.trades if not t['won'])
        win_rate = wins / total if total > 0 else 0
        
        total_profit = sum(t['profit'] for t in self.trades)
        avg_profit = total_profit / total if total > 0 else 0
        max_drawdown = self.calculate_max_drawdown()
        profit_factor = self.calculate_profit_factor()
        
        print(f"\n📈 TRADES: {total}")
        print(f"   Wins: {wins}  Losses: {losses}  Win Rate: {win_rate:.1%}")
        print(f"   Total P&L: ${total_profit:.2f}")
        print(f"   Avg Profit/Trade: ${avg_profit:.2f}")
        print(f"   Profit Factor: {profit_factor:.2f}x")
        print(f"   Max Drawdown: {max_drawdown:.1f}%")
        print(f"   Final Equity: ${self.equity:.2f}")
        print(f"   Peak Equity: ${self.peak_equity:.2f}")
        print(f"   ROI: {((self.equity / (self.initial_stake * 100)) - 1) * 100:.1f}%")
        
        # Performance by market state
        print(f"\n📊 PERFORMANCE BY MARKET STATE:")
        print(f"   {'STATE':20} | {'OPPS':>5} | {'TRADES':>6} | {'WINS':>4} | {'WR':>5} | {'PnL':>8}")
        print(f"   {'-'*20} | {'-'*5} | {'-'*6} | {'-'*4} | {'-'*5} | {'-'*8}")
        for state, data in sorted(state_perf.items(), key=lambda x: x[1]['trades'], reverse=True):
            if data['trades'] > 0:
                wr = data['wins'] / data['trades'] * 100
                opp_rate = data['trades'] / data['opportunities'] * 100 if data['opportunities'] > 0 else 0
                print(f"   {state:20} | {data['opportunities']:5} | {data['trades']:6} | {data['wins']:4} | {wr:4.1f}% | ${data['profit']:+>7.2f}")
        
        # Performance by RSI zone
        print(f"\n📊 PERFORMANCE BY RSI ZONE:")
        zones = {'Oversold (<30)': [], 'Moderately Low (30-40)': [], 'Neutral (40-60)': [], 'Moderately High (60-70)': [], 'Overbought (>70)': []}
        for t in self.trades:
            if t['rsi'] < 30:
                zones['Oversold (<30)'].append(t)
            elif t['rsi'] < 40:
                zones['Moderately Low (30-40)'].append(t)
            elif t['rsi'] < 60:
                zones['Neutral (40-60)'].append(t)
            elif t['rsi'] < 70:
                zones['Moderately High (60-70)'].append(t)
            else:
                zones['Overbought (>70)'].append(t)
        
        for zone, trades in zones.items():
            if trades:
                wr = sum(1 for t in trades if t['won']) / len(trades) * 100
                pnl = sum(t['profit'] for t in trades)
                print(f"   {zone:25} | {len(trades):3} trades | {wr:5.1f}% WR | ${pnl:+>7.2f}")
        
        # Consecutive loss analysis
        max_consec_losses = 0
        current_consec = 0
        for t in self.trades:
            if not t['won']:
                current_consec += 1
                max_consec_losses = max(max_consec_losses, current_consec)
            else:
                current_consec = 0
        
        print(f"\n⚠️  RISK METRICS:")
        print(f"   Max Consecutive Losses: {max_consec_losses}")
        
        # Analyze what worked
        print(f"\n📋 MOMENTUM ANALYSIS (last 10 trades):")
        for t in self.trades[-10:]:
            mark = "✓" if t['won'] else "✗"
            print(f"   {mark} {t['direction']:4} | RSI={t['rsi']:.0f} | mom={t['momentum']:+.3f} | "
                  f"conf={t['confidence']:.2f} | state={t['state']:15} | ${t['profit']:+.2f}")
        
        print("\n" + "="*80)
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage from pnl history."""
        if not self.pnl_history:
            return 0.0
        peak = self.pnl_history[0]
        max_dd = 0.0
        for value in self.pnl_history:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            max_dd = max(max_dd, dd)
        return max_dd
    
    def calculate_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        gross_profit = sum(t['profit'] for t in self.trades if t['profit'] > 0)
        gross_loss = abs(sum(t['profit'] for t in self.trades if t['profit'] < 0))
        if gross_loss == 0:
            return float('inf')
        return gross_profit / gross_loss


def main():
    """Run backtest with multiple scenarios."""
    print("🤖 TRADING BOT BACKTEST - NEW MOMENTUM-FOLLOWING STRATEGY")
    print("=" * 80)
    
    # Scenario 1: Synthetic data simulating R_100 behavior
    print("\n" + "=" * 80)
    print("📈 SCENARIO 1: Synthetic R_100 Market (momentum-driven)")
    print("=" * 80)
    runner = BacktestRunner(initial_stake=0.35)
    runner.run(n_ticks=5000, scenario_name="Synthetic R_100")
    
    # Scenario 2: Historical session data (replay actual prices from bot's history)
    print("\n" + "=" * 80)
    print("📉 SCENARIO 2: Historical Session Data Replay")
    print("=" * 80)
    runner2 = BacktestRunner(initial_stake=0.35)
    historical_prices = runner2.load_latest_session_prices()
    if historical_prices:
        runner2.run(price_data=historical_prices, scenario_name="Historical Replay")
    else:
        print("⚠️ No historical session data available. Generating synthetic data instead.")
        runner2.run(n_ticks=3000, scenario_name="Historical (fallback synthetic)")
    
    # Scenario 3: Strong trending market
    print("\n" + "=" * 80)
    print("📈 SCENARIO 3: Strong Trending Market (best case for momentum)")
    print("=" * 80)
    np.random.seed(456)
    trend_prices = [541.0]
    trend_direction = 1
    for i in range(1, 3000):
        if i == 1500:
            trend_direction = -1
        mean = trend_direction * 0.4
        change = np.random.normal(mean, 0.5)
        trend_prices.append(max(530, min(555, trend_prices[-1] + change)))
    
    runner3 = BacktestRunner(initial_stake=0.35)
    runner3.run(n_ticks=3000, price_data=trend_prices, scenario_name="Trending Market")
    
    # Scenario 4: Ranging/churning market (previously worst case)
    print("\n" + "=" * 80)
    print("📊 SCENARIO 4: Ranging Market (previously 40% WR)")
    print("=" * 80)
    np.random.seed(789)
    range_prices = [541.0]
    for i in range(1, 3000):
        change = np.random.normal(0, 0.3)
        range_prices.append(max(539, min(543, range_prices[-1] + change)))
    
    runner4 = BacktestRunner(initial_stake=0.35)
    runner4.run(n_ticks=3000, price_data=range_prices, scenario_name="Ranging Market")
    
    print("\n" + "=" * 80)
    print("✅ BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()