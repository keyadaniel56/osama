"""
Configuration and environment handling for the intelligent trading agent.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# === API Configuration ===
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1089")

# === Trading Configuration ===
BASE_STAKE = float(os.getenv("STAKE", "1.0"))
MIN_STAKE_AMOUNT = 0.35  # Deriv minimum stake
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", "10.0"))
STOP_LOSS = float(os.getenv("STOP_LOSS", "5.0"))

# Contract Duration Settings
CONTRACT_DURATION = int(os.getenv("CONTRACT_DURATION", "5"))  # Duration value
CONTRACT_DURATION_UNIT = os.getenv("CONTRACT_DURATION_UNIT", "m")  # s=seconds, m=minutes, h=hours, t=ticks

# Trade Management
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "1"))  # Max open trades at once (1 = strict sequential)

# === Risk Management ===
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "10.0"))
MAX_CONSEC_LOSSES = int(os.getenv("MAX_CONSEC_LOSSES", "3"))
MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", "20.0"))
USE_MARTINGALE = os.getenv("USE_MARTINGALE", "false").lower() == "true"

# Global consecutive losses across market switches (prevents loss-chaining through market hopping)
MAX_GLOBAL_CONSEC_LOSSES = int(os.getenv("MAX_GLOBAL_CONSEC_LOSSES", "4"))

# === Agent Decision Thresholds ===
MIN_CONFIDENCE = 0.65           # Minimum confidence to place a trade (balanced for quality)
HIGH_CONFIDENCE = 0.75          # High quality threshold
ULTRA_CONFIDENCE = 0.85         # Ultra high quality threshold
MIN_MARKET_HEALTH = 55          # Minimum market health score (0-100)
TRADE_COOLDOWN_TICKS = 50       # Minimum ticks between trades (reduced for more activity)

# === Feature Engineering ===
FEATURE_WINDOW = 30             # Window size for indicators
NUM_FEATURES = 50               # Number of technical features to extract

# === Model Configuration ===
RETRAIN_EVERY = 50              # Retrain model every N trades
MODEL_PERSISTENCE = True        # Save/load models
CONTINUOUS_LEARNING = True      # Learn from trades in real-time

# === Market Analysis ===
MARKET_STATE_WINDOW = 100       # Ticks to analyze for market state
VOLATILITY_THRESHOLD_HIGH = 0.75  # High volatility threshold
VOLATILITY_THRESHOLD_LOW = 0.25   # Low volatility threshold

# === Strategy Configuration ===
AVAILABLE_STRATEGIES = ["higher_lower", "accumulator", "rise_fall"]
STRATEGY_SWITCH_COOLDOWN = 10   # Ticks before switching strategies

# === Trading Symbols ===
AVAILABLE_SYMBOLS = ["R_100", "R_75", "R_50", "R_25", "R_10"]
DEFAULT_SYMBOL = os.getenv("SYMBOL", "R_100")

# === Logging ===
LOG_DIR = "logs"
LOG_LEVEL = "INFO"

# === Paths ===
MODELS_DIR = "models"
DATA_DIR = "data"

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)