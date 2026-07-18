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
    MAX_CONCURRENT_TRADES, AVAILABLE_SYMBOLS,
    TRADE_COOLDOWN_TICKS, MIN_MARKET_HEALTH
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
        self.symbols = AVAILABLE_SYMBOLS  # Track all symbols
        self.symbol = DEFAULT_SYMBOL  # Current trading symbol
        self.symbol_index = 0  # Index for cycling through symbols
        
        # Create analyzers for each symbol
        self.market_analyzers = {symbol: MarketAnalyzer(window=100) for symbol in self.symbols}
        self.current_market_analyzer = self.market_analyzers[self.symbol]
        
        # Initialize subsystems
        self.strategy_selector = StrategySelector(BASE_STAKE)
        self.learning_system = LearningSystem()
        self.risk_manager = RiskManager()
        self.ml_predictor = MLPredictor(MODELS_DIR, contract_duration_minutes=CONTRACT_DURATION)  # ML predictor with contract duration
        self.pattern_recognizer = ChartPatternRecognizer(window=100)  # Pattern recognition
        
        # Decision engine (combines ML + patterns + indicators)
        self.decision_engine = DecisionEngine()
        self.risk_adjusted_decision = RiskAdjustedDecision(self.decision_engine, self.risk_manager)
        
        # Rise/Fall optimization: Prefer rise_fall strategy
        self.preferred_strategy = 'rise_fall'  # Most profitable for trend following
        
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
        self.last_trade_tick = 0  # Track when last trade was placed
        self.trade_cooldown = TRADE_COOLDOWN_TICKS  # Minimum ticks between trades
        
        # Active trade tracking
        self.active_contracts = {}  # contract_id -> trade_info
        self.processed_contracts = set()  # Track processed to avoid duplicates
        self.max_concurrent_trades = MAX_CONCURRENT_TRADES  # From config
        
        # Current state
        self.current_market_state = "unknown"
        self.current_strategy = None
        self.current_patterns = {}  # Store detected patterns for ML
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
        agent_logger.log_info(f"  - Multi-Market Monitor ({len(AVAILABLE_SYMBOLS)} markets: {', '.join(AVAILABLE_SYMBOLS)})")
        agent_logger.log_info("  - ML Predictor (machine learning models)")
        agent_logger.log_info("  - Decision Engine (ensemble signals: ML + Patterns + Indicators)")
        agent_logger.log_info("  - Learning System (continuous adaptation)")
        agent_logger.log_info("  - Risk Manager (position sizing, drawdown control)")
        
        if self.monitoring_multiple_markets:
            agent_logger.log_info(f"🌐 Multi-market mode ENABLED - Monitoring {len(AVAILABLE_SYMBOLS)} markets simultaneously")
            agent_logger.log_info(f"   Will automatically switch to best opportunities across: {', '.join(AVAILABLE_SYMBOLS)}")
        else:
            agent_logger.log_info(f"📊 Single-market mode - Trading on {DEFAULT_SYMBOL} only")
    
    def start(self):
        """Start the trading agent."""
        self.running = True
        agent_logger.log_info("Starting trading agent...")
        
        # Clear any stale pause state from previous sessions
        self.risk_manager.trading_paused = False
        self.risk_manager.pause_reason = None
        agent_logger.log_info("✅ Cleared any stale pause state from previous sessions")
        
        # Clear loaded trade history from learning system to prevent stale data
        # from previous sessions causing false pause recommendations.
        # The learning system loads trades from disk, but those trades may have
        # poor performance that doesn't reflect current market conditions.
        # We keep the performance_data for strategy selection but clear the
        # recent trade history used for pause recommendations.
        self.learning_system.trade_history.clear()
        agent_logger.log_info("✅ Cleared loaded trade history for fresh session start")
        
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
            self.client = DerivClient(DERIV_APP_ID, DERIV_API_TOKEN, self.symbol, self.symbols)
            
            # Set up callbacks
            self.client.on_tick = self._on_tick_received
            self.client.on_buy_confirmed = self._on_buy_confirmed
            self.client.on_buy_failed = self._on_buy_failed
            self.client.on_contract_result = self._on_contract_result
            self.client.on_error = self._on_api_error
            
            # Connect
            self.client.connect()
            agent_logger.log_info(f"Connected to Deriv API - Primary: {self.symbol}, Monitoring: {', '.join(self.symbols)}")
        except Exception as e:
            agent_logger.log_error(f"Failed to connect to Deriv: {e}")
            raise
    
    def _trading_loop(self):
        """Main trading loop with integrated subsystems - multi-market enabled."""
        agent_logger.log_info("Entering main trading loop...")
        
        # Track last processed tick per symbol to avoid reprocessing
        last_processed_tick = {sym: 0 for sym in self.symbols}
        loop_iterations = 0  # Track loop iterations for debugging
        
        # Track time-based contract cleanup (not just tick-based)
        self._last_contract_cleanup_time = time.time()
        
        while self.running:
            try:
                loop_iterations += 1
                
                # Step 0: Update dashboard and check for commands (at the very top)
                if loop_iterations % 5 == 0:
                    self._update_dashboard_state()
                    self._process_dashboard_commands()
                
                # Log heartbeat every 1000 iterations to show loop is running
                if loop_iterations % 1000 == 0:
                    agent_logger.log_info(
                        f"💓 Loop heartbeat: iteration {loop_iterations}, "
                        f"tick_count={self.tick_count}, "
                        f"active_contracts={len(self.active_contracts)}, "
                        f"connected={self.client.connected}, "
                        f"authorized={self.client.authorized}"
                    )
                
                # Check if client is connected
                if not self.client.connected:
                    if loop_iterations % 100 == 0:
                        agent_logger.log_warning("⏸ Client not connected, waiting...")
                    time.sleep(1)
                    continue
                
                # Check if client is authorized
                if not self.client.authorized:
                    if loop_iterations % 200 == 0:
                        agent_logger.log_warning("⏸ Client not authorized, waiting...")
                    time.sleep(1)
                    continue
                
                # CRITICAL: Check tick health every 100 iterations (~10 seconds)
                # If ticks stop flowing, Deriv may have dropped the subscription
                if loop_iterations % 100 == 0:
                    tick_health = self.client.check_tick_health()
                    unhealthy_symbols = [sym for sym, healthy in tick_health.items() if not healthy]
                    
                    if unhealthy_symbols:
                        agent_logger.log_warning(
                            f"⚠️ Tick stream unhealthy for: {', '.join(unhealthy_symbols)} - Resubscribing..."
                        )
                        for sym in unhealthy_symbols:
                            self.client.resubscribe_to_ticks(sym)
                
                # Step 1: Check if we have NEW ticks for any symbol (use tick counter, not history length)
                has_new_tick = False
                for sym in self.symbols:
                    current_tick_count = self.client.get_tick_counter(sym)
                    if current_tick_count > last_processed_tick[sym]:
                        has_new_tick = True
                        break
                
                # If no new ticks, wait and continue
                if not has_new_tick:
                    # Log heartbeat every 10 seconds to show bot is alive
                    if self.tick_count % 100 == 0:
                        tick_counts = {sym: self.client.get_tick_counter(sym) for sym in self.symbols}
                        agent_logger.log_info(f"💓 Heartbeat: Waiting for ticks... Current counts: {tick_counts}")
                    time.sleep(0.1)
                    continue
                
                # Step 2: Process NEW ticks for ALL symbols
                for sym in self.symbols:
                    current_tick_count = self.client.get_tick_counter(sym)
                    if current_tick_count > last_processed_tick[sym]:
                        # Get the latest tick from history
                        tick_history = self.client.get_tick_history(sym)
                        if tick_history:
                            tick = tick_history[-1]  # Get most recent tick
                            sym_price = tick.get('quote')
                            
                            if sym_price and sym in self.market_analyzers:
                                # Update analyzer for this symbol
                                self.market_analyzers[sym].update(sym_price, volume=1.0)
                                
                                # If this is our current trading symbol, also update other systems
                                if sym == self.symbol:
                                    self.latest_price = sym_price
                        
                        # Update last processed count to current counter
                        last_processed_tick[sym] = current_tick_count
                
                # Step 3: Get price for current trading symbol
                price = self._get_price()
                if price is None:
                    time.sleep(0.1)
                    continue
                
                # Step 4: Update current symbol's systems (strategy selector, pattern recognizer, etc.)
                # Only update once per new tick (not every loop iteration)
                self.strategy_selector.update_market_data(price, volume=1.0)
                self.pattern_recognizer.add_price(price)  # Feed price to pattern recognizer
                self.tick_count += 1
                
                # Step 2.25: Let ML predictor observe the market (learn from actual movements)
                # Enrich with pattern data
                market_data_for_ml = {
                    'features': self.current_market_analyzer.feature_engine.extract_features(),
                    'price': price,
                    'timestamp': datetime.now().isoformat(),
                    'symbol': self.symbol
                }
                
                # Add pattern information if available
                if hasattr(self, 'current_patterns') and self.current_patterns:
                    has_bullish = 0.0
                    has_bearish = 0.0
                    max_confidence = 0.0
                    breakout_dir = 0.0
                    breakout_detected = 0.0
                    
                    for pattern_name, pattern_info in self.current_patterns.items():
                        conf = pattern_info.get('confidence', 0.0)
                        signal = pattern_info.get('signal', '')
                        
                        if conf > max_confidence:
                            max_confidence = conf
                        
                        if 'bullish' in signal or 'upside' in signal or signal == 'up':
                            has_bullish = 1.0
                        elif 'bearish' in signal or 'downside' in signal or signal == 'down':
                            has_bearish = 1.0
                        
                        if 'breakout' in pattern_name:
                            breakout_detected = 1.0
                            if 'upside' in signal:
                                breakout_dir = 1.0
                            elif 'downside' in signal:
                                breakout_dir = -1.0
                    
                    market_data_for_ml['features']['has_bullish_pattern'] = has_bullish
                    market_data_for_ml['features']['has_bearish_pattern'] = has_bearish
                    market_data_for_ml['features']['pattern_confidence'] = max_confidence
                    market_data_for_ml['features']['breakout_detected'] = breakout_detected
                    market_data_for_ml['features']['breakout_direction'] = breakout_dir
                
                self.ml_predictor.observe_market(market_data_for_ml, price)
                
                # Step 2.3: Validate ML predictions against actual price movements
                # Validate every contract duration (5 minutes = 300 ticks)
                if self.tick_count % (CONTRACT_DURATION * 60) == 0:
                    self.ml_predictor.validate_predictions(price)
                
                # Step 2.5: Update multi-market monitor for ALL symbols
                if self.monitoring_multiple_markets:
                    for sym in self.symbols:
                        if sym in self.market_analyzers:
                            # Get latest price for this symbol
                            sym_tick_history = self.client.get_tick_history(sym)
                            if sym_tick_history:
                                sym_latest_price = sym_tick_history[-1].get('quote')
                                if sym_latest_price:
                                    self.multi_market_monitor.update_market(sym, sym_latest_price, volume=1.0)
                
                # Step 3: Periodically scan and switch to best market
                # KEY IMPROVEMENT: Analyzes ALL markets but ONLY trades the one
                # with the clearest trending state. Does NOT switch markets while
                # an active contract is open.
                if self.tick_count % 25 == 0 and self.monitoring_multiple_markets:
                    # Log current tick counts for all symbols
                    if self.tick_count % 100 == 0:
                        tick_counts = {sym: len(self.client.get_tick_history(sym)) for sym in self.symbols}
                        agent_logger.log_info(f"📊 Tick counts by symbol: {tick_counts}")
                    
                    # Check if there's an active contract - DON'T switch while trade is open
                    if len(self.active_contracts) > 0:
                        if self.tick_count % 50 == 0:
                            contract_ids = list(self.active_contracts.keys())
                            agent_logger.log_warning(
                                f"🔒 Market LOCKED on {self.symbol} - Active contract open "
                                f"({contract_ids}) - Will NOT switch until contract closes"
                            )
                    else:
                        # Scan for best trending market
                        best_opportunity = self._find_best_market_opportunity()
                        if best_opportunity:
                            # Only switch if:
                            # 1. It's a different market
                            # 2. Current market is NOT trending (or target is MUCH better)
                            # 3. Target market is actually in a trending state
                            is_current_trending = 'trending' in self.current_market_state
                            current_score = self._calculate_current_market_score()
                            
                            # Calculate switching threshold: 
                            # - If current is NOT trending, any trending market with higher score is enough
                            # - If current IS trending, require a large difference to flip
                            if not is_current_trending:
                                switch_threshold = 5  # Small threshold if current is non-trending
                            else:
                                switch_threshold = 25  # Bigger threshold if already in a trend
                            
                            # Check if target market has a clear trend
                            target_state = getattr(best_opportunity, 'market_state', 'unknown')
                            target_is_trending = 'trending' in target_state
                            
                            should_switch = (
                                best_opportunity.symbol != self.symbol and
                                best_opportunity.score > current_score + switch_threshold and
                                target_is_trending
                            )
                            
                            if should_switch:
                                agent_logger.log_info(
                                    f"🔄 Switching markets: {self.symbol} (score={current_score:.1f}, state={self.current_market_state}) → "
                                    f"{best_opportunity.symbol} (score={best_opportunity.score:.1f}, state={target_state})"
                                )
                                self.symbol = best_opportunity.symbol
                                self.current_market_analyzer = self.market_analyzers[self.symbol]
                                # FIX: Use existing pattern_recognizer from multi_market_monitor instead of creating a new one
                                self.pattern_recognizer = self.multi_market_monitor.pattern_recognizers.get(
                                    self.symbol, ChartPatternRecognizer(window=100)
                                )
                                self.client.symbol = self.symbol
                                agent_logger.log_info(
                                    f"📊 New market: {best_opportunity.symbol} | "
                                    f"State: {target_state} | "
                                    f"Strategy: {best_opportunity.strategy} | "
                                    f"Confidence: {best_opportunity.confidence:.2f}"
                                )
                            elif self.tick_count % 100 == 0:
                                # Log analysis status
                                if target_is_trending:
                                    agent_logger.log_info(
                                        f"📊 Market scan: {self.symbol} (trending={is_current_trending}, score={current_score:.1f}) | "
                                        f"Best other: {best_opportunity.symbol} (trending={target_is_trending}, score={best_opportunity.score:.1f}) | "
                                        f"Difference={best_opportunity.score-current_score:.1f} (need>={switch_threshold})"
                                    )
                
                # Step 3.5: Log multi-market status periodically
                if self.tick_count % 100 == 0 and self.monitoring_multiple_markets:
                    self._log_multi_market_status()
                
                # Step 3.75: Check for stuck contracts (run BEFORE any continue statements)
                # This is critical: if the bot is in a state where it can't trade (overbought,
                # oversold, contradictory patterns, etc.), the continue statements below would
                # skip the cleanup code. By running cleanup here, we ensure stuck contracts
                # are always cleaned up regardless of market conditions.
                if len(self.active_contracts) > 0:
                    # Tick-based cleanup (every 100 ticks)
                    if self.tick_count % 100 == 0:
                        self._cleanup_stuck_contracts()
                    
                    # Time-based cleanup (every 30 seconds of real time)
                    current_time = time.time()
                    if current_time - self._last_contract_cleanup_time >= 30:
                        self._last_contract_cleanup_time = current_time
                        self._cleanup_stuck_contracts_time_based()
                
                # Step 4: Analyze current market state
                self.current_market_state = self.current_market_analyzer.detect_market_state()
                regime = self.current_market_analyzer.get_market_regime()
                self.market_health = regime['health']
                
                # Debug logging every 50 ticks
                if self.tick_count % 50 == 0:
                    patterns_str = f", patterns={len(patterns_detected)}" if patterns_detected else ""
                    ml_str = f", ml={ml_prediction_direction}@{ml_confidence:.2f}" if ml_prediction_direction != 'HOLD' else ""
                    ensemble_str = f", ensemble={trade_direction}@{ensemble_confidence:.2f}" if trade_direction else ""
                    agent_logger.log_info(
                        f"Analysis: ticks={self.tick_count}, "
                        f"state={self.current_market_state}, "
                        f"health={self.market_health:.1f}, "
                        f"strategy={self.current_strategy}, "
                        f"confidence={confidence:.2f}"
                        f"{patterns_str}{ml_str}{ensemble_str}"
                    )
                
                # Step 5: Build market data for strategies
                market_data = {
                    'features': self.current_market_analyzer.feature_engine.extract_features(),
                    'price': price,
                    'timestamp': datetime.now().isoformat(),
                    'symbol': self.symbol
                }
                
                # Step 6: Detect chart patterns
                patterns_detected = self.pattern_recognizer.detect_all_patterns()
                self.current_patterns = patterns_detected  # Store for ML enrichment
                
                # Log detected patterns
                if patterns_detected and self.tick_count % 100 == 0:
                    agent_logger.log_info(f"📊 Patterns detected: {list(patterns_detected.keys())}")
                    for pattern_name, pattern_info in patterns_detected.items():
                        agent_logger.log_info(
                            f"  • {pattern_name}: {pattern_info.get('signal')} "
                            f"(conf={pattern_info.get('confidence', 0):.2f})"
                        )
                
                # Step 6.5: Get ML prediction
                ml_prediction_direction, ml_confidence = self.ml_predictor.predict(market_data)
                ml_prediction = {
                    'direction': ml_prediction_direction.lower() if ml_prediction_direction != 'HOLD' else None,
                    'confidence': ml_confidence
                }
                
                # Step 6.6: Get multi-timeframe trend analysis from pattern recognizer
                multi_tf_trend = None
                if hasattr(self.pattern_recognizer, 'multi_tf_analyzer'):
                    tf_analysis = self.pattern_recognizer.multi_tf_analyzer.get_aligned_trend()
                    if tf_analysis['is_trending']:
                        multi_tf_trend = tf_analysis
                        if self.tick_count % 50 == 0:
                            agent_logger.log_info(
                                f"📊 Multi-timeframe trend: {tf_analysis['primary_direction'].upper()} "
                                f"(strength={tf_analysis['strength']:.2f}, "
                                f"higher_medium_agree={tf_analysis['higher_medium_agree']}, "
                                f"all_aligned={tf_analysis['all_timeframes_align']})"
                            )
                
                # Step 6.75: Prepare pattern data for decision engine
                pattern_data = None
                if patterns_detected:
                    pattern_data = {'patterns': {}}
                    for pattern_name, pattern_info in patterns_detected.items():
                        signal = pattern_info.get('signal', '')
                        pattern_type = None
                        if 'bullish' in signal or 'up' in signal:
                            pattern_type = 'bullish'
                        elif 'bearish' in signal or 'down' in signal:
                            pattern_type = 'bearish'
                        else:
                            pattern_type = 'neutral'
                        
                        pattern_data['patterns'][pattern_name] = {
                            'type': pattern_type,
                            'confidence': pattern_info.get('confidence', 0.5),
                            'signal': signal
                        }
                
                # Step 7: Use decision engine to combine ML + patterns + indicators
                indicators = market_data['features']
                
                # CRITICAL SAFEGUARD: Check for extreme indicator conditions
                rsi = indicators.get('rsi', 50)
                bb_position = indicators.get('bb_position', 0.5)
                
                # Block trading only at EXTREME RSI levels (not moderate ones)
                # RSI 0-15 = severely oversold (likely to bounce)
                # RSI 85-100 = severely overbought (likely to reverse)
                # Moderate RSI (15-85) is fine for trend following
                if rsi >= 85:
                    if self.tick_count % 100 == 0:
                        agent_logger.log_warning(
                            f"⚠️ EXTREME OVERBOUGHT: RSI={rsi:.1f} - Waiting for stabilization (threshold: 85)"
                        )
                    time.sleep(0.05)
                    continue
                
                if rsi <= 15:
                    if self.tick_count % 100 == 0:
                        agent_logger.log_warning(
                            f"⚠️ EXTREME OVERSOLD: RSI={rsi:.1f} - Waiting for stabilization (threshold: 15)"
                        )
                    time.sleep(0.05)
                    continue
                
                # BB threshold - only block at very extreme edges
                if bb_position >= 0.95 or bb_position <= 0.05:
                    if self.tick_count % 100 == 0:
                        agent_logger.log_warning(
                            f"⚠️ EXTREME BB position: {bb_position:.2f} - Price near band edge, waiting for mean reversion"
                        )
                    time.sleep(0.05)
                    continue
                
                # PATTERN CONTRADICTION CHECK: Only block if patterns are EQUALLY contradictory
                # (same number of bullish and bearish patterns with similar confidence)
                if pattern_data and 'patterns' in pattern_data:
                    bullish_count = sum(1 for p in pattern_data['patterns'].values() if p['type'] == 'bullish')
                    bearish_count = sum(1 for p in pattern_data['patterns'].values() if p['type'] == 'bearish')
                    
                    # Only block if perfectly balanced (equal bullish and bearish)
                    # If one side dominates, let the decision engine handle it
                    if bullish_count > 0 and bearish_count > 0 and bullish_count == bearish_count:
                        if self.tick_count % 100 == 0:
                            agent_logger.log_warning(
                                f"⚠️ EQUAL CONTRADICTORY PATTERNS: {bullish_count} bullish + {bearish_count} bearish - "
                                f"No clear directional signal, waiting for clarity"
                            )
                        time.sleep(0.05)
                        continue
                
                trade_direction, ensemble_confidence = self.decision_engine.make_decision(
                    ml_prediction=ml_prediction,
                    patterns=pattern_data,
                    indicators=indicators,
                    market_state=self.current_market_state,
                    market_health=self.market_health,
                    multi_tf_trend=multi_tf_trend
                )
                
                # Store for logging
                self.trade_direction = trade_direction
                self.ensemble_confidence = ensemble_confidence
                self.current_signals = {
                    'ml': ml_prediction,
                    'patterns': pattern_data,
                    'indicators': indicators
                }
                
                # Step 7.25: Select strategy based on ensemble decision
                # Prefer rise_fall for trend following (most profitable)
                strategy, confidence = self.strategy_selector.select_strategy(market_data)
                
                # Force rise_fall if we have a clear directional signal
                if trade_direction and strategy != 'accumulator':
                    strategy = 'rise_fall'
                    agent_logger.log_info(f"📈 Using rise_fall strategy (trend following) for {trade_direction.upper()} signal")
                
                self.current_strategy = strategy
                
                # Override confidence with ensemble confidence if decision engine has a signal
                if trade_direction and ensemble_confidence > confidence:
                    confidence = ensemble_confidence
                    agent_logger.log_info(
                        f"🎯 Ensemble decision: {trade_direction.upper()} "
                        f"(conf={ensemble_confidence:.2f}) overrides strategy confidence"
                    )
                
                # Step 7: (market state check handled in Step 7.5 below)
                
                # Step 7.5: Warmup phase — wait for enough data for reliable analysis.
                # Need at least 200 ticks so RSI-14, MACD, SMA-50, and Bollinger Bands
                # are all computed from sufficient history before placing any trade.
                WARMUP_TICKS = 200
                if self.tick_count < WARMUP_TICKS:
                    if self.tick_count % 25 == 0:
                        pct = int(self.tick_count / WARMUP_TICKS * 100)
                        bar = ('█' * (pct // 5)).ljust(20)
                        agent_logger.log_info(
                            f"📊 Warming up market data: [{bar}] {pct}% "
                            f"({self.tick_count}/{WARMUP_TICKS} ticks) — "
                            f"state={self.current_market_state}, health={self.market_health:.1f}"
                        )
                    time.sleep(0.05)
                    continue
                
                # === INITIAL MARKET SELECTION ===
                # The first time we pass warmup, analyze ALL markets and pick the
                # single best one to focus on.  This ensures the bot doesn't start
                # blindly on DEFAULT_SYMBOL but instead picks the market with the
                # clearest trend / strongest signal.
                if not hasattr(self, '_initial_market_selected'):
                    self._initial_market_selected = True
                    agent_logger.log_info("=" * 80)
                    agent_logger.log_info("🔍 INITIAL MARKET SCAN — Analyzing all markets after warmup...")
                    agent_logger.log_info("=" * 80)
                    
                    # Build complete market data for ALL symbols that have enough history
                    market_data_dict = {}
                    for symbol in self.symbols:
                        analyzer = self.market_analyzers[symbol]
                        if len(analyzer.price_history) < 50:
                            agent_logger.log_info(f"  ⏭ {symbol}: skipping (only {len(analyzer.price_history)} ticks, need 50)")
                            continue
                        
                        features = analyzer.feature_engine.extract_features()
                        market_data_dict[symbol] = {
                            'features': features,
                            'price': features.get('price_current', 0),
                            'timestamp': datetime.now().isoformat(),
                            'symbol': symbol
                        }
                        agent_logger.log_info(
                            f"  ✓ {symbol}: {len(analyzer.price_history)} ticks, "
                            f"state={analyzer.detect_market_state()}, "
                            f"price={features.get('price_current', 0):.5f}"
                        )
                    
                    # Use multi-market monitor to scan and rank
                    if market_data_dict:
                        opportunities = self.multi_market_monitor.scan_all_markets(market_data_dict)
                        if opportunities:
                            # Log all ranked opportunities
                            agent_logger.log_info("📊 MARKET RANKINGS (by opportunity score):")
                            for i, opp in enumerate(opportunities):
                                marker = "🎯" if i == 0 else "  "
                                agent_logger.log_info(
                                    f"  {marker} #{i+1}: {opp.symbol:8} | "
                                    f"Score: {opp.score:5.1f} | "
                                    f"State: {opp.market_state:15} | "
                                    f"Strategy: {opp.strategy:12} | "
                                    f"Confidence: {opp.confidence:.2f} | "
                                    f"Health: {opp.health:.1f}"
                                )
                            
                            # Select the best market
                            best = opportunities[0]
                            agent_logger.log_info("=" * 80)
                            agent_logger.log_info(
                                f"🎯 SELECTED MARKET: {best.symbol} "
                                f"(score={best.score:.1f}, state={best.market_state}, "
                                f"strategy={best.strategy}, conf={best.confidence:.2f})"
                            )
                            agent_logger.log_info("=" * 80)
                            
                            # Apply selection
                            self.symbol = best.symbol
                            self.current_market_analyzer = self.market_analyzers[self.symbol]
                            self.pattern_recognizer = self.multi_market_monitor.pattern_recognizers.get(
                                self.symbol, ChartPatternRecognizer(window=100)
                            )
                            self.client.symbol = self.symbol
                            self.current_market_state = best.market_state
                            
                            # Unsubscribe from all non-selected symbols to stop
                            # receiving ticks for markets we're not trading.
                            if self.monitoring_multiple_markets:
                                for sym in self.symbols:
                                    if sym != self.symbol:
                                        self.client.unsubscribe_from_symbol(sym)
                                agent_logger.log_info(
                                    f"🔕 Unsubscribed from non-selected markets: "
                                    f"{', '.join(s for s in self.symbols if s != self.symbol)}"
                                )
                                agent_logger.log_info(
                                    f"✅ Now ONLY receiving ticks for selected market: {self.symbol}"
                                )
                        else:
                            agent_logger.log_warning(
                                f"⚠️ No market opportunities found! "
                                f"Staying with default symbol: {self.symbol}"
                            )
                    else:
                        agent_logger.log_warning(
                            f"⚠️ No markets have enough data for selection! "
                            f"Staying with default symbol: {self.symbol}"
                        )
                
                # After warmup, block if EITHER the agent's or strategy selector's
                # market state is still unknown. Both must agree on a real state.
                selector_state = self.strategy_selector.current_market_state or "unknown"
                if self.current_market_state == "unknown" or selector_state == "unknown":
                    if self.tick_count % 50 == 0:
                        agent_logger.log_warning(
                            f"⏸ Market state still unknown after {self.tick_count} ticks "
                            f"(agent={self.current_market_state}, selector={selector_state}) — "
                            f"waiting for clearer conditions before trading"
                        )
                    time.sleep(0.05)
                    continue
                
                # Step 8: Check risk constraints
                can_trade = self.risk_manager.should_trade(confidence, self.market_health)
                
                # Step 9: Wait for active trade to close before opening another
                # If there is already an open contract, skip until it settles.
                if len(self.active_contracts) >= self.max_concurrent_trades:
                    if self.tick_count % 100 == 0:
                        agent_logger.log_info(
                            f"⏳ Waiting for trade to close before opening new one "
                            f"(active={len(self.active_contracts)}/{self.max_concurrent_trades})"
                        )
                    time.sleep(0.05)
                    continue
                
                # Step 10: Check trade cooldown (prevent rapid-fire trading)
                ticks_since_last_trade = self.tick_count - self.last_trade_tick
                cooldown_ready = ticks_since_last_trade >= self.trade_cooldown
                
                # Step 11: Execute trade based on ensemble decision
                # The ensemble combines:
                # - ML model (trained on actual 5-minute price movements)
                # - Chart patterns (breakouts, support/resistance, SMC concepts)
                # - Technical indicators (RSI, MACD, Bollinger Bands)
                # No tick counting - trust the pattern recognition and trained ML
                
                # Only trade if ensemble provides a clear direction
                if trade_direction is None:
                    if self.tick_count % 100 == 0 and strategy != 'hold':
                        agent_logger.log_info(
                            f"Not trading: ensemble_no_direction (waiting for clear signal)"
                        )
                    time.sleep(0.05)
                    continue
                
                # Check if ensemble agrees with strategy
                ensemble_agrees = (
                    strategy == 'hold' or
                    (trade_direction == 'up' and strategy in ['higher_lower', 'rise_fall', 'accumulator']) or
                    (trade_direction == 'down' and strategy in ['higher_lower', 'rise_fall'])
                )
                
                # Execute trade if all conditions met
                if can_trade and cooldown_ready and strategy != 'hold' and ensemble_agrees:
                    agent_logger.log_info(
                        f"✅ Trade signal: {trade_direction.upper()} | "
                        f"Ensemble: {ensemble_confidence:.2%} | "
                        f"ML: {ml_prediction.get('confidence', 0):.2%} | "
                        f"State: {self.current_market_state} | "
                        f"Health: {self.market_health:.1f}/100"
                    )
                    
                    volatility = market_data['features'].get('volatility', 0.5)
                    # Get trend direction for trend-aware position sizing
                    trend_dir = None
                    if multi_tf_trend and multi_tf_trend.get('is_trending'):
                        trend_dir = multi_tf_trend.get('primary_direction')
                    position_size = self.risk_manager.calculate_position_size(
                        confidence, volatility, 
                        trade_direction=trade_direction, 
                        trend_direction=trend_dir
                    )
                    
                    self._execute_trade(strategy, market_data, confidence, position_size, ensemble_direction=trade_direction)
                    self.last_trade_tick = self.tick_count
                else:
                    # Log why we're not trading (more frequently for debugging)
                    if self.tick_count % 50 == 0:  # Changed from 100 to 50 for more frequent logging
                        reasons = []
                        min_health = MIN_MARKET_HEALTH
                        if not can_trade:
                            reasons.append(f"can_trade=False (conf={confidence:.2f}, threshold={self.risk_manager.min_confidence_threshold:.2f}, health={self.market_health:.1f}, min={min_health})")
                        if not cooldown_ready:
                            reasons.append(f"cooldown ({ticks_since_last_trade}/{self.trade_cooldown} ticks)")
                        if strategy == 'hold':
                            reasons.append("strategy=hold")
                        if not ensemble_agrees:
                            reasons.append(f"ensemble_disagrees (direction={trade_direction}, strategy={strategy})")
                        if reasons:
                            agent_logger.log_info(f"❌ Not trading: {', '.join(reasons)}")
                
                # Step 13: Check for model retraining
                if self.tick_count % (RETRAIN_EVERY * 10) == 0:
                    if self.learning_system.should_retrain_model():
                        agent_logger.log_info("Retraining models based on performance...")
                
                # Step 14: Check for adaptation
                if self.tick_count % 100 == 0:
                    recommendations = self.learning_system.get_adaptation_recommendations()
                    if any(recommendations.values()):
                        self.risk_manager.adapt_risk_parameters(recommendations)
                
                # Step 14.5: Auto-resume from learning system pause if enough ticks have passed
                # The learning system may pause trading after a bad streak, but we need to
                # auto-resume after a cooldown period so the agent doesn't stay paused forever.
                if self.tick_count % 25 == 0:
                    self.risk_manager.check_auto_resume(self.tick_count)
                
                # Step 15: Periodic status logs
                if self.tick_count % 500 == 0:
                    self._log_status()
                
                time.sleep(0.05)  # Reduced sleep for faster trading
                
            except Exception as e:
                agent_logger.log_error(f"Error in trading loop: {e}")
                time.sleep(1)
    
    def _cleanup_stuck_contracts(self):
        """Clean up contracts that have been open for too long (tick-based)."""
        # Calculate expected ticks based on actual contract duration
        # Convert duration to expected ticks (1 tick/sec roughly)
        if CONTRACT_DURATION_UNIT == 'm':
            expected_ticks = CONTRACT_DURATION * 60  # minutes to seconds
        elif CONTRACT_DURATION_UNIT == 's':
            expected_ticks = CONTRACT_DURATION
        elif CONTRACT_DURATION_UNIT == 'h':
            expected_ticks = CONTRACT_DURATION * 3600
        elif CONTRACT_DURATION_UNIT == 't':
            expected_ticks = CONTRACT_DURATION
        else:
            expected_ticks = 300  # default 5 min
        
        stuck_threshold_ticks = int(expected_ticks * 1.5)  # 50% buffer over expected
        
        for key, trade in list(self.active_contracts.items()):
            tick_opened = trade.get('tick_opened', self.tick_count)
            ticks_open = self.tick_count - tick_opened
            
            # Check for PENDING contracts that never got a buy confirmation
            # These are contracts where buy_contract() was called but the
            # Deriv API never responded with a buy confirmation.
            # If pending for more than 30 ticks (~30 seconds), it's stuck.
            if isinstance(key, str) and key.startswith('pending_'):
                if ticks_open > 30:
                    agent_logger.log_warning(
                        f"⚠️ Stuck PENDING contract detected: {key} open for {ticks_open} ticks "
                        f"- Deriv never confirmed the buy. Removing from active list."
                    )
                    del self.active_contracts[key]
                continue
            
            # For confirmed contracts (have real contract_id):
            # Use actual contract duration to determine stuck threshold
            if ticks_open > stuck_threshold_ticks:
                agent_logger.log_warning(
                    f"⚠️ Stuck contract detected: {key} open for {ticks_open} ticks "
                    f"(expected ~{expected_ticks}, threshold={stuck_threshold_ticks}). "
                    f"Removing from active list."
                )
                del self.active_contracts[key]
    
    def _cleanup_stuck_contracts_time_based(self):
        """
        Time-based stuck contract cleanup.
        This runs even when ticks aren't flowing (e.g., after WebSocket disconnect).
        Uses real wall-clock time and actual contract duration.
        """
        # Calculate expected seconds based on actual contract duration
        if CONTRACT_DURATION_UNIT == 'm':
            expected_seconds = CONTRACT_DURATION * 60
        elif CONTRACT_DURATION_UNIT == 's':
            expected_seconds = CONTRACT_DURATION
        elif CONTRACT_DURATION_UNIT == 'h':
            expected_seconds = CONTRACT_DURATION * 3600
        elif CONTRACT_DURATION_UNIT == 't':
            expected_seconds = CONTRACT_DURATION * 5  # ~5 sec per tick
        else:
            expected_seconds = 300  # default 5 min
        
        stuck_threshold_seconds = expected_seconds * 2  # 100% buffer (extra generous for time-based)
        
        current_time = time.time()
        for key, trade in list(self.active_contracts.items()):
            # Skip pending contracts (handled by tick-based cleanup)
            if isinstance(key, str) and key.startswith('pending_'):
                continue
            
            # Get the timestamp when the contract was opened
            trade_timestamp = trade.get('timestamp')
            if not trade_timestamp:
                continue
            
            try:
                # Parse the ISO timestamp
                opened_time = datetime.fromisoformat(trade_timestamp).timestamp()
                elapsed_seconds = current_time - opened_time
                
                if elapsed_seconds > stuck_threshold_seconds:
                    agent_logger.log_warning(
                        f"⚠️ Stuck contract detected (time-based): {key} open for {elapsed_seconds:.0f}s "
                        f"(expected ~{expected_seconds}s, threshold={stuck_threshold_seconds}s). "
                        f"Removing from active list."
                    )
                    del self.active_contracts[key]
            except (ValueError, TypeError) as e:
                agent_logger.log_warning(
                    f"⚠️ Could not parse timestamp for contract {key}: {e}. "
                    f"Removing from active list to prevent blocking."
                )
                del self.active_contracts[key]
    
    def _update_dashboard_state(self):
        """Update dashboard state file for web UI."""
        try:
            regime = self.current_market_analyzer.get_market_regime()
            risk_metrics = self.risk_manager.get_risk_metrics()
            
            # Prepare market opportunities for dashboard
            market_opps = []
            if hasattr(self.multi_market_monitor, 'current_opportunities'):
                opportunities = self.multi_market_monitor.current_opportunities
                # Handle both dict and list for robustness
                iterable_opps = opportunities.values() if isinstance(opportunities, dict) else opportunities
                for opp in iterable_opps:
                    market_opps.append({
                        'symbol': getattr(opp, 'symbol', 'Unknown'),
                        'score': getattr(opp, 'score', 0.0),
                        'confidence': getattr(opp, 'confidence', 0.0),
                        'strategy': getattr(opp, 'strategy', 'N/A'),
                        'market_state': getattr(opp, 'market_state', 'Unknown'),
                        'market_health': getattr(opp, 'health', 0.0)
                    })

            state = {
                'agent_id': self.agent_id,
                'symbol': self.symbol,
                'daily_profit': self.daily_profit,
                'daily_loss': self.daily_loss,
                'win_count': self.win_count,
                'loss_count': self.loss_count,
                'total_trades': self.total_trades,
                'consecutive_losses': self.consecutive_losses,
                'market_state': regime['state'],
                'market_health': regime['health'],
                'current_strategy': self.current_strategy,
                'confidence': self.confidence,
                'drawdown': risk_metrics['drawdown'],
                'max_drawdown': risk_metrics['max_drawdown'],
                'tick_count': self.tick_count,
                'warmup_progress': min(100, int(self.tick_count / 200 * 100)),
                'trading_paused': self.risk_manager.trading_paused,
                'pause_reason': getattr(self.risk_manager, 'pause_reason', None),
                'trade_direction': self.trade_direction,
                'ensemble_confidence': self.ensemble_confidence,
                'signals': {
                    'ml': self.current_signals.get('ml'),
                    'pattern': self.current_signals.get('patterns'),
                    'indicator': {k: v for k, v in self.current_signals.get('indicators', {}).items() if isinstance(v, (int, float, str))}
                },
                'recent_trades': self.session_trades[-10:],  # Last 10 trades
                'active_trades': [
                    {
                        'id': k,
                        'symbol': v['symbol'],
                        'type': v['contract_type'],
                        'prediction': v['prediction'],
                        'entry_price': v['entry_price'],
                        'buy_price': v['buy_price'],
                        'timestamp': v['timestamp'],
                        'ticks_open': self.tick_count - v.get('tick_opened', self.tick_count)
                    } for k, v in self.active_contracts.items()
                ],
                'market_opportunities': market_opps,
                'pnl_history': self.pnl_history[-50:],  # Last 50 points
                'last_update': datetime.now().isoformat(),
                # Current config settings (to sync back to dashboard)
                'config': {
                    'stake': self.risk_manager.current_stake,
                    'max_daily_loss': self.risk_manager.max_daily_loss,
                    'max_consec_losses': self.risk_manager.max_consecutive_losses,
                    'min_confidence': self.risk_manager.min_confidence_threshold,
                    'min_market_health': MIN_MARKET_HEALTH,
                    'use_martingale': self.risk_manager.use_martingale,
                    'martingale_step': self.risk_manager.martingale_step,
                    'martingale_active': self.risk_manager.martingale_step > 0,
                    'global_consec_losses': self.risk_manager.global_consecutive_losses,
                    'max_global_consec_losses': self.risk_manager.max_global_consecutive_losses
                }
            }
            
            # Check for stop signal file
            if os.path.exists('STOP_SIGNAL'):
                agent_logger.log_info("🛑 Stop signal detected from dashboard. Stopping agent...")
                self.running = False
                os.remove('STOP_SIGNAL')
            
            # Save to file
            with open('dashboard_state.json', 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            # Don't log on every failure to avoid spamming
            if self.tick_count % 100 == 0:
                agent_logger.log_error(f"Error updating dashboard state: {e}")

    def _process_dashboard_commands(self):
        """Process commands and setting changes from dashboard."""
        try:
            if not os.path.exists('dashboard_commands.json'):
                return
                
            with open('dashboard_commands.json', 'r') as f:
                commands = json.load(f)
            
            if not commands:
                return
                
            agent_logger.log_info(f"📥 Received dashboard commands: {commands}")
            
            # Process settings
            if 'settings' in commands:
                settings = commands['settings']
                if 'stake' in settings:
                    new_stake = float(settings['stake'])
                    self.risk_manager.base_stake = new_stake
                    self.risk_manager.current_stake = new_stake
                    agent_logger.log_info(f"⚙️ Base Stake updated to: ${new_stake}")
                if 'max_daily_loss' in settings:
                    self.risk_manager.max_daily_loss = float(settings['max_daily_loss'])
                    agent_logger.log_info(f"⚙️ Max Daily Loss updated to: ${self.risk_manager.max_daily_loss}")
                if 'max_consec_losses' in settings:
                    self.risk_manager.max_consecutive_losses = int(settings['max_consec_losses'])
                    agent_logger.log_info(f"⚙️ Max Consec Losses updated to: {self.risk_manager.max_consecutive_losses}")
                if 'min_confidence' in settings:
                    self.risk_manager.min_confidence_threshold = float(settings['min_confidence'])
                    agent_logger.log_info(f"⚙️ Min Confidence updated to: {self.risk_manager.min_confidence_threshold}")
                if 'use_martingale' in settings:
                    martingale_enabled = bool(settings['use_martingale'])
                    self.risk_manager.set_martingale_enabled(martingale_enabled)
                if 'max_global_consec_losses' in settings:
                    self.risk_manager.max_global_consecutive_losses = int(settings['max_global_consec_losses'])
                    agent_logger.log_info(f"⚙️ Max Global Consec Losses updated to: {self.risk_manager.max_global_consecutive_losses}")
            
            # Process actions
            if 'action' in commands:
                action = commands['action']
                if action == 'pause':
                    self.risk_manager.trading_paused = True
                    self.risk_manager.pause_reason = "Paused via dashboard"
                    agent_logger.log_info("⏸ Trading paused via dashboard")
                elif action == 'resume':
                    self.risk_manager.trading_paused = False
                    self.risk_manager.pause_reason = None
                    agent_logger.log_info("▶ Trading resumed via dashboard")
                elif action == 'reset_stats':
                    self.daily_profit = 0.0
                    self.daily_loss = 0.0
                    self.win_count = 0
                    self.loss_count = 0
                    self.consecutive_losses = 0
                    self.session_trades = []
                    self.pnl_history = []
                    self.risk_manager.reset_daily_stats()
                    agent_logger.log_info("🔄 Stats reset via dashboard")
                elif action == 'switch_market' and 'symbol' in commands:
                    new_symbol = commands['symbol']
                    if new_symbol in self.symbols and new_symbol != self.symbol:
                        agent_logger.log_info(f"🔄 Manual market switch to {new_symbol}")
                        self.symbol = new_symbol
                        self.current_market_analyzer = self.market_analyzers[self.symbol]
                        self.client.symbol = self.symbol
                elif action == 'force_trade' and 'direction' in commands:
                    direction = commands['direction']
                    agent_logger.log_info(f"🚀 FORCING manual trade: {direction}")
                    # Use a default strategy for forced trades
                    self._execute_trade('rise_fall', {
                        'features': self.current_market_analyzer.feature_engine.extract_features(),
                        'price': self.latest_price,
                        'timestamp': datetime.now().isoformat(),
                        'symbol': self.symbol
                    }, 1.0, self.risk_manager.current_stake, ensemble_direction=direction.lower())

            # Clear commands after processing
            os.remove('dashboard_commands.json')
            
        except Exception as e:
            agent_logger.log_error(f"Error processing dashboard commands: {e}")
    
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
    
    def _on_buy_confirmed(self, data: Dict):
        """Callback when a buy is confirmed by Deriv with a real contract_id."""
        contract_id = data.get('contract_id', '')
        buy_price = data.get('buy_price', 0)
        
        agent_logger.log_info(f"✅ Buy confirmed: contract_id={contract_id}, price=${buy_price:.2f}")
        
        # Find the pending contract and update its key to the real contract_id
        for key, info in list(self.active_contracts.items()):
            if isinstance(key, str) and key.startswith('pending_'):
                # Update the key to actual contract_id
                self.active_contracts[contract_id] = info
                del self.active_contracts[key]
                agent_logger.log_info(f"🔄 Updated pending contract {key} → real contract {contract_id}")
                break
    
    def _on_buy_failed(self, data: Dict):
        """Callback when a buy fails."""
        error = data.get('error', 'Unknown error')
        agent_logger.log_warning(f"❌ Buy failed: {error}")
        
        # Remove the pending contract so the agent can continue trading
        for key in list(self.active_contracts.keys()):
            if isinstance(key, str) and key.startswith('pending_'):
                del self.active_contracts[key]
                agent_logger.log_info(f"🗑️ Removed pending contract {key} due to buy failure")
                break
    
    def _on_tick_received(self, tick_data: Dict):
        """Callback when new tick is received from Deriv."""
        price = tick_data.get('quote')
        symbol = tick_data.get('symbol', self.symbol)
        
        # Update the appropriate market analyzer
        if symbol in self.market_analyzers:
            # If this is the current trading symbol, update latest_price
            if symbol == self.symbol:
                self.latest_price = price
            
            # Update the analyzer for this symbol
            # Note: This happens in the WebSocket thread, but the main loop
            # will process it in the next iteration
            # We'll handle the full update in the main loop
        else:
            agent_logger.log_warning(f"Received tick for unknown symbol: {symbol}")
    
    def _on_contract_result(self, result: Dict):
        """Callback when contract result is received."""
        contract_id = str(result.get('contract_id', ''))
        # Deriv API can return profit as string or number — normalize to float
        raw_profit = result.get('profit', 0)
        try:
            profit = float(raw_profit)
        except (ValueError, TypeError):
            profit = 0.0
        status = result.get('status', 'unknown')
        
        if contract_id in self.processed_contracts:
            agent_logger.log_info(f"⏭️ Contract {contract_id} already processed, skipping duplicate result.")
            return
        
        agent_logger.log_info(f"📋 Contract result received: ID={contract_id}, profit=${profit:.2f}, status={status}")
        agent_logger.log_info(f"📊 Active contracts before processing: {list(self.active_contracts.keys())}")
        
        # Find the trade in active contracts
        trade_info = None
        trade_key = None
        
        # First check if contract_id exists directly
        if contract_id in self.active_contracts:
            trade_key = contract_id
            trade_info = self.active_contracts[contract_id]
            agent_logger.log_info(f"✓ Found contract by ID: {contract_id}")
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
                    agent_logger.log_info(f"✓ Matched pending contract {key} to ID {contract_id}")
                    break
        
        if not trade_info:
            agent_logger.log_warning(
                f"⚠️ Contract {contract_id} not found in active contracts. "
                f"Active: {list(self.active_contracts.keys())}. "
                f"This might be an old contract or already processed."
            )
            return
        
        # Process the result
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
            agent_logger.log_info(
                f"✓ WIN: Contract {contract_id} - Profit: ${profit:.2f} | "
                f"Total: {self.win_count}W/{self.loss_count}L "
                f"({self.win_count/(self.win_count+self.loss_count)*100:.1f}%)"
            )
        else:
            self.loss_count += 1
            self.daily_loss += abs(profit)
            self.consecutive_losses += 1
            agent_logger.log_info(
                f"✗ LOSS: Contract {contract_id} - Loss: ${abs(profit):.2f} | "
                f"Total: {self.win_count}W/{self.loss_count}L "
                f"({self.win_count/(self.win_count+self.loss_count)*100:.1f}%)"
            )
        
        # Record in risk manager
        stake = trade_info.get('buy_price', 0)
        self.risk_manager.record_trade_result(stake, is_win, profit)
        
        # Record in multi-market monitor for symbol-specific performance
        trade_symbol = trade_info.get('symbol', self.symbol)
        if self.monitoring_multiple_markets:
            self.multi_market_monitor.record_trade_result(trade_symbol, is_win, profit)
        
        # Update trade count and PnL history
        cumulative_pnl = self.daily_profit - self.daily_loss
        self.pnl_history.append(cumulative_pnl)
        
        # Update trade info with result
        trade_info['pnl'] = profit
        trade_info['result'] = 'win' if is_win else 'loss'
        trade_info['closed_tick'] = self.tick_count
        self.session_trades.append(trade_info)
        
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
        
        # CRITICAL: Remove from active contracts
        if contract_id in self.active_contracts:
            del self.active_contracts[contract_id]
            agent_logger.log_info(f"🗑️ Removed contract {contract_id} from active list")
        
        self.processed_contracts.add(contract_id)
        agent_logger.log_info(f"📊 Active contracts after processing: {list(self.active_contracts.keys())}")
        agent_logger.log_info(f"✅ Contract {contract_id} fully processed and closed")
    
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
    
    def _execute_trade(self, strategy: str, market_data: Dict, confidence: float, position_size: float, ensemble_direction: str = None):
        """Execute a trade using the selected strategy with ML enhancement and ensemble direction."""
        try:
            # Get actual prediction from the strategy (technical analysis)
            strategy_obj = self.strategy_selector.strategies.get(strategy)
            if not strategy_obj:
                agent_logger.log_error(f"Strategy {strategy} not found")
                return
            
            # Get the technical analysis signal
            signal = strategy_obj.analyze(market_data)
            
            # If ensemble direction is provided, trust it and bypass strategy action check
            # The ensemble has already considered all signals (ML, patterns, indicators)
            if not ensemble_direction and signal.action != 'BUY':
                agent_logger.log_info(
                    f"❌ Trade blocked: Strategy {strategy} returned action={signal.action} (expected BUY)"
                )
                return  # Strategy says don't trade
            
            # Initialize variables for logging
            ta_prediction = None
            ml_prediction = 'HOLD'
            ml_confidence = 0.0
            
            # Get ML stats for logging
            ml_stats = self.ml_predictor.get_stats()
            
            # Use ensemble direction if provided, otherwise fall back to strategy
            if ensemble_direction:
                final_prediction = ensemble_direction.upper()  # 'UP' or 'DOWN'
                final_confidence = confidence
                agent_logger.log_info(
                    f"✓ Using ensemble direction: {final_prediction} (conf={final_confidence:.2f}) | "
                    f"ML Stats: training_acc={ml_stats['model_accuracy']:.2%}, "
                    f"live_acc={ml_stats.get('live_accuracy', 0):.2%}, "
                    f"samples={ml_stats['training_samples']}"
                )
            else:
                # Get ML prediction as fallback
                ml_prediction, ml_confidence = self.ml_predictor.predict(market_data)
                
                # Convert strategy prediction to UP/DOWN
                if strategy == 'higher_lower':
                    ta_prediction = 'UP' if signal.contract_type == 'HIGHER' else 'DOWN'
                elif strategy == 'rise_fall':
                    ta_prediction = 'UP' if signal.contract_type == 'RISE' else 'DOWN'
                else:
                    ta_prediction = 'UP'  # Default for accumulator
                
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
            
            # Get current market conditions for logging
            current_price = market_data['features'].get('price_current', 0)
            rsi = market_data['features'].get('rsi', 50)
            macd = market_data['features'].get('macd_histogram', 0)
            bb_position = market_data['features'].get('bb_position', 0.5)
            
            # Log comprehensive trade information
            agent_logger.log_info("=" * 80)
            agent_logger.log_info(f"🎯 PLACING TRADE #{self.total_trades + 1}")
            agent_logger.log_info("=" * 80)
            agent_logger.log_info(f"Strategy: {strategy} | Direction: {final_prediction} ({display_prediction})")
            agent_logger.log_info(f"Confidence: {final_confidence:.2%} | Position Size: ${position_size:.2f}")
            agent_logger.log_info(f"Market: {self.symbol} | State: {self.current_market_state} | Health: {self.market_health:.1f}")
            agent_logger.log_info(f"Price: {current_price:.5f} | RSI: {rsi:.1f} | MACD: {macd:.5f} | BB: {bb_position:.2f}")
            agent_logger.log_info(f"ML Training Acc: {ml_stats['model_accuracy']:.2%} | Live Acc: {ml_stats.get('live_accuracy', 0):.2%}")
            agent_logger.log_info(f"ML Samples: {ml_stats['training_samples']} | Predictions: {ml_stats['predictions_made']}")
            agent_logger.log_info(f"Win/Loss Record: {self.win_count}W / {self.loss_count}L ({self.win_count/(self.win_count+self.loss_count)*100 if (self.win_count+self.loss_count) > 0 else 0:.1f}%)")
            agent_logger.log_info(f"Consecutive Losses: {self.consecutive_losses}")
            agent_logger.log_info("=" * 80)
            
            # Log trade execution
            agent_logger.log_decision({
                'action': 'execute_trade',
                'strategy': strategy,
                'ensemble_direction': ensemble_direction,
                'ta_prediction': ta_prediction if ta_prediction else 'N/A',
                'ml_prediction': ml_prediction if ml_prediction != 'HOLD' else 'N/A',
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
                
                agent_logger.log_info(f"🔄 Placing order: {contract_type} on {self.symbol} for ${position_size_rounded} ({duration}{duration_unit})")
                
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
                    'symbol': self.symbol,  # Track which symbol this trade is on
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
                    'timestamp': datetime.now().isoformat(),
                    'tick_opened': self.tick_count  # Track when opened
                }
                
                agent_logger.log_info(
                    f"✅ Trade #{self.total_trades}: {strategy} → {display_prediction} ({contract_type}) "
                    f"@ ${position_size_rounded:.2f} | Conf: {final_confidence:.2f} | "
                    f"Active: {len(self.active_contracts)} | Tick: {self.tick_count}"
                )
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
    
    
    def _find_best_market_opportunity(self):
        """Find the best trading opportunity across all monitored markets."""
        try:
            # Build market data dict for all symbols
            market_data_dict = {}
            for symbol in self.symbols:
                analyzer = self.market_analyzers[symbol]
                if len(analyzer.price_history) < 20:
                    continue
                
                features = analyzer.feature_engine.extract_features()
                market_data_dict[symbol] = {
                    'features': features,
                    'price': features.get('price_current', 0),
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol
                }
            
            # Use multi-market monitor to scan all markets
            if market_data_dict:
                opportunities = self.multi_market_monitor.scan_all_markets(market_data_dict)
                if opportunities:
                    best = opportunities[0]  # Already sorted by score
                    return type('Opportunity', (), {
                        'symbol': best.symbol,
                        'score': best.score,
                        'confidence': best.confidence,
                        'strategy': best.strategy,
                        'market_state': best.market_state,
                        'health': best.health
                    })()
            
            return None
        except Exception as e:
            agent_logger.log_warning(f"Error finding best market opportunity: {e}")
            return None
    
    def _calculate_current_market_score(self) -> float:
        """Calculate score for current market."""
        try:
            regime = self.current_market_analyzer.get_market_regime()
            health = regime['health']
            
            # Get current strategy confidence
            features = self.current_market_analyzer.feature_engine.extract_features()
            market_data = {
                'features': features,
                'price': features.get('price_current', 0),
                'timestamp': datetime.now().isoformat(),
                'symbol': self.symbol
            }
            strategy, confidence = self.strategy_selector.select_strategy(market_data)
            
            # Calculate score (same formula as MarketOpportunity)
            score = 50.0
            score += confidence * 20
            score += (health / 100) * 20
            
            # Pattern bonus
            patterns = self.pattern_recognizer.detect_all_patterns()
            if patterns:
                score += min(len(patterns) * 5, 10)
            
            return min(score, 100.0)
        except Exception as e:
            agent_logger.log_warning(f"Error calculating current market score: {e}")
            return 50.0
    
    def _log_multi_market_status(self):
        """Log status of all monitored markets."""
        try:
            market_status = self.multi_market_monitor.get_market_status()
            opportunities = self.multi_market_monitor.current_opportunities
            
            agent_logger.log_info("=" * 80)
            agent_logger.log_info(f"📊 MULTI-MARKET STATUS (Tick {self.tick_count})")
            agent_logger.log_info("=" * 80)
            
            # Sort by opportunity score
            sorted_markets = sorted(
                market_status.items(),
                key=lambda x: x[1].get('opportunity_score', 0),
                reverse=True
            )
            
            for symbol, status in sorted_markets:
                is_current = "🎯" if symbol == self.symbol else "  "
                has_opp = "✓" if status['has_opportunity'] else "✗"
                
                patterns_str = ", ".join(status['patterns'][:3]) if status['patterns'] else "none"
                if len(status['patterns']) > 3:
                    patterns_str += f" +{len(status['patterns'])-3} more"
                
                agent_logger.log_info(
                    f"{is_current} {symbol:8} | "
                    f"Score: {status['opportunity_score']:5.1f} | "
                    f"Health: {status['health']:5.1f} | "
                    f"State: {status['market_state']:15} | "
                    f"Strategy: {status['opportunity_strategy']:12} | "
                    f"Opp: {has_opp} | "
                    f"Patterns: {patterns_str}"
                )
            
            agent_logger.log_info("=" * 80)
            
            # Show performance stats
            performance = self.multi_market_monitor.get_all_performance()
            if any(p['trades'] > 0 for p in performance.values()):
                agent_logger.log_info("📈 PERFORMANCE BY MARKET:")
                for symbol, perf in performance.items():
                    if perf['trades'] > 0:
                        agent_logger.log_info(
                            f"  {symbol}: {perf['wins']}W/{perf['losses']}L "
                            f"({perf['win_rate']:.1%}) | "
                            f"Profit: ${perf['profit']:.2f}"
                        )
                agent_logger.log_info("=" * 80)
            
        except Exception as e:
            agent_logger.log_warning(f"Error logging multi-market status: {e}")
    
    def _log_status(self):
        """Log agent status."""
        regime = self.current_market_analyzer.get_market_regime()
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