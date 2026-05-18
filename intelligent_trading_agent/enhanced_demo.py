"""
Enhanced Demo - Multi-Market Monitoring & Pattern Recognition
Demonstrates the intelligent agent monitoring multiple markets and recognizing patterns.
"""

from multi_market_monitor import MultiMarketMonitor
from features.pattern_recognition import ChartPatternRecognizer
import random
import numpy as np


def generate_trending_prices(base_price=100.0, num_ticks=150, trend=0.01):
    """Generate prices with trend for testing."""
    prices = [base_price]
    for _ in range(num_ticks):
        trend_move = random.gauss(trend, 0.01)
        noise = random.gauss(0, 0.3)
        next_price = prices[-1] * (1 + trend_move + noise / prices[-1])
        prices.append(max(next_price, 1.0))
    return prices


def generate_consolidation_prices(base_price=100.0, num_ticks=150):
    """Generate consolidating price pattern."""
    prices = [base_price]
    for _ in range(num_ticks):
        # Small noise with mean reversion
        noise = random.gauss(0, 0.2)
        next_price = prices[-1] * (1 + noise / prices[-1])
        prices.append(max(next_price, 1.0))
    return prices


def demo_pattern_recognition():
    """Demonstrate chart pattern recognition."""
    print("\n" + "="*70)
    print("DEMO 1: CHART PATTERN RECOGNITION")
    print("="*70)
    
    recognizer = ChartPatternRecognizer(window=100)
    
    # Test with different price patterns
    patterns_to_test = [
        ('Head & Shoulders', generate_trending_prices(100, 150, trend=-0.02)),
        ('Double Bottom (Recovery)', generate_trending_prices(100, 150, trend=0.02)),
        ('Consolidation', generate_consolidation_prices(100, 150)),
    ]
    
    for pattern_name, prices in patterns_to_test:
        recognizer = ChartPatternRecognizer(window=100)
        
        print(f"\nTesting {pattern_name} pattern...")
        print(f"  Generating {len(prices)} price ticks...")
        
        for price in prices:
            recognizer.add_price(price)
        
        patterns = recognizer.detect_all_patterns()
        
        if patterns:
            print(f"  ✓ Detected {len(patterns)} patterns:")
            for pattern_key, pattern_data in patterns.items():
                signal = pattern_data.get('signal', 'unknown')
                confidence = pattern_data.get('confidence', 0.0)
                print(f"    - {pattern_key}: {signal} ({confidence:.0%})")
        else:
            print(f"  No patterns detected (normal for random prices)")


def demo_multi_market_monitoring():
    """Demonstrate multi-market monitoring."""
    print("\n" + "="*70)
    print("DEMO 2: MULTI-MARKET MONITORING")
    print("="*70)
    
    symbols = ['R_100', 'R_75', 'R_50', 'R_25', 'R_10']
    monitor = MultiMarketMonitor(symbols, base_stake=1.0)
    
    print(f"\nMonitoring {len(symbols)} markets simultaneously...")
    
    # Generate different market conditions for each symbol
    market_data = {}
    for i, symbol in enumerate(symbols):
        # Each symbol gets different market condition
        if i % 2 == 0:
            prices = generate_trending_prices(100 + i*5, 100, trend=0.01)
        else:
            prices = generate_consolidation_prices(100 + i*5, 100)
        
        # Update monitor
        for price in prices:
            monitor.update_market(symbol, price)
        
        # Create market data for scanning
        market_data[symbol] = {
            'features': monitor.analyzers[symbol].feature_engine.extract_features(),
            'price': prices[-1],
        }
    
    # Scan all markets
    opportunities = monitor.scan_all_markets(market_data)
    
    print(f"\n✓ Scan Complete:")
    print(f"  Markets monitored: {len(symbols)}")
    print(f"  Opportunities found: {len(opportunities)}")
    
    if opportunities:
        print(f"\n  Top Opportunities (by score):")
        for i, opp in enumerate(opportunities[:3], 1):
            print(f"    {i}. {opp.symbol}")
            print(f"       Strategy: {opp.strategy}")
            print(f"       Confidence: {opp.confidence:.0%}")
            print(f"       Score: {opp.score:.1f}/100")
            if opp.patterns:
                print(f"       Patterns: {', '.join(opp.patterns.keys())}")
    
    # Market status
    print(f"\n  Market Status by Symbol:")
    status = monitor.get_market_status()
    for symbol, data in status.items():
        print(f"    {symbol}: {data['market_state']} (Health: {data['health']:.0f})")
    
    # Pattern heatmap
    heatmap = monitor.get_pattern_heatmap()
    if heatmap:
        print(f"\n  Pattern Heatmap (detected patterns by symbol):")
        for symbol, patterns in heatmap.items():
            print(f"    {symbol}: {', '.join(patterns)}")
    
    # Market characteristics
    print(f"\n  Market Characteristics:")
    hottest = monitor.get_hottest_market()
    calmest = monitor.get_calmest_market()
    trending = monitor.get_trending_markets()
    ranging = monitor.get_ranging_markets()
    
    print(f"    Hottest market (highest volatility): {hottest}")
    print(f"    Calmest market (lowest volatility): {calmest}")
    print(f"    Trending markets: {trending if trending else 'None'}")
    print(f"    Ranging markets: {ranging if ranging else 'None'}")


def demo_intelligent_market_selection():
    """Demonstrate intelligent market selection for trading."""
    print("\n" + "="*70)
    print("DEMO 3: INTELLIGENT MARKET SELECTION")
    print("="*70)
    
    symbols = ['R_100', 'R_75', 'R_50', 'R_25']
    monitor = MultiMarketMonitor(symbols, base_stake=1.0)
    
    print(f"\nScanning {len(symbols)} markets for best opportunity...")
    
    # Simulate market data
    market_data = {}
    for symbol in symbols:
        prices = generate_trending_prices(100, 100, trend=random.uniform(-0.02, 0.02))
        for price in prices:
            monitor.update_market(symbol, price)
        
        market_data[symbol] = {
            'features': monitor.analyzers[symbol].feature_engine.extract_features(),
            'price': prices[-1],
        }
    
    # Get best opportunity
    opportunities = monitor.scan_all_markets(market_data)
    best = monitor.get_best_opportunity()
    
    if best:
        print(f"\n✓ Best Trading Opportunity Found:")
        print(f"  Symbol: {best.symbol}")
        print(f"  Market State: {best.market_state}")
        print(f"  Strategy: {best.strategy}")
        print(f"  Confidence: {best.confidence:.0%}")
        print(f"  Market Health: {best.health:.0f}/100")
        print(f"  Overall Score: {best.score:.1f}/100")
        
        if best.patterns:
            print(f"  Supporting Patterns:")
            for pattern in best.patterns:
                print(f"    ✓ {pattern}")
    else:
        print(f"\n  No good opportunities found")
    
    # Get high-score opportunities
    high_score_opportunities = monitor.get_opportunities_by_score(min_score=70.0)
    if high_score_opportunities:
        print(f"\n  High-Quality Opportunities (score >= 70):")
        for opp in high_score_opportunities:
            print(f"    {opp.symbol}: score={opp.score:.1f}, {opp.strategy}")


def demo_performance_tracking():
    """Demonstrate performance tracking across markets."""
    print("\n" + "="*70)
    print("DEMO 4: MULTI-MARKET PERFORMANCE TRACKING")
    print("="*70)
    
    symbols = ['R_100', 'R_75', 'R_50']
    monitor = MultiMarketMonitor(symbols, base_stake=1.0)
    
    print(f"\nSimulating trades across {len(symbols)} markets...")
    
    # Simulate trades
    trades_per_symbol = 20
    for symbol in symbols:
        for _ in range(trades_per_symbol):
            result = random.random() > 0.35  # 65% win rate
            profit = random.uniform(0.5, 2.0) if result else -random.uniform(0.5, 2.0)
            monitor.record_trade_result(symbol, result, profit)
    
    # Display performance
    print(f"\n  Performance Summary:")
    performance = monitor.get_all_performance()
    
    total_profit = 0.0
    total_trades = 0
    total_wins = 0
    
    for symbol, perf in performance.items():
        print(f"    {symbol}:")
        print(f"      Trades: {perf['trades']}")
        print(f"      Win Rate: {perf['win_rate']:.1%}")
        print(f"      Profit: ${perf['profit']:.2f}")
        print(f"      Avg/Trade: ${perf['avg_profit']:.2f}")
        
        total_profit += perf['profit']
        total_trades += perf['trades']
        total_wins += perf['wins']
    
    print(f"\n  Overall Statistics:")
    print(f"    Total Trades: {total_trades}")
    print(f"    Total Wins: {total_wins}")
    print(f"    Overall Win Rate: {total_wins/total_trades:.1%}")
    print(f"    Total Profit: ${total_profit:.2f}")
    
    best_symbol = monitor.get_best_performing_symbol()
    if best_symbol:
        print(f"    Best Performing Symbol: {best_symbol}")


def main():
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*10 + "ENHANCED AGENT DEMO - PATTERN RECOGNITION & MULTI-MARKET" + " "*6 + "║")
    print("╚" + "═"*68 + "╝")
    
    try:
        demo_pattern_recognition()
        
        demo_multi_market_monitoring()
        
        demo_intelligent_market_selection()
        
        demo_performance_tracking()
        
        print("\n" + "="*70)
        print("✅ ALL ENHANCED DEMOS COMPLETED SUCCESSFULLY")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
