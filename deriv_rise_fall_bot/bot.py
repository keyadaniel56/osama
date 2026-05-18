"""
Rise/Fall ML Trading Bot for Deriv.
Uses machine learning and technical analysis to predict price direction.
Trades with minute-based durations instead of ticks.
"""

import time
import threading
import os
import numpy as np
from collections import deque
from dotenv import load_dotenv

from deriv_client import DerivClient
from feature_engine import FeatureEngine, FEAT
from model import MLModel
from strategy import Strategy

load_dotenv()

# Configuration
API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
APP_ID = os.getenv("DERIV_APP_ID", "1089")
SYMBOL = os.getenv("SYMBOL", "R_100")
STAKE = float(os.getenv("STAKE", "1.0"))
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "1"))
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", "10.0"))
STOP_LOSS = float(os.getenv("STOP_LOSS", "5.0"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "10.0"))
MAX_CONSEC_LOSSES = int(os.getenv("MAX_CONSEC_LOSSES", "3"))

# Martingale configuration
ENABLE_MARTINGALE = os.getenv("ENABLE_MARTINGALE", "false").lower() == "true"
MARTINGALE_MULTIPLIER = float(os.getenv("MARTINGALE_MULTIPLIER", "2.0"))
MAX_MARTINGALE_STEPS = int(os.getenv("MAX_MARTINGALE_STEPS", "3"))

# Trading parameters
MIN_CONFIDENCE = 0.65  # Slightly higher for better quality
RETRAIN_EVERY = 50
TRADE_COOLDOWN_TICKS = 5  # Reduced from 10 to allow more trades


class Bot:
    def __init__(self):
        self.client = DerivClient(APP_ID, API_TOKEN, SYMBOL)
        self.features = FeatureEngine(window=50)
        self.model = MLModel()
        self.strategy = Strategy(
            base_stake=STAKE,
            enable_martingale=ENABLE_MARTINGALE,
            martingale_multiplier=MARTINGALE_MULTIPLIER,
            max_martingale_steps=MAX_MARTINGALE_STEPS
        )

        self.tick_count = 0
        self.samples_since_retrain = 0
        self.in_trade = False
        self.last_features = None
        self.last_prediction = None
        self.last_price = None
        self._trade_lock = threading.Lock()
        self._ticks_since_last_trade = 0
        self._paused = False

        self.client.on_tick = self._handle_tick
        self.client.on_contract_result = self._handle_result

    def run(self):
        print("=" * 60)
        print("🚀 Deriv Rise/Fall ML Trading Bot")
        print("=" * 60)
        
        self.client.connect()

        timeout = 15
        while not self.client.authorized and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5

        if not self.client.authorized:
            raise RuntimeError("Authorization failed. Check your API token.")

        print(f"🎯 Trading {SYMBOL} | Duration: {DURATION_MINUTES} minute(s)")
        print(f"💰 Stake: ${STAKE} | Take Profit: ${TAKE_PROFIT} | Stop Loss: ${STOP_LOSS}")
        if ENABLE_MARTINGALE:
            print(f"📈 Martingale: ENABLED | Multiplier: {MARTINGALE_MULTIPLIER}x | Max Steps: {MAX_MARTINGALE_STEPS}")
        else:
            print(f"📊 Martingale: DISABLED")
        print("=" * 60)
        
        try:
            while True:
                time.sleep(5)
                self._print_status()
        except KeyboardInterrupt:
            print("\n⚠️ Bot stopped by user")
            self._print_final_summary()

    def _print_status(self):
        """Print current status."""
        wins = sum(1 for t in self.strategy.trade_history if t["result"] == "win")
        losses = len(self.strategy.trade_history) - wins
        win_rate = (wins / len(self.strategy.trade_history) * 100) if self.strategy.trade_history else 0
        
        martingale_info = ""
        if ENABLE_MARTINGALE and self.strategy.martingale_step > 0:
            martingale_info = f" | 📈 Martingale: Step {self.strategy.martingale_step}/{MAX_MARTINGALE_STEPS}"
        
        print(f"\n📊 Status | Trades: {len(self.strategy.trade_history)} | "
              f"W/L: {wins}/{losses} | Win Rate: {win_rate:.1f}% | "
              f"P&L: ${self.strategy.total_profit:.2f}{martingale_info}")

    def _print_final_summary(self):
        """Print final summary."""
        print("\n" + "=" * 60)
        print("📈 TRADING SESSION SUMMARY")
        print("=" * 60)
        print(self.strategy.summary())
        print("=" * 60)

    def _handle_tick(self, price: float):
        self.tick_count += 1
        self.features.add_tick(price)
        self.last_price = price

        if self.tick_count % 10 == 0 and not self.features.ready():
            print(f"📥 Collecting data: {self.tick_count}/{self.features.window} ticks")

        # Pause management
        if self._paused and hasattr(self, '_pause_ticks_remaining'):
            self._pause_ticks_remaining -= 1
            if self._pause_ticks_remaining <= 0:
                self._paused = False
                self.strategy.consecutive_losses = 0
                del self._pause_ticks_remaining
                print("▶️ Resuming trading")

        feat = self.features.extract()
        if feat is None:
            return

        # Risk management checks
        if self._paused:
            return

        if self.strategy.total_profit >= TAKE_PROFIT:
            print(f"🎉 TAKE PROFIT REACHED! ${self.strategy.total_profit:.2f}")
            self._paused = True
            self._pause_ticks_remaining = 999999
            return

        if self.strategy.total_profit <= -STOP_LOSS:
            print(f"🛑 STOP LOSS TRIGGERED! ${self.strategy.total_profit:.2f}")
            self._paused = True
            self._pause_ticks_remaining = 999999
            return

        if self.strategy.total_profit <= -MAX_DAILY_LOSS:
            print(f"🛑 Daily loss limit reached: ${MAX_DAILY_LOSS}")
            self._paused = True
            self._pause_ticks_remaining = 999999
            return

        if self.strategy.consecutive_losses >= MAX_CONSEC_LOSSES:
            print(f"⏸️ Pausing after {MAX_CONSEC_LOSSES} consecutive losses")
            self._paused = True
            self._pause_ticks_remaining = 30
            return

        with self._trade_lock:
            if self.in_trade:
                return

        # Cooldown
        self._ticks_since_last_trade += 1
        if self._ticks_since_last_trade < TRADE_COOLDOWN_TICKS:
            return

        # Skip high entropy markets
        if self._is_high_entropy(feat):
            if self.tick_count % 20 == 0:
                print("⏭️ Skipping - high entropy market")
            return

        # Get prediction
        prediction, confidence, source = self._decide(feat)

        if prediction == -1:
            if self.tick_count % 30 == 0:
                print("⏭️ No signal")
            return

        # Dynamic confidence check
        required_confidence = self.strategy.get_dynamic_confidence()
        if confidence < required_confidence:
            if self.tick_count % 20 == 0:
                print(f"⏭️ Low confidence: {confidence:.2f} < {required_confidence:.2f}")
            return

        # Quality check
        if not self._is_high_quality_signal(feat, prediction, confidence):
            if self.tick_count % 20 == 0:
                print("⏭️ Signal quality check failed")
            return

        contract_type = self.strategy.get_contract_type(prediction)
        direction = "RISE" if prediction == 1 else "FALL"

        self.last_features = feat
        self.last_prediction = prediction

        with self._trade_lock:
            self.in_trade = True
        self._ticks_since_last_trade = 0

        martingale_info = ""
        if ENABLE_MARTINGALE and self.strategy.martingale_step > 0:
            martingale_info = f" | 📈 Martingale Step {self.strategy.martingale_step}/{MAX_MARTINGALE_STEPS}"

        print(f"\n🎯 TRADE | {direction} | Confidence: {confidence:.2f} | "
              f"Source: {source} | Stake: ${self.strategy.stake:.2f}{martingale_info}")
        
        self.client.buy_contract(contract_type, self.strategy.stake, DURATION_MINUTES)

    def _handle_result(self, status: str, profit: float):
        with self._trade_lock:
            self.in_trade = False

        won = profit > 0
        
        if won:
            self.strategy.on_win(abs(profit))
        else:
            self.strategy.on_loss(abs(profit))
            # Pause briefly after loss
            self._paused = True
            self._pause_ticks_remaining = 15
            print("⏸️ Pausing 15 ticks after loss")

        # Label outcome for training
        if self.last_features is not None and self.last_prediction is not None:
            # For Rise/Fall: outcome = 1 if RISE won, 0 if FALL won
            if self.last_prediction == 1:  # Predicted RISE
                actual_outcome = 1 if won else 0
            else:  # Predicted FALL
                actual_outcome = 0 if won else 1
            
            self.model.add_sample(self.last_features, actual_outcome)
            self.samples_since_retrain += 1

        # Retrain periodically
        if self.samples_since_retrain >= RETRAIN_EVERY:
            print("🔄 Retraining model...")
            if self.model.train():
                print(f"✅ Model retrained. CV accuracy: {self.model.cv_accuracy:.3f}")
            self.samples_since_retrain = 0

        self.last_features = None
        self.last_prediction = None

    def _decide(self, feat: np.ndarray) -> tuple[int, float, str]:
        """
        Returns (prediction, confidence, source).
        1 = RISE, 0 = FALL, -1 = no prediction
        """
        prediction, confidence = self.model.predict(feat)
        if prediction != -1:
            return prediction, confidence, "ml"

        prediction, confidence = self._heuristic_predict(feat)
        return prediction, confidence, "heuristic"

    def _is_high_entropy(self, feat: np.ndarray) -> bool:
        """Check if market is too random."""
        entropy = feat[FEAT["entropy"]]
        return entropy >= 0.98  # Relaxed from 0.95 to allow more trades

    def _is_high_quality_signal(self, feat: np.ndarray, prediction: int, confidence: float) -> bool:
        """Signal quality gate."""
        if confidence < 0.65:  # Raised from 0.60
            return False

        momentum = feat[FEAT["short_mom"]]
        rsi = feat[FEAT["rsi"]]

        # For medium confidence, require momentum alignment
        if confidence < 0.75:
            if prediction == 1 and momentum < -0.00001:
                return False
            if prediction == 0 and momentum > 0.00001:
                return False

        # Additional quality check: avoid extreme RSI with opposite prediction
        if prediction == 1 and rsi > 0.85:  # Don't buy when extremely overbought
            return False
        if prediction == 0 and rsi < 0.15:  # Don't sell when extremely oversold
            return False

        return True

    def _heuristic_predict(self, feat: np.ndarray) -> tuple[int, float]:
        """
        Improved heuristic prediction using technical indicators.
        """
        momentum = feat[FEAT["short_mom"]]
        med_mom = feat[FEAT["med_mom"]]
        mean_rev = feat[FEAT["mean_rev"]]
        imbalance = feat[FEAT["imbalance"]]
        rsi = feat[FEAT["rsi"]]
        bb_pos = feat[FEAT["bb_pos"]]
        trend = feat[FEAT["trend"]]

        votes = []

        # Strong momentum signal (increased weight)
        if abs(momentum) > 5e-6:  # Stronger threshold
            votes.append((1 if momentum > 0 else 0, 0.40))
        elif abs(momentum) > 3e-6:
            votes.append((1 if momentum > 0 else 0, 0.25))

        # Medium-term momentum confirmation
        if abs(med_mom) > 4e-6:
            votes.append((1 if med_mom > 0 else 0, 0.30))

        # Mean reversion (only strong signals)
        if abs(mean_rev) > 1.2:  # Stronger threshold
            votes.append((0 if mean_rev > 0 else 1, 0.35))

        # Imbalance
        if abs(imbalance) > 0.20:  # Stronger threshold
            votes.append((1 if imbalance > 0 else 0, 0.30))

        # RSI extremes (more conservative)
        if rsi > 0.75:
            votes.append((0, 0.30))  # Overbought - expect fall
        elif rsi < 0.25:
            votes.append((1, 0.30))  # Oversold - expect rise

        # Bollinger Bands extremes
        if bb_pos > 0.85:  # More extreme threshold
            votes.append((0, 0.25))  # Near upper band - expect fall
        elif bb_pos < 0.15:
            votes.append((1, 0.25))  # Near lower band - expect rise

        # Trend (only strong trends)
        if abs(trend) > 0.4:  # Stronger threshold
            votes.append((1 if trend > 0 else 0, 0.30))

        # Require at least 2 indicators agreeing
        if len(votes) < 2:
            return -1, 0.0

        rise_score = sum(w for p, w in votes if p == 1)
        fall_score = sum(w for p, w in votes if p == 0)
        total = rise_score + fall_score

        # Require stronger consensus
        if rise_score > fall_score:
            confidence = rise_score / total
            if confidence >= 0.68:  # Higher threshold
                return 1, confidence
        else:
            confidence = fall_score / total
            if confidence >= 0.68:  # Higher threshold
                return 0, confidence

        return -1, 0.0


if __name__ == "__main__":
    bot = Bot()
    bot.run()
