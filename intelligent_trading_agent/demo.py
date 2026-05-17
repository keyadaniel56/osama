"""
Demo script showing the Intelligent Trading Agent in action.
This demonstrates the agent's market analysis, strategy selection, and learning capabilities.
"""

from agent import IntelligentTradingAgent
from market_analyzer import MarketAnalyzer, MarketState
from strategy_selector import StrategySelector
from learning_system import LearningSystem
from risk_manager import RiskManager
import random
import time


def generate_synthetic_prices(base_price=100.0, num_ticks=500):
    """Generate synthetic price data for testing."""
    prices = [base_price]
    
    for _ in range(num_ticks):
        # Random walk with trend
        trend = random.gauss(0.01, 0.02)
        noise = random.gauss(0, 0.5)
        next_price = prices[-1] * (1 + trend + noise / prices[-1])
        prices.append(max(next_price, 1.0))  # Prevent negative prices
    
    return prices


def demo_market_analysis():
    """Demonstrate market analysis capabilities."""
    print("\n" + "="*60)
    print("DEMO 1: MARKET ANALYSIS ENGINE")
    print("="*60)
    
    analyzer = MarketAnalyzer(window=100)
    prices = generate_synthetic_prices(100.0, 150)
    
    print(f"\nGenerating {len(prices)} price ticks...")
    
    for price in prices:
        analyzer.update(price)
    
    regime = analyzer.get_market_regime()
    
    print(f"\nMarket Analysis Results:")
    print(f"  Current State: {regime['state']}")
    print(f"  Health Score: {regime['health']:.1f}/100")
    print(f"  Volatility: {regime['volatility']:.3f}")
    print(f"  Momentum: {regime['momentum']:.2f}%")
    print(f"  RSI: {regime['rsi']:.1f}")
    print(f"  Trend Strength: {regime['trend_strength']:.3f}")
    print(f"  Ready for Trading: {regime['ready_for_trading']}")
    
    recommendation = analyzer.get_strategy_recommendation()
    print(f"\nStrategy Recommendation:")
    print(f"  Best Strategy: {recommendation['strategy']}")
    print(f"  Confidence: {recommendation['confidence']:.1%}")


def demo_strategy_selection():
    """Demonstrate strategy selection."""
    print("\n" + "="*60)
    print("DEMO 2: STRATEGY SELECTOR")
    print("="*60)
    
    selector = StrategySelector(base_stake=1.0)
    prices = generate_synthetic_prices(100.0, 200)
    
    print(f"\nProcessing {len(prices)} price ticks...")
    
    for i, price in enumerate(prices):
        selector.update_market_data(price)
        
        if i % 50 == 0 and i > 0:
            market_data = {
                'features': selector.market_analyzer.feature_engine.extract_features(),
                'price': price,
            }
            
            strategy, confidence = selector.select_strategy(market_data)
            market_state = selector.get_market_state()
            
            print(f"\nTick {i}: Price={price:.2f}")
            print(f"  Market State: {market_state}")
            print(f"  Selected Strategy: {strategy}")
            print(f"  Confidence: {confidence:.1%}")
    
    print(f"\nFinal Statistics:")
    stats = selector.get_overall_stats()
    for state, data in stats.items():
        if data['total'] > 0:
            print(f"  {state}: {data['wins']}W / {data['losses']}L ({data['win_rate']:.1%})")


def demo_learning_system():
    """Demonstrate learning and adaptation."""
    print("\n" + "="*60)
    print("DEMO 3: LEARNING & ADAPTATION SYSTEM")
    print("="*60)
    
    learner = LearningSystem()
    
    print("\nSimulating 50 trades with different outcomes...")
    
    strategies = ['higher_lower', 'accumulator', 'rise_fall']
    market_states = ['trending_up', 'trending_down', 'ranging', 'volatile']
    
    for i in range(50):
        strategy = random.choice(strategies)
        market_state = random.choice(market_states)
        win = random.random() > 0.4  # 60% win rate
        profit = random.uniform(0.5, 2.0) if win else -random.uniform(0.5, 2.0)
        
        learner.record_trade({
            'strategy': strategy,
            'market_state': market_state,
            'entry_price': 100.0,
            'entry_confidence': random.uniform(0.55, 0.95),
            'profit': profit,
            'win': win,
            'duration': 60,
        })
    
    print("\nLearning Report:")
    report = learner.export_learning_report()
    print(f"  Total Trades: {report['total_trades']}")
    print(f"  Win Rate: {report['win_rate']:.1%}")
    print(f"  Total Profit: ${report['total_profit']:.2f}")
    print(f"  Avg Profit/Trade: ${report['avg_trade_profit']:.2f}")
    
    print(f"\nBest Strategies by Market State:")
    perf_summary = learner.get_performance_summary()
    for key, metrics in sorted(perf_summary.items()):
        print(f"  {metrics['strategy']} in {metrics['market_state']}: {metrics['win_rate']:.1%} WR")
    
    print(f"\nAdaptation Recommendations:")
    recommendations = learner.get_adaptation_recommendations()
    for rec, value in recommendations.items():
        if value:
            print(f"  - {rec}: {value}")


def demo_risk_management():
    """Demonstrate risk management."""
    print("\n" + "="*60)
    print("DEMO 4: RISK MANAGEMENT")
    print("="*60)
    
    risk_manager = RiskManager()
    
    print("\nSimulating trading session with risk management...")
    print(f"Initial Parameters:")
    print(f"  Base Stake: ${risk_manager.base_stake:.2f}")
    print(f"  Max Daily Loss: ${risk_manager.max_daily_loss:.2f}")
    print(f"  Max Consecutive Losses: {risk_manager.max_consecutive_losses}")
    print(f"  Max Drawdown: {risk_manager.max_drawdown:.1f}%")
    
    # Simulate trades
    trades = [
        ('WIN', 1.5, 0.70),
        ('WIN', 1.2, 0.75),
        ('LOSS', -0.8, 0.65),
        ('WIN', 2.0, 0.80),
        ('LOSS', -1.0, 0.55),
        ('LOSS', -0.9, 0.58),
    ]
    
    print(f"\nTrade Sequence:")
    for i, (result, profit, confidence) in enumerate(trades, 1):
        can_trade = risk_manager.should_trade(confidence, market_health=70)
        
        if can_trade:
            position_size = risk_manager.calculate_position_size(confidence, market_volatility=0.4)
            is_win = result == 'WIN'
            risk_manager.record_trade_result(position_size, is_win, profit)
            
            print(f"\n  Trade {i}: {result} (${profit:+.2f})")
            print(f"    Confidence: {confidence:.0%}")
            print(f"    Position Size: ${position_size:.2f}")
        else:
            print(f"\n  Trade {i}: BLOCKED (confidence {confidence:.0%})")
    
    print(f"\nFinal Risk Metrics:")
    metrics = risk_manager.get_risk_metrics()
    for key, value in metrics.items():
        if key not in ['pause_reason']:
            print(f"  {key}: {value}")


def demo_full_agent():
    """Demonstrate full integrated agent."""
    print("\n" + "="*60)
    print("DEMO 5: FULL INTELLIGENT TRADING AGENT")
    print("="*60)
    
    agent = IntelligentTradingAgent()
    
    print("\nAgent Configuration:")
    print(f"  Agent ID: {agent.agent_id}")
    print(f"  Symbol: {agent.symbol}")
    print(f"  Subsystems: 4 (Market, Strategy, Learning, Risk)")
    
    # Simulate price data
    prices = generate_synthetic_prices(100.0, 100)
    
    print(f"\nProcessing {len(prices)} price ticks...")
    
    for i, price in enumerate(prices):
        agent.market_analyzer.update(price)
        agent.strategy_selector.update_market_data(price)
        agent.tick_count += 1
        
        if i % 25 == 0 and i > 0:
            regime = agent.market_analyzer.get_market_regime()
            market_data = {
                'features': agent.market_analyzer.feature_engine.extract_features(),
                'price': price,
            }
            strategy, confidence = agent.strategy_selector.select_strategy(market_data)
            
            print(f"\nTick {i}: {regime['state']} | Health {regime['health']:.0f} | Strategy: {strategy} ({confidence:.0%})")


if __name__ == "__main__":
    print("\n")
    print("╔" + "═"*58 + "╗")
    print("║" + " "*10 + "INTELLIGENT TRADING AGENT - DEMOS" + " "*15 + "║")
    print("╚" + "═"*58 + "╝")
    
    try:
        demo_market_analysis()
        time.sleep(1)
        
        demo_strategy_selection()
        time.sleep(1)
        
        demo_learning_system()
        time.sleep(1)
        
        demo_risk_management()
        time.sleep(1)
        
        demo_full_agent()
        
        print("\n" + "="*60)
        print("ALL DEMOS COMPLETED SUCCESSFULLY")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
