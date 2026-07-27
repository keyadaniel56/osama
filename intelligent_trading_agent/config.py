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
CONTRACT_DURATION = int(os.getenv("CONTRACT_DURATION", "3"))  # LOWERED: 3 minute contracts for faster ticks
CONTRACT_DURATION_UNIT = os.getenv("CONTRACT_DURATION_UNIT", "m")  # s=seconds, m=minutes, h=hours, t=ticks

# Trade Management
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "1"))  # Max open trades at once (1 = strict sequential)

# === Risk Management ===
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "10.0"))
MAX_CONSEC_LOSSES = int(os.getenv("MAX_CONSEC_LOSSES", "2"))  # STRICT: max 2 consecutive losses, then pause
MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", "20.0"))
USE_MARTINGALE = os.getenv("USE_MARTINGALE", "false").lower() == "true"

# Martingale Configuration (user-controllable via .env)
MARTINGALE_MULTIPLIER = float(os.getenv("MARTINGALE_MULTIPLIER", "1.5"))  # Stake multiplier after each loss
MARTINGALE_MAX_STEPS = int(os.getenv("MARTINGALE_MAX_STEPS", "2"))  # Max steps before resetting

# Global consecutive losses across market switches (prevents loss-chaining through market hopping)
MAX_GLOBAL_CONSEC_LOSSES = int(os.getenv("MAX_GLOBAL_CONSEC_LOSSES", "2"))  # STRICT: max 2 losses across market switches

# === Agent Decision Thresholds ===
# These are read from .env if set, otherwise fall back to these defaults
# The .env values should take precedence
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.82"))           # RAISED: Minimum confidence to place a trade
HIGH_CONFIDENCE = float(os.getenv("HIGH_CONFIDENCE", "0.85"))         # High quality threshold
ULTRA_CONFIDENCE = float(os.getenv("ULTRA_CONFIDENCE", "0.92"))       # Ultra high quality threshold
MIN_MARKET_HEALTH = int(os.getenv("MIN_MARKET_HEALTH", "70"))         # RAISED: Minimum market health score (0-100)
TRADE_COOLDOWN_TICKS = int(os.getenv("TRADE_COOLDOWN_TICKS", "100"))  # RAISED: Minimum ticks between trades (more analysis)

# === Feature Engineering ===
FEATURE_WINDOW = int(os.getenv("FEATURE_WINDOW", "30"))
NUM_FEATURES = int(os.getenv("NUM_FEATURES", "50"))

# === Model Configuration ===
RETRAIN_EVERY = int(os.getenv("RETRAIN_EVERY", "50"))
MODEL_PERSISTENCE = os.getenv("MODEL_PERSISTENCE", "true").lower() == "true"
CONTINUOUS_LEARNING = os.getenv("CONTINUOUS_LEARNING", "true").lower() == "true"

# === Market Analysis ===
MARKET_STATE_WINDOW = int(os.getenv("MARKET_STATE_WINDOW", "100"))
VOLATILITY_THRESHOLD_HIGH = float(os.getenv("VOLATILITY_THRESHOLD_HIGH", "0.75"))
VOLATILITY_THRESHOLD_LOW = float(os.getenv("VOLATILITY_THRESHOLD_LOW", "0.25"))

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