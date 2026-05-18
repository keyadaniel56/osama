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
from deriv_client import DerivClient
from ml_predictor import MLPredictor
from multi_market_monitor import MultiMarketMonitor
from features.pattern_recognition import ChartPatternRecognizer
from decision_engine import DecisionEngine, RiskAdjustedDecision
from config import (
    DERIV_API_TOKEN, DERIV_APP_ID, DEFAULT_SYMBOL,
    BASE_STAKE, MAX_DAILY_LOSS, MAX_CONSEC_LOSSES,
    MIN_CONFIDENCE, RETRAIN_EVERY, MODELS_DIR,
    CONTRACT_DURATION, CONTRACT_DURATION_UNIT,
    MAX_CONCURRENT_TRADES, AVAILABLE_SYMBOLS
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
        self.ml_predictor = MLPredictor(MODELS_DIR)  # ML predictor
        self.pattern_recognizer = ChartPatternRecognizer(window=100)  # Pattern recognition
        
        # Decision engine (combines ML + patterns + indicators)
        self.decision_engine = DecisionEngine()
        self.risk_adjusted_decision = RiskAdjustedDecision(self.decision_engine, self.risk_manager)
        
        # Multi-market monitoring
        self.multi_market_monitor = MultiMarketMonitor(AVAILABLE_SYMBOLS, BASE_STAKE)
        self.monitoring_multiple_markets = len(AVAILABLE_SYMBOLS) > 1
        
        # Initialize Deriv client
        self.client = None
        self.latest_price = None
        
        # State tracking
        self.running = False
        self.session_trades = []
        self.tick_count = 0
        self.total_trades = 0
        self.win_count = 0
        self.loss_count = 0
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.pnl_history = []  # Track PnL over time
        
        # Active trade tracking
        self.active_contracts = {}  # contract_id -> trade_info
        self.max_concurrent_trades = MAX_CONCURRENT_TRADES  # From config
        
        # Current state
        self.current_market_state = "unknown"
        self.current_strategy = None
        self.market_health = 0.0
        self.confidence = 0.0
        self.trade_direction = None
        self.ensemble_confidence = 0.0
        self.current_signals = {}
        
        agent_logger.log_info(f"Initialized IntelligentTradingAgent: {self.agent_id}")
        agent_logger.log_info("Subsystems loaded:")
        agent_logger.log_info("  - Market Analyzer (feature extraction, state detection)")
        agent_logger.log_info("  - Strategy Selector (dynamic strategy matching)")
        agent_logger.log_info("  - Pattern Recognition (chart pattern detection)")
        agent_logger.log_info(f"  - Multi-Market Monitor ({len(AVAILABLE_SYMBOLS)} markets)")
        agent_logger.log_info("  - ML Predictor (machine learning models)")
        agent_logger.log_info("  - Decision Engine (ensemble signals: ML + Patterns + Indicators)")
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
        
        # Disconnect from Deriv
        if self.client:
            self.client.disconnect()
        
        self._save_session_data()
    
    def _initialize_connection(self):
        """Initialize connection to Deriv API."""
        try:
            self.client = DerivClient(DERIV_APP_ID, DERIV_API_TOKEN, self.symbol)
            
            # Set up callbacks
            self.client.on_tick = self._on_tick_received
            self.client.on_contract_result = self._on_contract_result
            self.client.on_error = self._on_api_error
            
            # Connect
            self.client.connect()
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
                
                # Step 7: Check if we have room for more trades
                has_capacity = len(self.active_contracts) < self.max_concurrent_trades
                
                # Step 8: Calculate position size and execute if conditions met
                if can_trade and has_capacity and strategy != 'hold':
                    volatility = market_data['features'].get('volatility', 0.5)
                    position_size = self.risk_manager.calculate_position_size(confidence, volatility)
                    
                    # Execute trade
                    self._execute_trade(strategy, market_data, confidence, position_size)
                
                # Step 9: Check for model retraining
                if self.tick_count % (RETRAIN_EVERY * 10) == 0:
                    if self.learning_system.should_retrain_model():
                        agent_logger.log_info("Retraining models based on performance...")
                
                # Step 10: Check for adaptation
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
        return self.latest_price
    
    def _on_tick_received(self, tick_data: Dict):
        """Callback when new tick is received from Deriv."""
        self.latest_price = tick_data.get('quote')
    
    def _on_contract_result(self, result: Dict):
        """Callback when contract result is received."""
        contract_id = result.get('contract_id')
        profit = result.get('profit', 0)
        status = result.get('status', 'unknown')
        
        # Find the trade in active contracts
        # First check if contract_id exists directly
        trade_info = None
        trade_key = None
        
        if contract_id in self.active_contracts:
            trade_key = contract_id
            trade_info = self.active_contracts[contract_id]
        else:
            # Check pending trades (those with temp keys)
            for key, info in list(self.active_contracts.items()):
                if isinstance(key, str) and key.startswith('pending_'):
                    # Assume this is the trade (first pending becomes first result)
                    trade_key = key
                    trade_info = info
                    # Update the key to actual contract_id
                    self.active_contracts[contract_id] = trade_info
                    del self.active_contracts[key]
                    break
        
        if trade_info:
            is_win = profit > 0
            
            # Determine actual price direction for ML training
            entry_price = trade_info.get('entry_price', 0)
            contract_type = trade_info.get('contract_type')
            
            if contract_type == 'CALL':
                actual_direction = 'UP' if is_win else 'DOWN'
            elif contract_type == 'PUT':
                actual_direction = 'DOWN' if is_win else 'UP'
            else:
                actual_direction = 'UP'
            
            # Train ML model with this result
            if 'market_data' in trade_info:
                self.ml_predictor.add_training_sample(
                    trade_info['market_data'],
                    actual_direction
                )
            
            # Check if ML prediction was correct
            ml_prediction = trade_info.get('ml_prediction', 'HOLD')
            if ml_prediction != 'HOLD':
                ml_was_correct = (ml_prediction == actual_direction)
                self.ml_predictor.record_prediction_result(ml_was_correct)
            
            # Update statistics
            if is_win:
                self.win_count += 1
                self.daily_profit += profit
                self.consecutive_losses = 0
                agent_logger.log_info(f"✓ WIN: Contract {contract_id} - Profit: ${profit:.2f} | Total: {self.win_count}W/{self.loss_count}L ({self.win_count/(self.win_count+self.loss_count)*100:.1f}%)")
            else:
                self.loss_count += 1
                self.daily_loss += abs(profit)
                self.consecutive_losses += 1
                agent_logger.log_info(f"✗ LOSS: Contract {contract_id} - Loss: ${abs(profit):.2f} | Total: {self.win_count}W/{self.loss_count}L ({self.win_count/(self.win_count+self.loss_count)*100:.1f}%)")
            
            # Update trade count and PnL history
            self.total_trades += 1
            cumulative_pnl = self.daily_profit - self.daily_loss
            self.pnl_history.append(cumulative_pnl)
            
            # Update trade info with result
            if contract_id in self.active_contracts:
                self.active_contracts[contract_id]['pnl'] = profit
                self.active_contracts[contract_id]['result'] = 'win' if is_win else 'loss'
                self.session_trades.append(self.active_contracts[contract_id])
            
            # Record for learning system
            self.learning_system.record_trade({
                'strategy': trade_info.get('strategy'),
                'market_state': trade_info.get('market_state'),
                'entry_price': trade_info.get('entry_price'),
                'entry_confidence': trade_info.get('confidence'),
                'profit': profit,
                'win': is_win,
                'duration': 300,  # 5 minutes in seconds
            })
            
            # Remove from active contracts
            if contract_id in self.active_contracts:
                del self.active_contracts[contract_id]
            
            # Update dashboard
            self._update_dashboard_state()
        else:
            agent_logger.log_info(f"Contract {contract_id} result: ${profit:.2f} ({status})")
    
    def _on_api_error(self, error_msg: str):
        """Callback when API error occurs."""
        agent_logger.log_error(f"Deriv API error: {error_msg}")
    
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
        """Execute a trade using the selected strategy with ML enhancement."""
        try:
            # Get actual prediction from the strategy (technical analysis)
            strategy_obj = self.strategy_selector.strategies.get(strategy)
            if not strategy_obj:
                agent_logger.log_error(f"Strategy {strategy} not found")
                return
            
            # Get the technical analysis signal
            signal = strategy_obj.analyze(market_data)
            
            if signal.action != 'BUY':
                return  # Strategy says don't trade
            
            # Get ML prediction
            ml_prediction, ml_confidence = self.ml_predictor.predict(market_data)
            
            # Combine technical analysis with ML
            # Convert strategy prediction to UP/DOWN
            if strategy == 'higher_lower':
                ta_prediction = 'UP' if signal.contract_type == 'HIGHER' else 'DOWN'
            elif strategy == 'rise_fall':
                ta_prediction = 'UP' if signal.contract_type == 'RISE' else 'DOWN'
            else:
                ta_prediction = 'UP'  # Default for accumulator
            
            # Decision logic: Both must agree OR ML must be very confident
            final_prediction = ta_prediction
            final_confidence = confidence
            
            if self.ml_predictor.is_trained:
                if ml_prediction == ta_prediction:
                    # Both agree - boost confidence
                    final_confidence = min(confidence + ml_confidence * 0.3, 1.0)
                    agent_logger.log_info(f"✓ Agreement: TA={ta_prediction}, ML={ml_prediction} → Confidence boosted to {final_confidence:.2f}")
                elif ml_confidence > 0.75:
                    # ML very confident, override TA
                    final_prediction = ml_prediction
                    final_confidence = ml_confidence
                    agent_logger.log_info(f"⚠ ML Override: TA={ta_prediction}, ML={ml_prediction} (conf={ml_confidence:.2f})")
                else:
                    # Disagreement with low ML confidence - reduce confidence
                    final_confidence = confidence * 0.7
                    agent_logger.log_info(f"✗ Disagreement: TA={ta_prediction}, ML={ml_prediction} → Confidence reduced to {final_confidence:.2f}")
            
            # Check if confidence still meets threshold
            if final_confidence < MIN_CONFIDENCE:
                agent_logger.log_info(f"Trade skipped: confidence {final_confidence:.2f} < {MIN_CONFIDENCE}")
                return
            
            # Map final prediction to contract type
            if strategy == 'higher_lower':
                contract_type = 'CALL' if final_prediction == 'UP' else 'PUT'
                display_prediction = 'HIGHER' if final_prediction == 'UP' else 'LOWER'
            elif strategy == 'rise_fall':
                contract_type = 'CALL' if final_prediction == 'UP' else 'PUT'
                display_prediction = 'RISE' if final_prediction == 'UP' else 'FALL'
            elif strategy == 'accumulator':
                contract_type = 'ACCU'
                display_prediction = 'ACCU'
            else:
                contract_type = 'CALL'
                display_prediction = 'UP'
            
            # Log trade execution
            agent_logger.log_decision({
                'action': 'execute_trade',
                'strategy': strategy,
                'ta_prediction': ta_prediction,
                'ml_prediction': ml_prediction,
                'ml_confidence': ml_confidence,
                'final_prediction': final_prediction,
                'contract_type': contract_type,
                'confidence': final_confidence,
                'market_state': self.current_market_state,
                'market_health': self.market_health,
                'position_size': position_size,
                'reasoning': signal.reasoning,
                'timestamp': datetime.now().isoformat()
            })
            
            current_price = market_data['features'].get('price_current', 0)
            duration = CONTRACT_DURATION
            duration_unit = CONTRACT_DURATION_UNIT
            
            # Execute via Deriv client
            if self.client and self.client.authorized:
                # Round position size to 2 decimal places for Deriv API
                position_size_rounded = round(position_size, 2)
                
                contract_id = self.client.buy_contract(
                    symbol=self.symbol,
                    contract_type=contract_type,
                    duration=duration,
                    duration_unit=duration_unit,
                    amount=position_size_rounded,
                    currency="USD"
                )
                self.total_trades += 1
                
                # Store contract info for tracking
                temp_key = f"pending_{self.total_trades}"
                self.active_contracts[temp_key] = {
                    'strategy': strategy,
                    'contract_type': contract_type,
                    'prediction': display_prediction,
                    'ml_prediction': ml_prediction,
                    'ta_prediction': ta_prediction,
                    'market_state': self.current_market_state,
                    'entry_price': current_price,
                    'confidence': final_confidence,
                    'buy_price': position_size_rounded,
                    'reasoning': signal.reasoning,
                    'market_data': market_data,  # Store for ML training
                    'timestamp': datetime.now().isoformat()
                }
                
                agent_logger.log_info(f"Trade #{self.total_trades}: {strategy} → {display_prediction} ({contract_type}) @ ${position_size_rounded:.2f} | Conf: {final_confidence:.2f} | Active: {len(self.active_contracts)}")
            else:
                agent_logger.log_warning("Cannot execute trade - not authorized")
                return
            
            # Record trade for learning
            trade_data = {
                'strategy': strategy,
                'contract_type': contract_type,
                'prediction': display_prediction,
                'market_state': self.current_market_state,
                'entry_price': current_price,
                'entry_confidence': final_confidence,
                'position_size': position_size_rounded,
                'reasoning': signal.reasoning,
                'timestamp': datetime.now().isoformat()
            }
            
            self.session_trades.append(trade_data)
            
        except Exception as e:
            agent_logger.log_error(f"Trade execution failed: {e}")
    
    def _update_dashboard_state(self):
        """Update dashboard state file for web UI."""
        try:
            # Calculate current metrics
            win_rate = 0
            if self.total_trades > 0:
                win_rate = self.win_count / self.total_trades
            
            # Calculate max drawdown
            max_drawdown = 0
            if self.pnl_history:
                peak = max(0, max(self.pnl_history[:max(1, len(self.pnl_history))]))
                current = self.pnl_history[-1] if self.pnl_history else 0
                max_drawdown = max(0, ((peak - current) / max(peak, 1)) * 100)
            
            drawdown = max(0, ((max(0, max(self.pnl_history[:max(1, len(self.pnl_history))]) if self.pnl_history else 0) - (self.pnl_history[-1] if self.pnl_history else 0)) / max(1, max(0, max(self.pnl_history[:max(1, len(self.pnl_history))]) if self.pnl_history else 0))) * 100)
            
            state = {
                'daily_profit': self.daily_profit,
                'daily_loss': self.daily_loss,
                'win_count': self.win_count,
                'loss_count': self.loss_count,
                'total_trades': self.total_trades,
                'consecutive_losses': self.consecutive_losses,
                'market_state': self.current_market_state,
                'market_health': self.market_health,
                'current_strategy': self.current_strategy,
                'confidence': self.confidence,
                'drawdown': drawdown,
                'max_drawdown': max_drawdown,
                'tick_count': self.tick_count,
                'trading_paused': self.risk_manager.trading_paused,
                'pause_reason': self.risk_manager.pause_reason,
                'trade_direction': self.trade_direction,
                'ensemble_confidence': self.ensemble_confidence,
                'signals': self.current_signals,
                'recent_trades': self._format_recent_trades(10),
                'market_opportunities': self._format_market_opportunities(),
                'pnl_history': self.pnl_history[-50:] if self.pnl_history else []  # Last 50
            }
            
            with open('dashboard_state.json', 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            agent_logger.log_error(f"Failed to update dashboard state: {e}")
    
    def _format_recent_trades(self, limit: int):
        """Format recent trades for dashboard."""
        trades = []
        for trade in self.session_trades[-limit:]:
            trades.append({
                'symbol': self.symbol,
                'direction': trade.get('prediction', 'UP').lower(),
                'result': 'win' if trade.get('pnl', 0) > 0 else 'loss',
                'pnl': trade.get('pnl', 0),
                'confidence': trade.get('entry_confidence', 0)
            })
        return trades
    
    def _format_market_opportunities(self):
        """Format market opportunities for dashboard."""
        if not self.multi_market_monitor:
            return []
        
        opportunities = []
        all_opps = self.multi_market_monitor.scan_all_markets()
        for opp in all_opps:
            opportunities.append({
                'symbol': opp.symbol,
                'score': opp.opportunity_score,
                'confidence': opp.confidence,
                'market_health': opp.market_health,
                'strategy': opp.recommended_strategy,
                'pattern_count': len(opp.confirmed_patterns)
            })
        
        return sorted(opportunities, key=lambda x: x['score'], reverse=True)[:5]
    
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
