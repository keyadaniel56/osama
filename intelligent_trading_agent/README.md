# Intelligent Trading Agent

An AI-powered trading bot for Deriv synthetic indices (R_10 through R_100) that uses machine learning, reinforcement learning, multi-timeframe trend analysis, chart pattern recognition, and ensemble decision-making to trade Rise/Fall contracts.

## 🧠 Core Architecture

```
IntelligentTradingAgent
├── Market Analysis
│   ├── MarketAnalyzer (state detection, health scoring)
│   ├── FeatureEngine (50+ technical indicators)
│   └── MultiTimeframeTrendAnalyzer (5 timeframes + sure trend scoring)
├── Pattern Recognition
│   ├── ChartPatternRecognizer (8+ chart patterns)
│   ├── CandlePatternLearner (candlestick patterns + learning)
│   └── MultiTimeframeTrendAnalyzer (ultra_short→higher)
├── Machine Learning
│   ├── MLPredictor (RandomForest + GradientBoosting ensemble)
│   └── ReinforcementLearningSystem (Q-learning with experience replay)
├── Decision Engine
│   ├── DecisionEngine (ensemble: trend + patterns + ML + indicators)
│   └── RiskAdjustedDecision (confidence adjustments)
├── Strategy Selection
│   ├── RiseFallStrategy (BB extreme continuation - 55.7% edge)
│   ├── HigherLowerStrategy (RSI extremes)
│   └── AccumulatorStrategy (trend following)
├── Risk Management
│   ├── RiskManager (Kelly sizing, drawdown, martingale, 2-loss hard limit)
│   └── ProfitCompounder (automatic stake growth)
├── Multi-Market Monitor
│   └── Scans R_100, R_75, R_50, R_25, R_10 simultaneously
├── Deriv API Client
│   └── WebSocket + REST, auto-reconnect, tick health monitoring
├── Terminal UI
│   └── Real-time ANSI dashboard (no external deps)
└── Logging
    ├── agent.log, trades.log, market_analysis.log, decisions.log
```

## 📦 Components

### 1. Agent Orchestrator (`agent.py`)
**Class: `IntelligentTradingAgent`** (1991 lines)

The central coordinator that initializes and manages all subsystems in a main trading loop.

**Key Initialization:**
- Creates per-symbol `MarketAnalyzer` instances for all 5 symbols
- Initializes: `StrategySelector`, `LearningSystem`, `RiskManager`, `MLPredictor`, `ChartPatternRecognizer`, `DecisionEngine`, `RiskAdjustedDecision`, `MultiMarketMonitor`, `ReinforcementLearningSystem`, `DerivClient`, `TerminalUI`
- Tracks: tick_count, total_trades, win/loss counts, daily profit/loss, consecutive losses, active contracts, market state, ensemble confidence

**Main Trading Loop (`_trading_loop`):**
1. **Tick Processing**: Processes new ticks for ALL symbols, updates per-symbol market analyzers
2. **ML Observation**: Feeds market data to `ml_predictor.observe_market()` every tick; validates predictions every `CONTRACT_DURATION * 60` ticks
3. **Multi-Market Monitoring**: Every 25 ticks, scans all markets and potentially switches to the best trending market (with safeguards: won't switch with active contract, requires trending state, uses score thresholds)
4. **Market Analysis**: Detects market state (trending_up/down, ranging, volatile, calm) and calculates health score
5. **Pattern Detection**: Runs `ChartPatternRecognizer.detect_all_patterns()` for chart patterns + candlestick patterns + multi-timeframe trend
6. **ML Prediction**: Gets direction prediction from ML ensemble
7. **Ensemble Decision**: `DecisionEngine.make_decision()` combines trend + ML + patterns + indicators
8. **RL Decision**: `ReinforcementLearningSystem.decide()` provides Q-learning based trade/no-trade signal
9. **Risk Check**: `RiskManager.should_trade()` enforces all risk limits
10. **Trade Execution**: If all checks pass, calls `buy_contract()` on Deriv API
11. **Contract Monitoring**: Tracks active contracts via `_on_contract_result` callback; handles stuck contracts with time-based and tick-based cleanup
12. **Learning**: Records trade results in `LearningSystem` and `ReinforcementLearningSystem`

### 2. Configuration (`config.py`)
All settings loaded from `.env` file with sensible defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DERIV_API_TOKEN` | `""` | Deriv API token |
| `DERIV_APP_ID` | `1089` | Deriv application ID |
| `BASE_STAKE` | `1.0` | Base stake amount |
| `MIN_STAKE_AMOUNT` | `0.35` | Deriv minimum stake |
| `TAKE_PROFIT` | `10.0` | Profit target |
| `STOP_LOSS` | `5.0` | Stop loss |
| `CONTRACT_DURATION` | `5` | Contract duration value |
| `CONTRACT_DURATION_UNIT` | `m` | Duration unit (m/s/h/t) |
| `MAX_CONCURRENT_TRADES` | `1` | Max open trades at once |
| `MAX_DAILY_LOSS` | `10.0` | Daily loss limit |
| `MAX_CONSEC_LOSSES` | `3` | Consecutive loss limit |
| `MAX_DRAWDOWN` | `20.0` | Maximum drawdown % |
| `USE_MARTINGALE` | `false` | Enable martingale |
| `MAX_GLOBAL_CONSEC_LOSSES` | `4` | Global loss limit across markets |
| `MIN_CONFIDENCE` | `0.78` | Minimum confidence to trade |
| `HIGH_CONFIDENCE` | `0.85` | High quality threshold |
| `ULTRA_CONFIDENCE` | `0.92` | Ultra high quality threshold |
| `MIN_MARKET_HEALTH` | `65` | Minimum market health score |
| `TRADE_COOLDOWN_TICKS` | `50` | Min ticks between trades |
| `FEATURE_WINDOW` | `30` | Feature calculation window |
| `NUM_FEATURES` | `50` | Number of features |
| `RETRAIN_EVERY` | `50` | Retrain model every N trades |
| `CONTINUOUS_LEARNING` | `true` | Learn from each trade |
| `AVAILABLE_SYMBOLS` | `["R_100", "R_75", "R_50", "R_25", "R_10"]` | Trading symbols |
| `DEFAULT_SYMBOL` | `R_100` | Default trading symbol |

### 3. Market Analyzer (`market_analyzer.py`)
**Class: `MarketAnalyzer`** (347 lines)

Detects market conditions and assigns health scores tailored for synthetic indices.

**Market States Detected:**
- `trending_up` / `trending_down` - Price above/below both SMA-20 and SMA-50 with sustained momentum
- `ranging` - Price oscillating around SMAs with low momentum
- `volatile` - Extreme volatility (overrides all other states)
- `calm` - Very low volatility and momentum
- `unknown` - Insufficient data

**Key Methods:**
- `detect_market_state()` - Uses SMA alignment, momentum, RSI, trend strength, and volatility
- `calculate_market_health()` - 0-100 score based on volatility, trend strength, momentum, RSI, BB position, MA alignment
- `get_market_regime()` - Returns detailed regime info with health, volatility, momentum, RSI, trend strength
- `get_strategy_recommendation()` - Recommends strategy based on market state
- `get_price_trend()` - Normalized trend strength (-1 to 1)
- `get_support_resistance_levels()` - Identifies key S/R levels using percentiles

**Synthetic Index Optimizations:**
- Lower momentum thresholds (synthetic indices trend more subtly)
- Requires SUSTAINED directionality (price above/below both SMA-20 AND SMA-50)
- Stricter ranging detection (low momentum + price crossing SMA)
- Ranging markets get health penalties; trending markets get bonuses

### 4. Feature Engineering (`features/indicators.py`)
**Classes: `TechnicalIndicators` + `FeatureEngine`** (285 lines)

Computes 50+ features from price data:

**Price Features:** current, min, max, range
**Moving Averages:** SMA(10, 20, 50), EMA(12, 26)
**Momentum:** RSI(14), momentum(10, 20), price direction
**MACD:** line, signal, histogram, positive flag
**Bollinger Bands:** upper, middle, lower, bandwidth, position
**Volatility:** normalized volatility (0-1), high/low flags
**ATR:** average true range, ATR ratio
**Volume:** On-Balance Volume
**Trend:** trend strength (SMA ratio), MA crossover, price vs SMA

### 5. Pattern Recognition (`features/pattern_recognition.py`)
**Classes: `ChartPatternRecognizer`, `CandlePatternLearner`, `MultiTimeframeTrendAnalyzer`** (770 lines)

**ENHANCED: Sure Trend Detection System**
The bot now uses a 5-timeframe trend analysis system with a confidence scoring mechanism to identify "SURE TRENDS" - trends so clear that the bot can trade them with high confidence on lower timeframes.

**5 Timeframes (ENHANCED from 4):**
- `ultra_short`: 10 ticks (~10 seconds) - immediate momentum for quick entries
- `micro`: 20 ticks (~20 seconds) - entry timing
- `lower`: 50 ticks (~50 seconds) - short-term trend
- `medium`: 100 ticks (~1.7 minutes) - secondary trend
- `higher`: 200 ticks (~3.3 minutes) - primary trend

**Trend Confidence Scoring (0-100):**
1. **Timeframe alignment** (max 40 points): All 5 aligned = 40pts, 4 aligned = 30pts, 2 aligned = 20pts
2. **R-squared strength** (max 30 points): 10pts per timeframe (higher, medium, lower)
3. **Momentum consistency** (max 20 points): All timeframes have momentum in same direction
4. **Trend persistence** (max 10 points): 1 point per 5 ticks of consistent direction

**"Sure Trend" Definition:**
- `trend_confidence_score >= 80` AND `trend_persistence >= 20 ticks`
- When a sure trend is detected, the bot can trade with lower confidence thresholds
- Sure trends get a 10-20% confidence bonus in the decision engine
- Sure trends allow up to 20% stake increase in position sizing
- Sure trends reduce minimum confidence threshold by 0.05 and health requirement by 5

**Chart Patterns Detected:**
- Head & Shoulders (bearish reversal)
- Double Top / Double Bottom (reversal patterns)
- Triangle (breakout pending)
- Flag (continuation pattern)
- Rising/Falling Wedge
- Breakout from consolidation
- Support/Resistance levels

**Candlestick Patterns:**
- Bullish/Bearish Engulfing
- Bullish/Bearish Harami
- Doji (indecision)
- Hammer (bullish reversal)
- Shooting Star (bearish reversal)
- Three White Soldiers (bullish continuation)
- Three Black Crows (bearish continuation)

**CandlePatternLearner:**
- Tracks how each candle type predicts the next N candles' direction
- Builds statistical model of candle pattern effectiveness
- Reports best performing patterns with accuracy data

**MultiTimeframeTrendAnalyzer:**
- 4 timeframes: higher (200 ticks), medium (100), lower (50), micro (20)
- Higher timeframe gets 4x weight, medium 2x, lower 1x, micro 0.5x
- Only returns trending when higher + medium timeframes agree
- R-squared based trend strength calculation
- Alignment score across all timeframes

### 6. Machine Learning Predictor (`ml_predictor.py`)
**Class: `MLPredictor`** (638 lines)

Ensemble of two models for price direction prediction:

**Models:**
- `RandomForestClassifier` (50 trees, max_depth=6, min_samples_split=20, min_samples_leaf=10)
- `GradientBoostingClassifier` (50 estimators, max_depth=4, learning_rate=0.08)

**Key Features:**
- **Market Observation Learning**: Learns from actual price movements, not trade results
- **Lookahead Prediction**: Predicts price direction `CONTRACT_DURATION` minutes ahead
- **Balanced Training**: Automatically balances UP/DOWN classes to prevent bias
- **Time-Series Validation**: 70/30 train/test split maintaining temporal order
- **Live Validation**: Validates predictions against actual price movements
- **Accuracy-Based Confidence**: Only uses ML signal when model accuracy > 55%
- **Auto-Training**: Retrains every 30 observations with class diversity check
- **Support/Resistance Features**: Distance to S/R, S/R strength, near S/R flags
- **Trend Features**: Trend strength, price velocity, trend consistency, high/low ratio
- **Pattern Features**: Bullish/bearish pattern flags, breakout detection

**Feature Vector (35 features):**
- RSI, MACD (line/signal/histogram), BB position/width
- Momentum (5/10/20), volatility, ATR
- SMA (5/10/20), EMA (5/10/20)
- Price changes (1/5/10 ticks)
- Trend strength, price velocity, trend consistency, high/low ratio
- Distance to support/resistance, S/R strength, near S/R
- Pattern features (bullish/bearish/breakout)

### 7. Reinforcement Learning System (`reinforcement_learning.py`)
**Classes: `ReinforcementLearningSystem`, `RLEngine`, `MarketStateEncoder`, `ProfitCompounder`, `ExperienceReplay`** (743 lines)

**RLEngine:**
- Linear Q-learning with 18-dimensional state space
- 2 actions: skip (0) or take_trade (1)
- Adam optimizer with momentum
- Epsilon-greedy exploration (starts at 1.0, decays to 0.05)
- Prioritized experience replay (2000 experiences max)

**MarketStateEncoder:**
Encodes 18 features: RSI, BB position, volatility, momentum (10/20), trend strength, MA crossover, price vs SMA, price direction, RSI overbought/oversold, volatility high/low, MACD positive, recent win rate, consecutive losses, current stake %, trade count

**Reward Function:**
- Win: `+profit/stake * 10` (capped at 5.0)
- Loss: `-abs(profit)/stake * 5` (capped at -5.0)
- Skip: neutral (0.0)

**ProfitCompounder:**
- Automatically grows stake as account equity increases
- Growth rate: 15% of profits added to stake
- Requires 20% equity increase from last growth point
- Max 50% stake increase per step
- Tracks milestones for logging

### 8. Decision Engine (`decision_engine.py`)
**Classes: `DecisionEngine` + `RiskAdjustedDecision`** (533 lines)

**ENHANCED: Pattern-First Approach**
The decision engine now prioritizes patterns and trend over raw indicators. This is a fundamental shift from indicator-based trading to pattern-based trading.

**Ensemble Weights (ENHANCED):**
- Multi-timeframe trend: 35% (PRIMARY - increased)
- Chart patterns: 30% (SECONDARY - increased, patterns over ML)
- ML predictions: 25% (tertiary - decreased)
- Technical indicators: 10% (quaternary - supporting only)

**Sure Trend Override:**
When `trend_confidence_score >= 80` and at least one other signal agrees with the trend:
- Bypasses normal confidence threshold checks
- Returns boosted confidence (up to 0.95)
- Allows trading with just trend + 1 confirming signal
- Logs "🎯 SURE TREND CONFIRMED" for transparency

**Confidence Bonuses:**
- Sure trend bonus: +10-20% confidence (scaled by trend_confidence_score)
- Pattern confirmation bonus: +12% when patterns confirm trend direction
- Perfect agreement: +20% boost
- Majority agreement: +5% boost
- Disagreement: -30% penalty

**Key Rules:**
- Multi-timeframe trend is PRIMARY - only trade if higher+medium agree
- In ranging markets, trading is STRONGLY DISFAVORED (requires 2+ signal sources)
- Never trade against the higher timeframe trend
- ML threshold raised to 0.65 to filter noise
- Trend disagreement is a hard block, not just a penalty
- Single source signals blocked in non-trending markets
- Perfect agreement boosts confidence 20%
- Disagreement reduces confidence 30%

**RiskAdjustedDecision:**
- Reduces confidence after consecutive losses (10% per loss)
- Boosts confidence after winning streaks (5% per win, max 3)
- Reduces confidence 15% if win rate < 45%

### 9. Trading Strategies

#### Rise/Fall (`strategies/rise_fall.py`)
**Class: `RiseFallStrategy`** (172 lines)

**Empirically Proven Edge:**
- BB extreme continuations: 55.7% win rate (ONLY edge)
- All other indicators: ~50% (random walk)
- Confidence > 0.88: 9.9% win rate (confidence system BROKEN at extremes)
- Confidence 0.80-0.87: 51.7% win rate (best range)

**Key Rules:**
1. ONLY trade BB extreme continuations (the only signal with edge)
2. CAP confidence at 0.85 (higher confidence = WORSE performance)
3. Filter out RSI extremes (RSI > 90 or < 10 = noise)
4. Need momentum confirmation for continuation trades
5. Volatility filter: reduce confidence 15% if volatility > 0.8

#### Higher/Lower (`strategies/higher_lower.py`)
**Class: `HigherLowerStrategy`** (83 lines)
- RSI-based: oversold (<30) → HIGHER, overbought (>70) → LOWER
- Momentum confirmation (+0.1 confidence)
- Volatility adjustment (0.9x if > 0.6)
- 60-second contracts

#### Accumulator (`strategies/accumulator.py`)
**Class: `AccumulatorStrategy`** (91 lines)
- Trend following: price > SMA-50 + SMA-20 > SMA-50 + momentum > 0
- MA alignment bonus (+0.05 confidence)
- Volatility reduction (0.85x if > 0.8)
- 5-minute contracts

### 10. Risk Manager (`risk_manager.py`)
**Class: `RiskManager`** (524 lines)

**ENHANCED: Hard 2-Loss Limit & Sure Trend Awareness**

**Position Sizing (ENHANCED):**
- Starts at user's configured base_stake
- **Sure trend bonus**: +0-20% stake increase when trend_confidence_score >= 80
- **First loss protection**: -50% stake reduction after 1 consecutive loss (prevents second loss from being bigger)
- Low confidence reduction (proportional to confidence deficit)
- Volatility reduction (0.5x if > 1.0, 0.75x if > 0.7)
- Drawdown reduction (linear penalty from 5% to max_drawdown)
- Martingale override (1.5x multiplier, max 2 steps, capped at 4x base)
- Kelly Criterion tracking (for informational purposes)

**Risk Limits (ENHANCED):**
- **HARD 2-LOSS LIMIT**: After 2 consecutive losses, MUST pause trading (was 3)
- **HARD GLOBAL 2-LOSS LIMIT**: After 2 losses across market switches, MUST pause (was 4)
- Daily loss limit (MAX_DAILY_LOSS)
- Maximum daily trades (20)
- Profit target (TAKE_PROFIT)
- Stop loss (STOP_LOSS)
- Trailing stop (30% below peak profit)
- Maximum drawdown (MAX_DRAWDOWN)
- Minimum market health (MIN_MARKET_HEALTH - raised to 70)
- Minimum confidence threshold (MIN_CONFIDENCE - raised to 0.82)

**Sure Trend Override in Risk Manager:**
When `is_sure_trend=True` and `trend_confidence_score >= 80`:
- Reduces minimum confidence threshold by 0.05 (e.g., 0.82 → 0.77)
- Reduces minimum health requirement by 5 (e.g., 70 → 65)
- Allows trading in conditions that would normally be blocked
- This ensures the bot doesn't miss strong trends due to overly strict thresholds

**Adaptive Confidence:**
- Win rate < 40%: raise threshold to MIN_CONFIDENCE + 0.1 (max 0.85)
- Win rate > 60%: lower threshold to MIN_CONFIDENCE - 0.05 (min 0.55)

**Auto-Resume:**
- Learning system pauses auto-resume after 500 ticks
- Other pauses require manual resume

### 11. Multi-Market Monitor (`multi_market_monitor.py`)
**Class: `MultiMarketMonitor`** (334 lines)

Monitors all 5 symbols simultaneously with per-symbol analyzers, selectors, and pattern recognizers.

**Opportunity Scoring:**
- Base score: 50
- Confidence component: +confidence * 20
- Health component: +(health/100) * 20
- Trending bonus: +20
- Ranging penalty: -15
- Volatile penalty: -20
- Pattern bonus in trend: +8 per pattern (max 16)
- Pattern bonus in non-trend: +2 per pattern (max 4)

**Market Switching Logic:**
- Won't switch while active contract is open (market lock)
- If current is NOT trending: switch to any trending market with higher score
- If current IS trending: require 25-point score difference to switch
- Target must be in trending state

### 12. Deriv API Client (`deriv_client.py`)
**Class: `DerivClient`** (844 lines)

**Connection Strategy:**
1. Try REST API authentication (PAT token + Deriv-App-ID) for OTP WebSocket
2. Fall back to public WebSocket for market data only

**Features:**
- Multi-symbol tick subscription (all 5 symbols simultaneously)
- Automatic reconnection (up to 10 attempts, progressive backoff)
- Tick health monitoring (30-second timeout, auto-resubscribe)
- Two-step buy flow (proposal → buy with proposal_id)
- Contract result tracking via `proposal_open_contract` subscription
- Stuck contract detection and cleanup
- Per-symbol tick counters (unlimited) and history (500 max)

**Callbacks:**
- `on_tick` - New tick received
- `on_buy_confirmed` - Buy executed with contract_id
- `on_buy_failed` - Buy failed
- `on_contract_result` - Contract closed with profit/loss
- `on_error` - API or connection error

### 13. Strategy Selector (`strategy_selector.py`)
**Class: `StrategySelector`** (183 lines)

- Tracks performance of each strategy in each market state
- Uses market analyzer recommendation as primary signal (+0.1 boost)
- Strategy switch cooldown (10 ticks)
- Records trade results per strategy per market state
- Can query best strategy for any market state

### 14. Learning System (`learning_system.py`)
**Class: `LearningSystem`** (313 lines)

- Tracks trade history (1000 max) with full metadata
- Performance metrics per strategy+market_state combination
- Optimal confidence threshold calculation based on historical win rates
- Adaptation recommendations (stake adjustment, pause trading, strategy switch)
- Periodic save to disk (every 5 minutes)
- Loads previous session data on startup
- Exportable learning report

### 15. Terminal UI (`terminal_ui.py`)
**Class: `TerminalUI`**

Real-time terminal dashboard using ANSI escape codes (no external dependencies).

**Display Sections:**
1. **Header**: Agent ID, spinner, last update time
2. **Status Bar**: Live/Disconnected/Paused, symbol, tick count, trade count
3. **Market Analysis**: State (colored), health bar, multi-TF trend, strategy, signals, confidence bar, patterns
4. **Performance**: W/L count, win rate %, P&L, session profit with peak, trailing stop, loss streaks
5. **Risk Management**: Stake info, Martingale step, Kelly fraction, drawdown %, adaptive threshold, ML accuracy
6. **Active Contracts**: Contract list with type, prediction, entry price, tick opened
7. **Price Chart**: Mini sparkline from deque(maxlen=60)

### 16. Logging (`logger.py`)
**Class: `AgentLogger`** (90 lines)

Four log files in `logs/` directory:
- `agent.log` - Main agent operations
- `trades.log` - Trade execution records
- `market_analysis.log` - Market analysis results
- `decisions.log` - Trading decisions

### 17. Backtesting (`backtest_bot.py`)
**Class: `BacktestRunner`** (509 lines)

Replays historical price data through bot subsystems without connecting to Deriv.

**Tests:**
- Market analysis (state detection, health scoring)
- Momentum-following strategy (Rise/Fall with BB extremes)
- Decision engine (ensemble signals)
- Risk management (position sizing, drawdown)
- Pattern recognition

**Reports:**
- Overall win rate, profit factor, Sharpe ratio
- Performance by market state
- Performance by confidence range
- Performance by signal type
- Trade-by-trade log

## 🚀 Quick Start

### 1. Setup

```bash
# Navigate to the agent directory
cd intelligent_trading_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required `.env` settings:
```env
DERIV_API_TOKEN=your_token_here
DERIV_APP_ID=1089
STAKE=0.35
SYMBOL=R_100
CONTRACT_DURATION=5
CONTRACT_DURATION_UNIT=m
```

### 3. Run

```bash
# Start the trading agent
python agent.py

# Or use the shell script
./run_agent.sh
```

### 4. Backtest

```bash
python backtest_bot.py
```

## 📊 Configuration Reference

See `config.py` for all configurable parameters. Key settings in `.env`:

```env
# === API Configuration ===
DERIV_API_TOKEN=your_token
DERIV_APP_ID=1089

# === Trading Configuration ===
STAKE=0.35              # Base stake amount
TAKE_PROFIT=10.0        # Profit target
STOP_LOSS=5.0           # Stop loss
CONTRACT_DURATION=5     # Contract duration
CONTRACT_DURATION_UNIT=m # s=seconds, m=minutes, h=hours, t=ticks
MAX_CONCURRENT_TRADES=1 # Max open trades

# === Risk Management ===
MAX_DAILY_LOSS=10.0     # Daily loss limit
MAX_CONSEC_LOSSES=3     # Consecutive loss limit
MAX_DRAWDOWN=20.0       # Maximum drawdown
USE_MARTINGALE=false    # Enable martingale
MAX_GLOBAL_CONSEC_LOSSES=4 # Global loss limit

# === Agent Decision Thresholds ===
MIN_CONFIDENCE=0.78     # Minimum confidence to trade
HIGH_CONFIDENCE=0.85    # High quality threshold
ULTRA_CONFIDENCE=0.92   # Ultra high quality threshold
MIN_MARKET_HEALTH=65    # Minimum market health
TRADE_COOLDOWN_TICKS=50 # Min ticks between trades

# === Model Configuration ===
RETRAIN_EVERY=50        # Retrain model every N trades
CONTINUOUS_LEARNING=true # Learn from each trade

# === Trading Symbols ===
SYMBOL=R_100            # Default trading symbol
```

## 📈 Performance Goals

- **Win Rate**: > 55% (BB extreme continuation edge + sure trend detection)
- **Risk Management**: HARD 2 consecutive loss limit - MUST pause after 2 losses
- **Lower Timeframe Profitability**: 3-minute contracts with 5-timeframe trend analysis
- **Pattern-First Trading**: Prioritizes chart patterns and multi-timeframe trends over raw indicators
- **Sure Trend Detection**: Identifies trends with 80+ confidence score for high-probability trades
- **Adaptability**: Automatically switches to best trending market
- **Learning**: Improves ML model accuracy over time
- **Compounding**: Grows stake proportionally with profits

## 🛡️ Risk Management Features

1. **HARD 2-LOSS LIMIT**: After 2 consecutive losses, MUST pause trading (was 3)
2. **HARD GLOBAL 2-LOSS LIMIT**: After 2 losses across market switches, MUST pause (was 4)
3. **First Loss Protection**: After 1 loss, stake is reduced by 50% to prevent second loss from being bigger
4. **Sure Trend Override**: When trend confidence >= 80, thresholds are relaxed to capture strong trends
5. **Daily Loss Limit**: Stops trading if losses exceed MAX_DAILY_LOSS
6. **Drawdown Protection**: Stops if portfolio drawdown exceeds MAX_DRAWDOWN
7. **Profit Target**: Stops after reaching TAKE_PROFIT
8. **Trailing Stop**: Locks in profits at 30% below peak
9. **Market Health Check**: Refuses to trade in unfavorable markets (threshold raised to 70)
10. **Confidence Threshold**: Only trades with sufficient confidence (raised to 0.82)
11. **Trade Cooldown**: Minimum ticks between trades (raised to 100 for more analysis)
12. **Maximum Daily Trades**: Prevents over-trading (20/day)
13. **Martingale**: Optional with 1.5x multiplier, max 2 steps
14. **Adaptive Confidence**: Raises threshold after losses, lowers after wins

## 🔧 Latest Enhancements (v2.0)

### 1. Lower Timeframe Profitability
- **Contract duration reduced to 3 minutes** (was 5) for faster trading cycles
- **Added ultra_short timeframe** (10 ticks) for quick entry signals
- **5 timeframes now** (ultra_short, micro, lower, medium, higher) for multi-scale analysis
- **Faster candle formation** (3 ticks per candle) for more pattern detections in shorter windows

### 2. Pattern-First Trading (Not Just Indicators)
- **Decision engine rebalanced**: Trend 35% + Patterns 30% + ML 25% + Indicators 10%
- **Patterns now SECONDARY priority** (was tertiary), indicators are now last
- **Pattern confirmation bonus**: +12% confidence when patterns confirm trend direction
- **Sure trend override**: When trend confidence >= 80, can trade with just trend + 1 confirming signal
- **Multi-timeframe trend is PRIMARY** - all other signals must align with it

### 3. Hard 2-Loss Limit
- **MAX_CONSEC_LOSSES reduced to 2** (was 3) - hard stop after 2 consecutive losses
- **MAX_GLOBAL_CONSEC_LOSSES reduced to 2** (was 4) - prevents loss-chaining across markets
- **First loss protection**: After 1 loss, stake is cut by 50% to prevent second loss from being bigger
- **MIN_CONFIDENCE raised to 0.82** (was 0.78) - only trade with high conviction
- **MIN_MARKET_HEALTH raised to 70** (was 65) - only trade in healthy markets
- **TRADE_COOLDOWN raised to 100 ticks** (was 50) - more analysis between trades

### 4. Sure Trend Identification
- **Trend Confidence Scoring** (0-100): Combines alignment, R-squared, momentum consistency, and persistence
- **"Sure Trend" definition**: confidence >= 80 AND persistence >= 20 ticks
- **Sure trend override**: Relaxes confidence threshold by 0.05 and health requirement by 5
- **Sure trend stake bonus**: Up to 20% stake increase when trend is very strong
- **Sure trend confidence bonus**: +10-20% in decision engine calculations
- **Trend persistence tracking**: Monitors how long a trend has been consistent

### Previous Fixes & Improvements

#### Trading Logic Fixes
- **False Signal Filtering**: RSI extremes (>90 or <10) filtered as noise
- **Confidence Cap**: Hard cap at 0.85 (empirically proven: higher = worse)
- **BB Extreme Edge**: Only trade BB extreme continuations (55.7% edge)
- **Ranging Market Guard**: Require 2+ signal sources in ranging markets
- **Trend Disagreement Block**: Hard block when all signals conflict with trend
- **Single Source Guard**: Block single-source signals in non-trending markets

#### ML Improvements
- **Balanced Training**: Auto-balances UP/DOWN classes
- **Time-Series Validation**: 70/30 temporal split for honest accuracy
- **Accuracy Gate**: Only use ML when accuracy > 55%
- **Reduced Overfitting**: min_samples_leaf=10, max_depth=6
- **Live Validation**: Validates predictions against actual price movement

#### Risk Management Fixes
- **Global Consecutive Losses**: Tracks across market switches
- **Market Lock**: Won't switch markets with active contract
- **Trailing Stop**: Locks in profits
- **Adaptive Confidence**: Dynamic threshold based on win rate
- **Auto-Resume**: Learning system pauses auto-resume after 500 ticks

#### Connection & Stability Fixes
- **Tick Health Monitoring**: 30-second timeout with auto-resubscribe
- **Stuck Contract Cleanup**: Time-based and tick-based cleanup
- **Reconnection Logic**: Up to 10 attempts with progressive backoff
- **Multi-Symbol Tick Tracking**: Per-symbol counters and history

#### Pattern Detection Fixes
- **Percentage-Based Thresholds**: Works for any price level
- **Synthetic Index Optimizations**: Lower momentum thresholds
- **Candle Formation**: 3 ticks per candle for faster pattern detection

## 📝 Logging

Logs are saved to the `logs/` directory:
- `agent.log` - Main agent operations
- `trades.log` - Trade execution records
- `market_analysis.log` - Market analysis results
- `decisions.log` - Trading decisions

## 📁 File Structure

```
intelligent_trading_agent/
├── agent.py                    # Main agent orchestrator (1991 lines)
├── config.py                   # Configuration management (78 lines)
├── logger.py                   # Logging infrastructure (90 lines)
├── deriv_client.py             # Deriv API client (844 lines)
├── market_analyzer.py          # Market analysis (347 lines)
├── strategy_selector.py        # Strategy selection (183 lines)
├── decision_engine.py          # Ensemble decision engine (533 lines)
├── risk_manager.py             # Risk management (524 lines)
├── learning_system.py          # Learning & adaptation (313 lines)
├── ml_predictor.py             # ML prediction (638 lines)
├── reinforcement_learning.py   # RL system (743 lines)
├── multi_market_monitor.py     # Multi-market monitoring (334 lines)
├── terminal_ui.py              # Terminal dashboard
├── backtest_bot.py             # Backtesting (509 lines)
├── demo.py                     # Demo mode
├── enhanced_demo.py            # Enhanced demo
├── test_bot_intelligence.py    # Intelligence tests
├── run_agent.sh                # Startup script
├── requirements.txt            # Python dependencies
├── .env                        # Environment configuration
├── .env.example                # Environment template
├── features/
│   ├── __init__.py
│   ├── indicators.py           # Technical indicators (285 lines)
│   └── pattern_recognition.py  # Pattern recognition (770 lines)
├── strategies/
│   ├── __init__.py             # Base strategy + TradeSignal (71 lines)
│   ├── accumulator.py          # Accumulator strategy (91 lines)
│   ├── higher_lower.py         # Higher/Lower strategy (83 lines)
│   └── rise_fall.py            # Rise/Fall strategy (172 lines)
├── models/                     # Persisted models
│   ├── rf_model.pkl            # Random Forest model
│   ├── gb_model.pkl            # Gradient Boosting model
│   ├── scaler.pkl              # Feature scaler
│   ├── ml_metadata.pkl         # ML metadata
│   ├── rl_model.pkl            # RL model
│   ├── compounder_data.json    # Profit compounder data
│   ├── performance_metrics.json # Learning system data
│   └── session_agent_*.json    # Session data
├── logs/                       # Log files
│   ├── agent.log
│   ├── trades.log
│   ├── market_analysis.log
│   └── decisions.log
└── data/                       # Data directory
```

## ⚠️ Disclaimer

**Trading involves substantial risk.** This agent is for educational purposes.

- Test thoroughly on demo accounts first
- Only trade with money you can afford to lose
- Past performance doesn't guarantee future results
- The author is not responsible for losses

## 🔧 Troubleshooting

### Connection Issues
```bash
# Verify API token is valid
# Check internet connection
# Ensure app_id is correct (1089 for public, register new for trading)
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Model Issues
```bash
# Delete old models and retrain
rm models/*.pkl
python agent.py
```

### Bot Not Trading
- Check logs for pause reasons
- Verify market health > MIN_MARKET_HEALTH
- Check confidence > MIN_CONFIDENCE
- Ensure no active contracts blocking
- Verify Deriv connection and authorization

---

**Happy Trading! 🚀**