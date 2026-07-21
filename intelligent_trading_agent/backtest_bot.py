"""
Backtest the fixed trading agent against historical market data.
Replays price data from session logs and tests the improved decision engine,
pattern recognition, RL system, and risk management.

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
from config import MODELS_DIR


class BacktestRunner:
    """
    Replays historical price data through the bot's subsystems.
    Tests: market analysis, pattern detection, decision engine, RL system, risk management.
    Does NOT connect to Deriv or place real trades.
    """
    
    def __init__(self, initial_stake: float = 0.35):
        self.initial_stake = initial_stake
        
        # Initialize bot subsystems (same as agent.py)
        self.market_analyzer = MarketAnalyzer(window=100)
        self.pattern_recognizer = ChartPatternRecognizer(window=100)
        self.decision_engine = DecisionEngine()
        self.risk_manager = RiskManager()
        
        # Override risk manager's base stake
        self.risk_manager.base_stake = initial_stake
        self.risk_manager.current_stake = initial_stake
        
        # Try to import RL system (may not be available)
        self.rl_system = None
        try:
            from reinforcement_learning import ReinforcementLearningSystem
            self.rl_system = ReinforcementLearningSystem(initial_stake=initial_stake)
            self.has_rl = True
        except ImportError:
            self.has_rl = False
        
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
    
    def extract_price_data(self, session_file: str) -> List[float]:
        """Extract price data from a session file."""
        prices = []
        try:
            with open(session_file, 'r') as f:
                data = json.load(f)
            
            trades = data.get('trades', [])
            for trade in trades:
                market_data = trade.get('market_data', {})
                if market_data:
                    price = market_data.get('price', 0)
                    if price > 0:
                        prices.append(price)
                
                features = market_data.get('features', {})
                entry_price = trade.get('entry_price', 0)
                if entry_price > 0 and isinstance(entry_price, (int, float)):
                    prices.append(entry_price)
        except Exception as e:
            print(f"  ⚠️ Error extracting prices from {session_file}: {e}")
        
        return prices
    
    def generate_synthetic_prices(self, n_ticks: int = 5000, base_price: float = 4885.0) -> List[float]:
        """
        Generate realistic synthetic index prices.
        Models R_10 behavior: rapid oscillations with occasional trends.
        """
        np.random.seed(42)
        prices = [base_price]
        
        for i in range(1, n_ticks):
            # Random walk with R_10 characteristics
            mean = 0.0
            std = 0.5  # ~$0.50 per tick volatility
            
            # Add occasional trends (every ~200 ticks)
            if i % 200 < 30:  # 30-tick trend
                mean = 0.3 if (i // 200) % 2 == 0 else -0.3
            
            # Add momentum effect
            if len(prices) >= 3:
                recent_trend = prices[-1] - prices[-3]
                mean += recent_trend * 0.1  # 10% momentum
            
            # Generate next price
            change = np.random.normal(mean, std)
            new_price = prices[-1] + change
            
            # Keep prices in realistic range
            new_price = max(base_price - 30, min(base_price + 30, new_price))
            prices.append(new_price)
        
        return prices
    
    def run(self, n_ticks: int = 3000, price_data: Optional[List[float]] = None):
        """Run backtest simulation."""
        if price_data is None:
            print(f"\n🔄 Generating {n_ticks} ticks of synthetic price data...")
            price_data = self.generate_synthetic_prices(n_ticks)
        else:
            n_ticks = len(price_data)
            print(f"\n🔄 Using {n_ticks} historical price points")
        
        print(f"   Price range: ${min(price_data):.2f} - ${max(price_data):.2f}")
        
        # Track results
        decisions = []
        signals_log = []
        patterns_log = []
        
        WARMUP_TICKS = 200
        cooldown = 0
        trade_count = 0
        win_count = 0
        loss_count = 0
        
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
            
            # Detect patterns
            patterns = self.pattern_recognizer.detect_all_patterns()
            
            # Get ML prediction (simplified - use indicator-based)
            indicators = features
            rsi = indicators.get('rsi', 50)
            bb_position = indicators.get('bb_position', 0.5)
            macd = indicators.get('macd_histogram', 0)
            
            # Build mock ML prediction from indicators
            if rsi > 60 and macd > 0:
                ml_dir = 'up'
                ml_conf = min((rsi - 50) / 50 + 0.5, 0.85)
            elif rsi < 40 and macd < 0:
                ml_dir = 'down'
                ml_conf = min((50 - rsi) / 50 + 0.5, 0.85)
            else:
                ml_dir = None
                ml_conf = 0.0
            
            ml_prediction = {
                'direction': ml_dir,
                'confidence': ml_conf
            }
            
            # Get pattern data
            pattern_data = None
            if patterns:
                pattern_data = {'patterns': {}}
                for pname, pinfo in patterns.items():
                    signal = pinfo.get('signal', '')
                    ptype = None
                    if 'bullish' in signal or 'up' in signal:
                        ptype = 'bullish'
                    elif 'bearish' in signal or 'down' in signal:
                        ptype = 'bearish'
                    else:
                        ptype = 'neutral'
                    pattern_data['patterns'][pname] = {
                        'type': ptype,
                        'confidence': pinfo.get('confidence', 0.5)
                    }
            
            # Trend guard check (simplified)
            # Skip if RSI is extreme and would go against trend
            if rsi > 70:
                # Check multi-tf trend
                tf_analysis = self.pattern_recognizer.multi_tf_analyzer.get_aligned_trend()
                if tf_analysis.get('is_trending') and tf_analysis.get('primary_direction') == 'up':
                    # Overbought + uptrend: let it ride
                    pass
            
            # Make decision
            trade_dir, confidence = self.decision_engine.make_decision(
                ml_prediction=ml_prediction,
                patterns=pattern_data,
                indicators=indicators,
                market_state=market_state,
                market_health=market_health
            )
            
            # Check risk constraints
            can_trade = self.risk_manager.should_trade(confidence, market_health)
            
            # Decrement cooldown
            if cooldown > 0:
                cooldown -= 1
            
            # Record decisions periodically
            if tick % 500 == 0:
                decisions.append({
                    'tick': tick,
                    'price': price,
                    'state': market_state,
                    'health': market_health,
                    'direction': trade_dir,
                    'confidence': confidence,
                    'rsi': rsi,
                    'bb_pos': bb_position,
                    'patterns': list(patterns.keys()) if patterns else [],
                    'macro_hist': macd,
                })
            
            # Log patterns detected
            if patterns and tick % 300 == 0:
                pattern_names = list(patterns.keys())
                patterns_log.append({
                    'tick': tick,
                    'patterns': pattern_names,
                    'signals': [p.get('signal', '') for p in patterns.values()],
                    'confidences': [p.get('confidence', 0) for p in patterns.values()]
                })
            
            # Simulate trade
            if (trade_dir and confidence >= 0.65 and can_trade and cooldown == 0 
                and len(self.trades) < 50):  # Limit to 50 trades for backtest
                
                # Determine direction prediction
                prediction = 'RISE' if trade_dir == 'up' else 'FALL'
                contract_type = 'CALL' if trade_dir == 'up' else 'PUT'
                
                # Calculate position size
                volatility = features.get('volatility', 0.5)
                position_size = self.risk_manager.calculate_position_size(
                    confidence, volatility, trade_direction=trade_dir
                )
                
                # Check if RL system allows this trade
                rl_blocks = False
                if self.has_rl and self.rl_system:
                    rl_should, _, _ = self.rl_system.decide(features)
                    if not rl_should and self.rl_system.rl_engine.training_count > 5:
                        rl_blocks = True
                
                if rl_blocks:
                    continue
                
                # Look ahead contract_duration ticks to see outcome
                contract_duration_ticks = 300  # 5 minutes ≈ 300 ticks
                end_tick = min(tick + contract_duration_ticks, n_ticks - 1)
                future_price = price_data[end_tick]
                
                # Determine if trade wins
                if contract_type == 'CALL':
                    won = future_price > price + (position_size * 0.01)  # Need price to go up enough
                else:
                    won = future_price < price - (position_size * 0.01)
                
                # Calculate profit
                if won:
                    profit = position_size * 0.80  # ~80% payout
                    win_count += 1
                else:
                    profit = -position_size
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
                    'prediction': prediction,
                    'confidence': confidence,
                    'position': position_size,
                    'won': won,
                    'profit': profit,
                    'state': market_state,
                    'rsi': rsi,
                    'bb_pos': bb_position,
                    'volatility': volatility,
                    'patterns': list(patterns.keys()) if patterns else [],
                })
                
                self.pnl_history.append(self.equity)
                trade_count += 1
                
                # Update RL system
                if self.has_rl and self.rl_system:
                    self.rl_system.record_trade_result(profit, won, features)
                
                # Update risk manager
                self.risk_manager.record_trade_result(position_size, won, profit)
                
                # Set cooldown
                cooldown = 50  # ticks
        
        # Print results
        self.print_results(decisions, patterns_log)
        
        return self.trades, self.pnl_history
    
    def print_results(self, decisions: List[Dict], patterns_log: List[Dict]):
        """Print backtest results."""
        print("\n" + "="*80)
        print("📊 BACKTEST RESULTS")
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
        print(f"   Return: {((self.equity / (self.initial_stake * 100)) - 1) * 100:.1f}%")
        
        # Stake growth
        stake_growth = 1.0
        if self.has_rl and self.rl_system:
            stake = self.rl_system.compounder.get_current_stake()
            stake_growth = stake / self.initial_stake
            print(f"\n💰 STAKE GROWTH: ${self.initial_stake:.2f} → ${stake:.2f} ({stake_growth:.1f}x)")
            
            rl_stats = self.rl_system.get_stats()
            print(f"🧠 RL TRAINING: {rl_stats['rl_trained']} batches, ε={rl_stats['rl_epsilon']:.3f}")
        
        # Performance by market state
        print(f"\n📊 PERFORMANCE BY MARKET STATE:")
        states = {}
        for t in self.trades:
            s = t['state']
            if s not in states:
                states[s] = {'trades': 0, 'wins': 0, 'profit': 0.0}
            states[s]['trades'] += 1
            states[s]['wins'] += 1 if t['won'] else 0
            states[s]['profit'] += t['profit']
        
        for state, data in sorted(states.items(), key=lambda x: x[1]['trades'], reverse=True):
            wr = data['wins'] / data['trades'] * 100
            print(f"   {state:20} | {data['trades']:3} trades | {wr:5.1f}% WR | ${data['profit']:+.2f}")
        
        # Performance by RSI zone
        print(f"\n📊 PERFORMANCE BY RSI ZONE:")
        zones = {'Oversold (<30)': [], 'Neutral (30-70)': [], 'Overbought (>70)': []}
        for t in self.trades:
            if t['rsi'] < 30:
                zones['Oversold (<30)'].append(t)
            elif t['rsi'] > 70:
                zones['Overbought (>70)'].append(t)
            else:
                zones['Neutral (30-70)'].append(t)
        
        for zone, trades in zones.items():
            if trades:
                wr = sum(1 for t in trades if t['won']) / len(trades) * 100
                pnl = sum(t['profit'] for t in trades)
                print(f"   {zone:20} | {len(trades):3} trades | {wr:5.1f}% WR | ${pnl:+.2f}")
        
        # Pattern detection stats
        all_patterns = {}
        for entry in patterns_log:
            for p in entry['patterns']:
                all_patterns[p] = all_patterns.get(p, 0) + 1
        
        if all_patterns:
            print(f"\n🔍 PATTERNS DETECTED ({len(all_patterns)} types):")
            for pname, count in sorted(all_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"   {pname:25} | {count:4} times")
        
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
        print(f"   Current Stake: ${self.risk_manager.current_stake:.2f}")
        
        # Print recent decisions
        print(f"\n📋 SAMPLE DECISIONS (every 500 ticks):")
        for d in decisions[:10]:
            pat_str = ", ".join(d['patterns'][:3]) if d['patterns'] else "none"
            if len(d['patterns']) > 3:
                pat_str += f" +{len(d['patterns'])-3} more"
            print(f"   Tick {d['tick']:5} | ${d['price']:.2f} | State: {d['state']:15} | "
                  f"Health: {d['health']:.0f} | RSI: {d['rsi']:.0f} | "
                  f"Dir: {str(d['direction']):4} | Patterns: {pat_str}")
        
        print("\n" + "="*80)
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage."""
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
    print("🤖 TRADING BOT BACKTEST")
    print("=" * 80)
    
    runner = BacktestRunner(initial_stake=0.35)
    
    # Scenario 1: Synthetic data (R_10-like)
    print("\n" + "=" * 80)
    print("📈 SCENARIO 1: Synthetic R_10 Market Data")
    print("=" * 80)
    runner.run(n_ticks=5000)
    
    # Scenario 2: Volatile market
    print("\n" + "=" * 80)
    print("📉 SCENARIO 2: High Volatility Market")
    print("=" * 80)
    np.random.seed(123)
    volatile_prices = [4885.0]
    for i in range(1, 3000):
        change = np.random.normal(0, 1.2)  # Higher volatility
        if i % 150 < 20:
            change += 0.5 if (i // 150) % 2 == 0 else -0.5
        volatile_prices.append(max(4850, min(4920, volatile_prices[-1] + change)))
    
    runner2 = BacktestRunner(initial_stake=0.35)
    runner2.run(n_ticks=3000, price_data=volatile_prices)
    
    # Scenario 3: Trending market
    print("\n" + "=" * 80)
    print("📈 SCENARIO 3: Strong Trending Market")
    print("=" * 80)
    np.random.seed(456)
    trend_prices = [4885.0]
    trend_direction = 1
    for i in range(1, 3000):
        # Strong bias for first half (up), then reverse (down)
        if i == 1500:
            trend_direction = -1
        mean = trend_direction * 0.4
        change = np.random.normal(mean, 0.6)
        trend_prices.append(max(4840, min(4940, trend_prices[-1] + change)))
    
    runner3 = BacktestRunner(initial_stake=0.35)
    runner3.run(n_ticks=3000, price_data=trend_prices)
    
    print("\n✅ BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()