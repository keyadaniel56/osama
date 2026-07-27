"""
Quick test to verify the bot's strategy logic is correct.
Tests the core hypothesis: momentum-following vs mean-reversion on synthetic indices.
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from features.indicators import FeatureEngine
from strategies.rise_fall import RiseFallStrategy


def test_momentum_hypothesis():
    """
    Test the core hypothesis: Do synthetic indices have momentum?
    """
    print("=" * 60)
    print("TESTING MOMENTUM HYPOTHESIS ON SYNTHETIC DATA")
    print("=" * 60)
    
    np.random.seed(42)
    
    n_ticks = 10000
    prices = [541.0]
    
    for i in range(1, n_ticks):
        mean = 0.0
        std = 0.5
        if len(prices) >= 5:
            recent_trend = prices[-1] - prices[-5]
            mean += recent_trend * 0.15
        if i % 300 < 40:
            mean += 0.4 if (i // 300) % 2 == 0 else -0.4
        change = np.random.normal(mean, std)
        new_price = max(520, min(562, prices[-1] + change))
        prices.append(new_price)
    
    fe = FeatureEngine(window=100)
    
    momentum_up_correct = 0
    momentum_up_total = 0
    momentum_down_correct = 0
    momentum_down_total = 0
    rsi_high_up = 0
    rsi_high_total = 0
    rsi_low_down = 0
    rsi_low_total = 0
    bb_extreme_continue = 0
    bb_extreme_total = 0
    
    for i in range(200, n_ticks - 300):
        fe.add_price(prices[i], volume=1.0)
        if len(fe.indicators.prices) < 30:
            continue
        
        features = fe.extract_features()
        momentum_10 = features.get('momentum_10', 0.0)
        rsi = features.get('rsi', 50.0)
        bb_position = features.get('bb_position', 0.5)
        
        future_price = prices[i + 300]
        price_moved_up = future_price > prices[i]
        
        if momentum_10 > 0.2:
            momentum_up_total += 1
            if price_moved_up:
                momentum_up_correct += 1
        if momentum_10 < -0.2:
            momentum_down_total += 1
            if not price_moved_up:
                momentum_down_correct += 1
        if rsi > 60:
            rsi_high_total += 1
            if price_moved_up:
                rsi_high_up += 1
        if rsi < 40:
            rsi_low_total += 1
            if not price_moved_up:
                rsi_low_down += 1
        if bb_position > 0.9 or bb_position < 0.1:
            bb_extreme_total += 1
            if (bb_position > 0.9 and price_moved_up) or (bb_position < 0.1 and not price_moved_up):
                bb_extreme_continue += 1
    
    print(f"\n📊 MOMENTUM HYPOTHESIS (300-tick forward test):")
    print(f"   Positive momentum > 0.2: {momentum_up_correct}/{momentum_up_total} = {momentum_up_correct/max(1,momentum_up_total)*100:.1f}% continued UP")
    print(f"   Negative momentum < -0.2: {momentum_down_correct}/{momentum_down_total} = {momentum_down_correct/max(1,momentum_down_total)*100:.1f}% continued DOWN")
    print(f"\n📊 RSI HYPOTHESIS:")
    print(f"   RSI > 60: {rsi_high_up}/{rsi_high_total} = {rsi_high_up/max(1,rsi_high_total)*100:.1f}% continued UP")
    print(f"   RSI < 40: {rsi_low_down}/{rsi_low_total} = {rsi_low_down/max(1,rsi_low_total)*100:.1f}% continued DOWN")
    print(f"\n📊 BB EXTREME HYPOTHESIS:")
    print(f"   BB extreme: {bb_extreme_continue}/{bb_extreme_total} = {bb_extreme_continue/max(1,bb_extreme_total)*100:.1f}% continued")
    
    print(f"\n💰 PROFITABILITY ANALYSIS:")
    print(f"   Deriv payout: 80% on win, -100% on loss")
    print(f"   Break-even win rate: {1/1.8*100:.1f}%")


def test_rise_fall_strategy():
    """
    Test the new RiseFallStrategy on synthetic data.
    Tests different confidence thresholds to find the optimal cutoff.
    """
    print("\n" + "=" * 60)
    print("TESTING RISE/FALL STRATEGY WITH CONFIDENCE FILTERS")
    print("=" * 60)
    
    np.random.seed(42)
    
    n_ticks = 10000
    prices = [541.0]
    
    for i in range(1, n_ticks):
        mean = 0.0
        std = 0.5
        if len(prices) >= 5:
            recent_trend = prices[-1] - prices[-5]
            mean += recent_trend * 0.15
        if i % 300 < 40:
            mean += 0.4 if (i // 300) % 2 == 0 else -0.4
        change = np.random.normal(mean, std)
        new_price = max(520, min(562, prices[-1] + change))
        prices.append(new_price)
    
    strategy = RiseFallStrategy(base_stake=0.35)
    fe = FeatureEngine(window=100)
    
    all_trades = []
    
    for i in range(200, n_ticks - 300):
        fe.add_price(prices[i], volume=1.0)
        if len(fe.indicators.prices) < 30:
            continue
        
        features = fe.extract_features()
        market_data = {'features': features, 'price': prices[i]}
        
        signal = strategy.analyze(market_data)
        
        if signal.action == 'BUY':
            future_price = prices[i + 300]
            
            if signal.contract_type == 'RISE':
                won = future_price > prices[i]
            else:
                won = future_price < prices[i]
            
            all_trades.append({
                'won': won,
                'contract': signal.contract_type,
                'confidence': signal.confidence,
                'rsi': features.get('rsi', 50),
                'momentum': features.get('momentum_10', 0),
            })
    
    total = len(all_trades)
    if total > 0:
        print(f"\n📊 ALL TRADES ({total}):")
        wr = sum(1 for t in all_trades if t['won']) / total * 100
        print(f"   Win Rate: {wr:.1f}%")
        print(f"   {'✅ PROFITABLE' if wr > 55.6 else '❌ NOT PROFITABLE'} (need >55.6%)")
        
        # Test different confidence thresholds
        print(f"\n📊 PERFORMANCE BY CONFIDENCE THRESHOLD:")
        print(f"   {'Threshold':>10} | {'Trades':>6} | {'WR':>5} | {'Profitable?':>12}")
        print(f"   {'-'*10} | {'-'*6} | {'-'*5} | {'-'*12}")
        
        for threshold in [0.80, 0.82, 0.84, 0.85, 0.86, 0.87, 0.88, 0.89, 0.90]:
            filtered = [t for t in all_trades if t['confidence'] >= threshold]
            if filtered:
                f_wr = sum(1 for t in filtered if t['won']) / len(filtered) * 100
                profitable = "✅" if f_wr > 55.6 else "❌"
                print(f"   {threshold:>10.2f} | {len(filtered):>6} | {f_wr:>4.1f}% | {profitable:>12}")
        
        # Show last 10 trades
        print(f"\n📋 LAST 10 TRADES:")
        for t in all_trades[-10:]:
            mark = "✓" if t['won'] else "✗"
            print(f"   {mark} {t['contract']:4} | RSI={t['rsi']:.0f} | mom={t['momentum']:+.3f} | conf={t['confidence']:.2f}")


if __name__ == "__main__":
    test_momentum_hypothesis()
    test_rise_fall_strategy()