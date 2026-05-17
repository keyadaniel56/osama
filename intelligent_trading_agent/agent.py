"""
Intelligent Trading Agent - Main Orchestrator
Coordinates market analysis, strategy selection, and trade execution.

Integrates:
- Market analysis (state detection, feature engineering)
- Strategy selection (dynamic strategy matching)
- Learning system (continuous model training)
- Risk management (position sizing, drawdown control)
"""

import time
import json
import os
from datetime import datetime
from collections import deque
from typing import Dict, Optional, Tuple
from logger import agent_logger
from market_analyzer import MarketAnalyzer
from strategy_selector import StrategySelector
from learning_system import LearningSystem
from risk_manager import RiskManager
from config import (
    DERIV_API_TOKEN, DERIV_APP_ID, DEFAULT_SYMBOL,
    BASE_STAKE, MAX_DAILY_LOSS, MAX_CONSEC_LOSSES,
    MIN_CONFIDENCE, RETRAIN_EVERY, MODELS_DIR
)


class IntelligentTradingAgent:
    """
    Main AI trading agent that:
    - Analyzes market conditions
    - Selects appropriate strategies
    - Manages risk dynamically
    - Learns from trades
    """
    
    def __init__(self):
        """Initialize the trading agent with all subsystems."""
        self.agent_id = f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.symbol = DEFAULT_SYMBOL
        
        # Initialize subsystems
        self.market_analyzer = MarketAnalyzer(window=100)
        self.strategy_selector = StrategySelector(BASE_STAKE)
        self.learning_system = LearningSystem()
        self.risk_manager = RiskManager()
        
        # State tracking
        self.running = False
        self.session_trades = []
        self.tick_count = 0
        
        # Current state
        self.current_market_state = "unknown"
        self.current_strategy = None
        self.market_health = 0.0
        
        agent_logger.log_info(f"Initialized IntelligentTradingAgent: {self.agent_id}")
        agent_logger.log_info("Subsystems loaded:")
        agent_logger.log_info("  - Market Analyzer (feature extraction, state detection)")
        agent_logger.log_info("  - Strategy Selector (dynamic strategy matching)")
        agent_logger.log_info("  - Learning System (continuous adaptation)")
        agent_logger.log_info("  - Risk Manager (position sizing, drawdown control)")
    
    def start(self):
        """Start the trading agent."""
        self.running = True
        agent_logger.log_info("Starting trading agent...")
        
        # Load models from disk if they exist
        self._load_models()
        
        # Initialize connection to Deriv
        self._initialize_connection()
        
        # Main trading loop
        self._trading_loop()
    
    def stop(self):
        """Stop the trading agent."""
        self.running = False
        agent_logger.log_info("Stopping trading agent...")
        self._save_session_data()
    
    def _initialize_connection(self):
        """Initialize connection to Deriv API."""
        try:
            # TODO: Initialize DerivClient with API credentials
            # self.client = DerivClient(DERIV_APP_ID, DERIV_API_TOKEN, self.symbol)
            # self.client.connect()
            agent_logger.log_info(f"Connected to Deriv API - Symbol: {self.symbol}")
        except Exception as e:
            agent_logger.log_error(f"Failed to connect to Deriv: {e}")
            raise
    
    def _trading_loop(self):
        """Main trading loop with integrated subsystems."""
        agent_logger.log_info("Entering main trading loop...")
        
        while self.running:
            try:
                # Step 1: Get market data
                price = self._get_price()
                if price is None:
                    time.sleep(1)
                    continue
                
                # Step 2: Update all subsystems with price
                self.market_analyzer.update(price, volume=1.0)
                self.strategy_selector.update_market_data(price, volume=1.0)
                self.tick_count += 1
                
                # Step 3: Analyze market state
                self.current_market_state = self.market_analyzer.detect_market_state()
                regime = self.market_analyzer.get_market_regime()
                self.market_health = regime['health']
                
                # Step 4: Build market data for strategies
                market_data = {
                    'features': self.market_analyzer.feature_engine.extract_features(),
                    'price': price,
                    'timestamp': datetime.now()
                }
                
                # Step 5: Select best strategy
                strategy, confidence = self.strategy_selector.select_strategy(market_data)
                self.current_strategy = strategy
                
                # Step 6: Check risk constraints
                can_trade = self.risk_manager.should_trade(confidence, self.market_health)
                
                # Step 7: Calculate position size
                if can_trade and strategy != 'hold':
                    volatility = market_data['features'].get('volatility', 0.5)
                    position_size = self.risk_manager.calculate_position_size(confidence, volatility)
                    
                    # Execute trade
                    self._execute_trade(strategy, market_data, confidence, position_size)
                
                # Step 8: Check for model retraining
                if self.tick_count % (RETRAIN_EVERY * 10) == 0:
                    if self.learning_system.should_retrain_model():
                        agent_logger.log_info("Retraining models based on performance...")
                
                # Step 9: Check for adaptation
                if self.tick_count % 100 == 0:
                    recommendations = self.learning_system.get_adaptation_recommendations()
                    if any(recommendations.values()):
                        self.risk_manager.adapt_risk_parameters(recommendations)
                
                # Periodic status
                if self.tick_count % 500 == 0:
                    self._log_status()
                
                time.sleep(0.1)
                
            except Exception as e:
                agent_logger.log_error(f"Error in trading loop: {e}")
                time.sleep(1)
    
    def _get_market_data(self) -> Optional[Dict]:
        """Get current market data from Deriv."""
        try:
            # TODO: Fetch latest ticks from Deriv
            # return self.client.get_latest_ticks()
            return None
        except Exception as e:
            agent_logger.log_error(f"Failed to get market data: {e}")
            return None
    
    def _get_price(self) -> Optional[float]:
        """Get current price from market data."""
        # TODO: Get from Deriv WebSocket
        # For now, returning None to indicate not connected
        return None
    
    def _analyze_market(self, market_data: Dict) -> Tuple[str, float]:
        """
        Analyze market conditions.
        Returns: (market_state, market_health_score)
        """
        # TODO: Implement market analysis
        # - Detect trends, volatility, patterns
        # - Score market attractiveness
        # - Identify regime (trending, ranging, volatile, calm)
        return "unknown", 50.0
    
    def _select_strategy(self, market_data: Dict) -> Tuple[str, float]:
        """
        Select best strategy for current market conditions.
        Returns: (strategy_name, confidence_score)
        """
        # TODO: Implement strategy selection logic
        # - Match market state to best strategy
        # - Return confidence score
        return "higher_lower", 0.65
    
    def _check_risk_constraints(self) -> bool:
        """Check if risk constraints allow trading. Returns True if trading should pause."""
        # Check daily loss limit
        if self.daily_loss >= MAX_DAILY_LOSS:
            agent_logger.log_warning(f"Daily loss limit reached: {self.daily_loss} >= {MAX_DAILY_LOSS}")
            return True
        
        # Check consecutive losses
        if self.consecutive_losses >= MAX_CONSEC_LOSSES:
            agent_logger.log_warning(f"Consecutive loss limit reached: {self.consecutive_losses}")
            return True
        
        return False
    
    def _execute_trade(self, strategy: str, market_data: Dict, confidence: float, position_size: float):
        """Execute a trade using the selected strategy."""
        try:
            # Log trade execution
            agent_logger.log_decision({
                'action': 'execute_trade',
                'strategy': strategy,
                'confidence': confidence,
                'market_state': self.current_market_state,
                'market_health': self.market_health,
                'position_size': position_size,
                'timestamp': datetime.now().isoformat()
            })
            
            # TODO: Actual Deriv API execution
            # For now, just log
            
            # Record trade for learning
            trade_data = {
                'strategy': strategy,
                'market_state': self.current_market_state,
                'entry_price': market_data['features'].get('price_current', 0),
                'entry_confidence': confidence,
                'position_size': position_size,
                'timestamp': datetime.now()
            }
            
            self.session_trades.append(trade_data)
            
        except Exception as e:
            agent_logger.log_error(f"Trade execution failed: {e}")
    
    def _log_status(self):
        """Log agent status."""
        regime = self.market_analyzer.get_market_regime()
        risk_metrics = self.risk_manager.get_risk_metrics()
        performance = self.learning_system.export_learning_report()
        
        status = f"""
        === Trading Agent Status ===
        Market State: {regime['state']}
        Market Health: {regime['health']:.1f}/100
        Current Strategy: {self.current_strategy}
        Ticks Processed: {self.tick_count}
        Trades Today: {len(self.session_trades)}
        Win Rate: {performance['win_rate']:.1%}
        Daily P&L: ${risk_metrics['daily_profit']:.2f} / ${risk_metrics['daily_loss']:.2f}
        Drawdown: {risk_metrics['drawdown']}
        Trading Paused: {risk_metrics['trading_paused']}
        """
        
        agent_logger.log_info(status)
    
    def _load_models(self):
        """Load persisted models from disk."""
        agent_logger.log_info("Loading models...")
        # TODO: Load model files
        # - market_state_model.pkl
        # - strategy_performance.json
        # - training_data.csv
    
    def _save_session_data(self):
        """Save session data for later analysis."""
        session_file = os.path.join(MODELS_DIR, f"session_{self.agent_id}.json")
        session_data = {
            'agent_id': self.agent_id,
            'total_trades': self.total_trades,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'daily_profit': self.daily_profit,
            'trades': self.session_trades
        }
        
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            agent_logger.log_info(f"Session data saved to {session_file}")
        except Exception as e:
            agent_logger.log_error(f"Failed to save session data: {e}")
    
    def record_trade_result(self, trade_id: str, result: bool, profit: float):
        """Record the result of a trade for learning."""
        # Record in risk manager
        self.risk_manager.record_trade_result(
            stake=self.risk_manager.current_stake,
            result=result,
            profit_loss=profit
        )
        
        # Record in learning system
        if self.session_trades:
            # Find the trade and record its result
            for trade in self.session_trades:
                if trade.get('timestamp'):
                    self.learning_system.record_trade({
                        'strategy': trade['strategy'],
                        'market_state': trade['market_state'],
                        'entry_price': trade.get('entry_price', 0),
                        'entry_confidence': trade['entry_confidence'],
                        'profit': profit,
                        'win': result,
                        'duration': 60,  # TODO: calculate actual duration
                    })
                    break


def main():
    """Main entry point."""
    try:
        agent = IntelligentTradingAgent()
        agent.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        agent.stop()
    except Exception as e:
        agent_logger.log_error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
