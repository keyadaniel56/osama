"""
Comprehensive backtest of the fixed intelligent trading bot.
Tests ALL subsystems with the new configuration:
- ML predictor (trained on actual price movements)
- RL system (advisory only, not hard veto)
- Decision engine (ML weight 35%)
- Pattern recognition
- Risk management

Uses synthetic price data that mimics Deriv synthetic indices.
"""

import sys
import os
import json
import numpy as np
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from features.indicators import FeatureEngine
from features.pattern_recognition import ChartPatternRecognizer
from market_analyzer import MarketAnalyzer
from decision_engine import DecisionEngine
from risk_manager import RiskManager
from ml_predictor import MLPredictor
from reinforcement_learning import ReinforcementLearningSystem
from config import MODELS_DIR, CONTRACT_DURATION, CONTRACT_DURATION_UNIT


class IntelligentBacktest:
    """
    Tests the bot's intelligence by replaying price data through ALL subsystems.
    Uses the REAL ML predictor, REAL RL system, and REAL decision engine.
    """
    
    def __init__(self, initial_stake: float = 0.35):
        self.initial_stake = initial_stake
        
        # Initialize ALL real subsystems (same as agent.py)
        self.market_analyzer = MarketAnalyzer(window=100)
        self.pattern_recognizer = ChartPatternRecognizer(window=100)
        self.decision_engine = DecisionEngine()
        self.risk_manager = RiskManager()
        self.risk_manager.base_stake = initial_stake
        self.risk_manager.current_stake = initial_stake
        
        # REAL ML predictor - learns from price movements
        self.ml_predictor = MLPredictor(MODELS_DIR, contract_duration_minutes=CONTRACT_DURATION)
        
        # REAL RL system - advisory only (not hard veto)
        self.rl_system = ReinforcementLearningSystem(initial_stake=initial_stake)
        
        # CRITICAL: Disable martingale - it causes net losses despite 64% win rate
        # because 2x-4x stake losses wipe out smaller stake wins
        self.risk_manager.use_martingale = False
        self.risk_manager.martingale_step = 0
        
        # Performance tracking
        self.trades = []
        self.pnl_history = []
        self.equity = initial_stake * 100
        self.peak_equity = self.equity
        self.consecutive_losses = 0
        self.win_count = 0
        self.loss_count = 0
        
        # Track ML accuracy during backtest
        self.ml_predictions = []
        self.ml_correct = 0
        self.ml_total = 0
        
        # Track RL decisions
        self.rl_skip_count = 0
        self.rl_trade_count = 0
        
        # Track decision engine signals
        self.signal_counts = {'ml': 0, 'pattern': 0, 'indicator': 0, 'trend': 0}
        self.ensemble_decisions = 0
        
    def generate_synthetic_prices(self, n_ticks: int = 5000, seed: int = 42) -> List[float]:
        """
        Generate realistic synthetic index prices that mimic Deriv's R_10/R_25/R_50/R_75/R_100.
        Features:
        - Random walk with ~$0.50 per tick volatility
        - Occasional trends (every ~200 ticks, lasting ~30 ticks)
        - Momentum effect (10% of recent trend)
        - Mean reversion at extremes
        - Price range: base ± $30
        """
        np.random.seed(seed)
        base_price = 4885.0
        prices = [base_price]
        
        for i in range(1, n_ticks):
            mean = 0.0
            std = 0.5  # ~$0.50 per tick
            
            # Add occasional trends
            if i % 200 < 30:
                mean = 0.3 if (i // 200) % 2 == 0 else -0.3
            
            # Momentum effect
            if len(prices) >= 3:
                recent_trend = prices[-1] - prices[-3]
                mean += recent_trend * 0.1
            
            # Mean reversion at extremes
            if prices[-1] > base_price + 20:
                mean -= 0.2
            elif prices[-1] < base_price - 20:
                mean += 0.2
            
            change = np.random.normal(mean, std)
            new_price = prices[-1] + change
            new_price = max(base_price - 30, min(base_price + 30, new_price))
            prices.append(new_price)
        
        return prices
    
    def generate_trending_prices(self, n_ticks: int = 3000, seed: int = 123) -> List[float]:
        """Generate strongly trending prices (up then down)."""
        np.random.seed(seed)
        prices = [4885.0]
        trend_dir = 1
        
        for i in range(1, n_ticks):
            if i == 1500:
                trend_dir = -1
            mean = trend_dir * 0.4
            change = np.random.normal(mean, 0.6)
            prices.append(max(4840, min(4940, prices[-1] + change)))
        
        return prices
    
    def generate_volatile_prices(self, n_ticks: int = 3000, seed: int = 456) -> List[float]:
        """Generate high volatility prices."""
        np.random.seed(seed)
        prices = [4885.0]
        
        for i in range(1, n_ticks):
            change = np.random.normal(0, 1.2)
            if i % 150 < 20:
                change += 0.5 if (i // 150) % 2 == 0 else -0.5
            prices.append(max(4850, min(4920, prices[-1] + change)))
        
        return prices
    
    def run(self, n_ticks: int = 5000, price_data: Optional[List[float]] = None, 
            scenario_name: str = "Default") -> Dict:
        """Run backtest simulation with ALL real subsystems."""
        if price_data is None:
            price_data = self.generate_synthetic_prices(n_ticks)
        else:
            n_ticks = len(price_data)
        
        print(f"\n{'='*80}")
        print(f"📊 SCENARIO: {scenario_name}")
        print(f"{'='*80}")
        print(f"   Ticks: {n_ticks} | Price range: ${min(price_data):.2f} - ${max(price_data):.2f}")
        
        WARMUP_TICKS = 200
        cooldown = 0
        trade_count = 0
        last_trade_tick = 0
        trade_cooldown = 50
        
        # Track ML training progress
        ml_trained = False
        
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
            regime = self.market_analyzer.get_market_regime()
            market_health = regime['health']
            
            # Detect patterns
            patterns_detected = self.pattern_recognizer.detect_all_patterns()
            
            # === FEED ML PREDICTOR ===
            # This is critical - the ML learns from actual price movements
            market_data_for_ml = {
                'features': features,
                'price': price,
                'timestamp': datetime.now().isoformat(),
                'symbol': 'R_100'
            }
            
            # Add pattern info to ML features
            if patterns_detected:
                has_bullish = 0.0
                has_bearish = 0.0
                max_conf = 0.0
                for pname, pinfo in patterns_detected.items():
                    conf = pinfo.get('confidence', 0.0)
                    signal = pinfo.get('signal', '')
                    if conf > max_conf:
                        max_conf = conf
                    if 'bullish' in signal or 'upside' in signal or signal == 'up':
                        has_bullish = 1.0
                    elif 'bearish' in signal or 'downside' in signal or signal == 'down':
                        has_bearish = 1.0
                market_data_for_ml['features']['has_bullish_pattern'] = has_bullish
                market_data_for_ml['features']['has_bearish_pattern'] = has_bearish
                market_data_for_ml['features']['pattern_confidence'] = max_conf
            
            self.ml_predictor.observe_market(market_data_for_ml, price)
            
            # Validate ML predictions periodically
            if tick % (CONTRACT_DURATION * 60) == 0 and tick > 0:
                self.ml_predictor.validate_predictions(price)
            
            # === GET ML PREDICTION ===
            ml_direction, ml_confidence = self.ml_predictor.predict(market_data_for_ml)
            ml_prediction = {
                'direction': ml_direction.lower() if ml_direction != 'HOLD' else None,
                'confidence': ml_confidence
            }
            
            if ml_direction != 'HOLD':
                self.ml_total += 1
                if not ml_trained and self.ml_predictor.is_trained:
                    ml_trained = True
                    print(f"   🧠 ML model trained at tick {tick} (acc={self.ml_predictor.model_accuracy:.2%})")
            
            # === GET MULTI-TIMEFRAME TREND ===
            multi_tf_trend = None
            if hasattr(self.pattern_recognizer, 'multi_tf_analyzer'):
                tf_analysis = self.pattern_recognizer.multi_tf_analyzer.get_aligned_trend()
                if tf_analysis['is_trending']:
                    multi_tf_trend = tf_analysis
            
            # === PREPARE PATTERN DATA ===
            pattern_data = None
            if patterns_detected:
                pattern_data = {'patterns': {}}
                for pname, pinfo in patterns_detected.items():
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
                        'confidence': pinfo.get('confidence', 0.5),
                        'signal': signal
                    }
            
            # === DECISION ENGINE ===
            indicators = features
            rsi = indicators.get('rsi', 50)
            bb_position = indicators.get('bb_position', 0.5)
            
            # Intelligent mean reversion guard (same as fixed agent.py)
            has_ml_signal = ml_direction not in (None, 'HOLD')
            
            if (rsi > 80 or rsi < 20) or (bb_position > 0.90 or bb_position < 0.10):
                has_trend_data = multi_tf_trend is not None and multi_tf_trend.get('is_trending')
                
                if rsi > 80 or bb_position > 0.90:
                    if has_trend_data and multi_tf_trend.get('primary_direction') == 'up':
                        if has_ml_signal and ml_direction == 'UP':
                            continue  # All evidence says trend continues
                
                if rsi < 20 or bb_position < 0.10:
                    if has_trend_data and multi_tf_trend.get('primary_direction') == 'down':
                        if has_ml_signal and ml_direction == 'DOWN':
                            continue  # All evidence says trend continues
            
            # Pattern contradiction check
            if pattern_data and 'patterns' in pattern_data:
                bullish_count = sum(1 for p in pattern_data['patterns'].values() if p['type'] == 'bullish')
                bearish_count = sum(1 for p in pattern_data['patterns'].values() if p['type'] == 'bearish')
                if bullish_count > 0 and bearish_count > 0 and bullish_count == bearish_count:
                    continue
            
            # Make decision
            trade_dir, ensemble_confidence = self.decision_engine.make_decision(
                ml_prediction=ml_prediction,
                patterns=pattern_data,
                indicators=indicators,
                market_state=market_state,
                market_health=market_health,
                multi_tf_trend=multi_tf_trend
            )
            
            # Track signal sources
            if trade_dir:
                self.ensemble_decisions += 1
            
            # === RL SYSTEM (ADVISORY ONLY) ===
            rl_should_trade = True
            rl_q_skip = 0.0
            rl_q_take = 0.0
            if hasattr(self, 'rl_system'):
                rl_should_trade, rl_q_skip, rl_q_take = self.rl_system.decide(indicators)
                self.rl_system.record_trade_execution(1 if rl_should_trade else 0)
                
                if not rl_should_trade:
                    self.rl_skip_count += 1
                else:
                    self.rl_trade_count += 1
            
            # RL is advisory - reduce confidence but don't block
            if not rl_should_trade:
                rl_certainty = min(abs(rl_q_take - rl_q_skip), 1.0)
                confidence_penalty = 0.15 + rl_certainty * 0.25
                ensemble_confidence = max(ensemble_confidence - confidence_penalty, 0.0)
            
            # === RISK CHECK ===
            can_trade = self.risk_manager.should_trade(ensemble_confidence, market_health)
            
            # Cooldown
            ticks_since_last = tick - last_trade_tick
            cooldown_ready = ticks_since_last >= trade_cooldown
            
            # === EXECUTE TRADE ===
            if (trade_dir and ensemble_confidence >= 0.65 and can_trade and cooldown_ready
                and len(self.trades) < 100):
                
                prediction = 'RISE' if trade_dir == 'up' else 'FALL'
                contract_type = 'CALL' if trade_dir == 'up' else 'PUT'
                
                volatility = features.get('volatility', 0.5)
                position_size = self.risk_manager.calculate_position_size(
                    ensemble_confidence, volatility, trade_direction=trade_dir
                )
                
                # Look ahead contract_duration ticks to see outcome
                contract_duration_ticks = CONTRACT_DURATION * 60  # minutes to ticks
                end_tick = min(tick + contract_duration_ticks, n_ticks - 1)
                future_price = price_data[end_tick]
                
                # Determine if trade wins
                if contract_type == 'CALL':
                    won = future_price > price
                else:
                    won = future_price < price
                
                # Calculate profit
                if won:
                    profit = position_size * 0.80  # ~80% payout
                    self.win_count += 1
                    self.consecutive_losses = 0
                else:
                    profit = -position_size
                    self.loss_count += 1
                    self.consecutive_losses += 1
                
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
                    'confidence': ensemble_confidence,
                    'position': position_size,
                    'won': won,
                    'profit': profit,
                    'state': market_state,
                    'health': market_health,
                    'rsi': rsi,
                    'bb_pos': bb_position,
                    'volatility': volatility,
                    'patterns': list(patterns_detected.keys()) if patterns_detected else [],
                    'ml_signal': ml_direction if ml_direction != 'HOLD' else None,
                    'ml_conf': ml_confidence,
                    'rl_skip': not rl_should_trade,
                    'rl_q_skip': rl_q_skip,
                    'rl_q_take': rl_q_take,
                })
                
                self.pnl_history.append(self.equity)
                trade_count += 1
                
                # Update RL system with result
                if hasattr(self, 'rl_system'):
                    self.rl_system.record_trade_result(profit, won, features)
                
                # Update risk manager
                self.risk_manager.record_trade_result(position_size, won, profit)
                
                last_trade_tick = tick
            
            # Log progress
            if tick % 1000 == 0 and tick > 0:
                print(f"   Progress: tick {tick}/{n_ticks} | Trades: {trade_count} | "
                      f"Equity: ${self.equity:.2f} | ML trained: {ml_trained}")
        
        # Print results
        results = self._print_results(scenario_name)
        return results
    
    def _print_results(self, scenario_name: str) -> Dict:
        """Print and return backtest results."""
        total = len(self.trades)
        wins = sum(1 for t in self.trades if t['won'])
        losses = sum(1 for t in self.trades if not t['won'])
        win_rate = wins / total if total > 0 else 0
        
        total_profit = sum(t['profit'] for t in self.trades)
        avg_profit = total_profit / total if total > 0 else 0
        
        # Calculate max drawdown
        max_dd = 0.0
        peak = self.initial_stake * 100
        for v in self.pnl_history:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            max_dd = max(max_dd, dd)
        
        # Profit factor
        gross_profit = sum(t['profit'] for t in self.trades if t['profit'] > 0)
        gross_loss = abs(sum(t['profit'] for t in self.trades if t['profit'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Max consecutive losses
        max_consec = 0
        current_consec = 0
        for t in self.trades:
            if not t['won']:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0
        
        # ML accuracy
        ml_accuracy = self.ml_predictor.model_accuracy if self.ml_predictor.is_trained else 0
        
        # RL stats
        rl_stats = self.rl_system.get_stats() if hasattr(self, 'rl_system') else {}
        
        print(f"\n{'='*80}")
        print(f"📊 RESULTS: {scenario_name}")
        print(f"{'='*80}")
        print(f"📈 TRADES: {total}")
        print(f"   Wins: {wins}  Losses: {losses}  Win Rate: {win_rate:.1%}")
        print(f"   Total P&L: ${total_profit:.2f}")
        print(f"   Avg Profit/Trade: ${avg_profit:.2f}")
        print(f"   Profit Factor: {profit_factor:.2f}x")
        print(f"   Max Drawdown: {max_dd:.1f}%")
        print(f"   Max Consec Losses: {max_consec}")
        print(f"   Final Equity: ${self.equity:.2f}")
        print(f"   Return: {((self.equity / (self.initial_stake * 100)) - 1) * 100:.1f}%")
        
        print(f"\n🧠 ML SYSTEM:")
        print(f"   Trained: {self.ml_predictor.is_trained}")
        print(f"   Model Accuracy: {ml_accuracy:.2%}")
        print(f"   Training Samples: {len(self.ml_predictor.training_buffer)}")
        print(f"   Predictions Made: {self.ml_predictor.predictions_made}")
        
        print(f"\n🧠 RL SYSTEM:")
        print(f"   Training Batches: {rl_stats.get('rl_trained', 0)}")
        print(f"   Epsilon: {rl_stats.get('rl_epsilon', 1.0):.3f}")
        print(f"   RL Skip Count: {self.rl_skip_count}")
        print(f"   RL Trade Count: {self.rl_trade_count}")
        print(f"   Stake: ${rl_stats.get('stake', 0.35):.2f}")
        
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
        
        # Sample trades
        if self.trades:
            print(f"\n📋 SAMPLE TRADES (last 5):")
            for t in self.trades[-5:]:
                result = "✅" if t['won'] else "❌"
                pat_str = ", ".join(t['patterns'][:2]) if t['patterns'] else "none"
                print(f"   {result} Tick {t['tick']:5} | ${t['price']:.2f} | "
                      f"{t['direction'].upper():4} | Conf: {t['confidence']:.2f} | "
                      f"RSI: {t['rsi']:.0f} | State: {t['state']:15} | "
                      f"ML: {str(t['ml_signal']):4} | PnL: ${t['profit']:+.2f}")
        
        print(f"\n{'='*80}\n")
        
        return {
            'scenario': scenario_name,
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'avg_profit': avg_profit,
            'profit_factor': profit_factor,
            'max_drawdown': max_dd,
            'max_consec_losses': max_consec,
            'final_equity': self.equity,
            'return_pct': ((self.equity / (self.initial_stake * 100)) - 1) * 100,
            'ml_accuracy': ml_accuracy,
            'ml_trained': self.ml_predictor.is_trained,
            'rl_trained': rl_stats.get('rl_trained', 0),
            'rl_skip_count': self.rl_skip_count,
            'rl_trade_count': self.rl_trade_count,
        }


def main():
    """Run comprehensive backtest across multiple scenarios."""
    print("=" * 80)
    print("🤖 INTELLIGENT TRADING BOT - COMPREHENSIVE BACKTEST")
    print("   Testing: ML Predictor | RL System | Decision Engine | Pattern Recognition")
    print("   Configuration: ML weight=35% | RL=advisory | min_advantage=0.01")
    print("=" * 80)
    
    all_results = []
    
    # Scenario 1: Normal market (R_10-like)
    bt1 = IntelligentBacktest(initial_stake=0.35)
    r1 = bt1.run(n_ticks=5000, scenario_name="Normal Market (R_10-like)")
    all_results.append(r1)
    
    # Scenario 2: Strong trending market
    bt2 = IntelligentBacktest(initial_stake=0.35)
    trend_prices = bt2.generate_trending_prices(3000)
    r2 = bt2.run(n_ticks=3000, price_data=trend_prices, scenario_name="Strong Trending Market")
    all_results.append(r2)
    
    # Scenario 3: High volatility market
    bt3 = IntelligentBacktest(initial_stake=0.35)
    volatile_prices = bt3.generate_volatile_prices(3000)
    r3 = bt3.run(n_ticks=3000, price_data=volatile_prices, scenario_name="High Volatility Market")
    all_results.append(r3)
    
    # Scenario 4: Longer run with different seed
    bt4 = IntelligentBacktest(initial_stake=0.35)
    prices4 = bt4.generate_synthetic_prices(5000, seed=789)
    r4 = bt4.run(n_ticks=5000, price_data=prices4, scenario_name="Normal Market (seed=789)")
    all_results.append(r4)
    
    # Summary
    print("\n" + "=" * 80)
    print("📈 OVERALL SUMMARY")
    print("=" * 80)
    
    total_trades = sum(r['total_trades'] for r in all_results)
    total_wins = sum(r['wins'] for r in all_results)
    total_losses = sum(r['losses'] for r in all_results)
    total_profit = sum(r['total_profit'] for r in all_results)
    
    print(f"\n   Total Trades Across All Scenarios: {total_trades}")
    print(f"   Total Wins: {total_wins}  Total Losses: {total_losses}")
    print(f"   Overall Win Rate: {total_wins/total_trades*100:.1f}%" if total_trades > 0 else "   No trades")
    print(f"   Total P&L: ${total_profit:.2f}")
    
    # Check if bot is trading properly
    if total_trades == 0:
        print("\n⚠️  WARNING: Bot placed ZERO trades across all scenarios!")
        print("   The RL system or indicator guards may still be too restrictive.")
    elif total_trades < 10:
        print(f"\n⚠️  WARNING: Only {total_trades} trades placed - may be too conservative.")
    else:
        print(f"\n✅ Bot is actively trading ({total_trades} trades across {len(all_results)} scenarios)")
    
    # Check ML learning
    ml_trained_any = any(r['ml_trained'] for r in all_results)
    if ml_trained_any:
        avg_ml_acc = np.mean([r['ml_accuracy'] for r in all_results if r['ml_trained']])
        print(f"✅ ML model trained and learning (avg accuracy: {avg_ml_acc:.2%})")
    else:
        print("⚠️  ML model did not train - may need more ticks")
    
    # Check RL behavior
    total_rl_skip = sum(r['rl_skip_count'] for r in all_results)
    total_rl_trade = sum(r['rl_trade_count'] for r in all_results)
    if total_rl_skip > 0 and total_rl_trade > 0:
        print(f"✅ RL system is working: {total_rl_skip} skips, {total_rl_trade} trades (advisory mode)")
    elif total_rl_skip > 0 and total_rl_trade == 0:
        print("⚠️  RL is still blocking all trades - check min_advantage and weights")
    
    print(f"\n{'='*80}")
    print("✅ BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()