"""
Main bot orchestrator.
Ties together: tick feed → feature extraction → ML prediction → strategy → trade execution.

Thinking improvements:
- Correct outcome-based labeling (actual result, not inverted wrong guess)
- Heuristic uses named feature indices (no magic numbers)
- Digit-aware signals: last digit bias, streak, entropy
- Model falls back to heuristic when CV accuracy is near chance
- Regime detection: high-entropy (random) vs trending vs mean-reverting
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
from strategy import Strategy, TradingPhase, TradeType
from hidden_markov_chain import HiddenMarkovChain
from theme import *

load_dotenv()

# --- Config ---
API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
APP_ID    = os.getenv("DERIV_APP_ID", "1089")
SYMBOL    = os.getenv("SYMBOL", "R_100")
STAKE     = float(os.getenv("STAKE", "1.0"))
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", "10.0"))
STOP_LOSS = float(os.getenv("STOP_LOSS", "5.0"))

# Multi-symbol support for better opportunities
AVAILABLE_SYMBOLS = ["R_100", "R_75", "R_50", "R_25", "R_10"]
SYMBOL_SWITCH_THRESHOLD = 15  # Reduced - switch symbols faster to find opportunities

# Enhanced confidence thresholds for better win rate
MIN_CONFIDENCE      = 0.60  # Reduced from 0.65 to allow more trades
HIGH_CONFIDENCE     = 0.75  # Keep high quality threshold
ULTRA_CONFIDENCE    = 0.85  # Keep ultra quality threshold
RETRAIN_EVERY       = 50
TRADE_COOLDOWN_TICKS = 6    # Reduced from 8 for more opportunities
MAX_DAILY_LOSS      = float(os.getenv("MAX_DAILY_LOSS", "10.0"))
MAX_CONSEC_LOSSES   = int(os.getenv("MAX_CONSEC_LOSSES", "2"))


class Bot:
    def __init__(self):
        self.current_symbol = SYMBOL
        self.client   = DerivClient(APP_ID, API_TOKEN, self.current_symbol)
        self.features = FeatureEngine(window=30)  # Reduced from 50 for faster startup
        self.model    = MLModel()
        self.strategy = Strategy(base_stake=STAKE)

        self.hmc = HiddenMarkovChain(history_length=20, min_confidence=MIN_CONFIDENCE)

        self.tick_count              = 0
        self.samples_since_retrain   = 0
        self.in_trade                = False
        self.last_features           = None
        self.last_prediction         = None
        self.last_contract_type      = None   # track what we actually bought
        self._trade_lock             = threading.Lock()
        self._ticks_since_last_trade = 0
        self._trade_timeout_ticks    = 0
        self._paused                 = False
        
        # Enhanced loss prevention
        self._recent_losses          = deque(maxlen=10)  # Track recent performance
        self._dynamic_confidence     = MIN_CONFIDENCE
        self._signal_confirmation    = deque(maxlen=3)   # Track signal consistency
        self._last_market_state      = None              # Track market regime changes
        
        # Multi-symbol and market adaptation
        self._ticks_without_trade    = 0                 # Track ticks without good trades
        self._symbol_index           = 0                 # Current symbol index
        self._market_bias            = None              # Current market bias (OVER/UNDER)
        self._bias_confidence        = 0.0               # Confidence in market bias

        self.client.on_tick            = self._handle_tick
        self.client.on_contract_result = self._handle_result

    def run(self):
        print_banner()
        print(f"{get_timestamp()} {Emojis.ROCKET} {colored_text('Starting Deriv ML Bot...', Colors.BRIGHT_YELLOW, Colors.BOLD)}")
        
        self.client.connect()

        timeout = 15
        while not self.client.authorized and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5

        if not self.client.authorized:
            print_connection_status("error")
            raise RuntimeError("Authorization failed. Check your API token.")

        print(f"{get_timestamp()} {colored_text('🎯 Trading session started', Colors.BRIGHT_GREEN, Colors.BOLD)} on {colored_text(self.current_symbol, Colors.BRIGHT_CYAN, Colors.BOLD)}")
        
        try:
            while True:
                time.sleep(5)
                # Use themed status display
                self._print_status()
        except KeyboardInterrupt:
            print(f"\n{get_timestamp()} {Emojis.WARNING} {colored_text('Bot stopped by user', Colors.BRIGHT_YELLOW, Colors.BOLD)}")
            self._print_final_summary()

    def _print_status(self):
        """Print themed status information"""
        wins = sum(1 for t in self.strategy.trade_history if t["result"] == "win")
        losses = len(self.strategy.trade_history) - wins
        win_rate = (wins / len(self.strategy.trade_history) * 100) if self.strategy.trade_history else 0
        
        # Format phase info
        phase_info = format_phase(
            self.strategy.phase.value,
            self.strategy.over_trades_completed,
            self.strategy.get_current_target(),
            self.strategy.under_trades_completed,
            self.strategy.get_current_target()
        )
        
        # Format P&L
        pnl_formatted = format_profit(self.strategy.total_profit)
        
        # Format win rate
        wr_formatted = format_win_rate(win_rate)
        
        # Format stake (check if in recovery for martingale indicator)
        is_martingale = self.strategy.phase == TradingPhase.RECOVERY
        stake_formatted = format_stake(self.strategy.current_stake, is_martingale)
        
        print(f"""
{get_timestamp()} {phase_info}
├─ Trades: {colored_text(str(len(self.strategy.trade_history)), Colors.WHITE)} | W/L: {colored_text(f'{wins}', Colors.GREEN)}/{colored_text(f'{losses}', Colors.RED)} | Win Rate: {wr_formatted}
├─ Stake: {stake_formatted} | P&L: {pnl_formatted}
└─ Symbol: {colored_text(self.current_symbol, Colors.BRIGHT_CYAN)}
""")

    def _print_final_summary(self):
        """Print final themed summary"""
        wins = sum(1 for t in self.strategy.trade_history if t["result"] == "win")
        losses = len(self.strategy.trade_history) - wins
        win_rate = (wins / len(self.strategy.trade_history) * 100) if self.strategy.trade_history else 0
        
        print(f"""
{Colors.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════╗
║                      {Colors.WHITE}{Colors.BOLD}TRADING SESSION SUMMARY{Colors.RESET}{Colors.BRIGHT_CYAN}                     ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}

{Emojis.CHART} {colored_text('Total Trades:', Colors.WHITE, Colors.BOLD)} {colored_text(str(len(self.strategy.trade_history)), Colors.BRIGHT_CYAN)}
{Emojis.WIN} {colored_text('Wins:', Colors.WHITE, Colors.BOLD)} {colored_text(str(wins), Colors.BRIGHT_GREEN)}
{Emojis.LOSS} {colored_text('Losses:', Colors.WHITE, Colors.BOLD)} {colored_text(str(losses), Colors.BRIGHT_RED)}
{Emojis.STAR} {colored_text('Win Rate:', Colors.WHITE, Colors.BOLD)} {format_win_rate(win_rate)}
{Emojis.MONEY} {colored_text('Final P&L:', Colors.WHITE, Colors.BOLD)} {format_profit(self.strategy.total_profit)}
{Emojis.DIAMOND} {colored_text('Final Phase:', Colors.WHITE, Colors.BOLD)} {colored_text(self.strategy.phase.value.upper(), Colors.BRIGHT_MAGENTA)}

{colored_text('Thank you for using Deriv ML Bot! 🚀', Colors.BRIGHT_YELLOW, Colors.BOLD)}
""")

    def _handle_tick(self, price: float):
        self.tick_count += 1
        self.features.add_tick(price)

        if self.tick_count % 10 == 0 and not self.features.ready():
            print_collecting_ticks(self.tick_count, self.features.window)

        # Consecutive-loss pause countdown
        if self._paused and hasattr(self, '_pause_ticks_remaining'):
            self._pause_ticks_remaining -= 1
            if self._pause_ticks_remaining <= 0:
                self._paused = False
                
                # Don't reset consecutive_losses or stake in recovery mode (preserve martingale)
                if self.strategy.phase != TradingPhase.RECOVERY:
                    self.strategy.consecutive_losses = 0
                    self.strategy.current_stake = self.strategy.base_stake
                    print(f"[Bot] Pause over. Resuming with reset stake ${self.strategy.base_stake:.2f}.")
                else:
                    # In recovery mode, preserve both consecutive_losses and current_stake
                    print(f"[Bot] Pause over. Resuming in RECOVERY mode with martingale stake ${self.strategy.current_stake:.2f} (multiplier: {self.strategy.recovery_stake_multiplier}x).")
                    
                del self._pause_ticks_remaining

        feat = self.features.extract()
        if feat is None:
            return

        # Risk management
        if self._paused:
            return
            
        # Take Profit check
        if self.strategy.total_profit >= TAKE_PROFIT:
            print(f"🎉 TAKE PROFIT REACHED! Profit: ${self.strategy.total_profit:.2f} (Target: ${TAKE_PROFIT:.2f})")
            print(f"🛑 Trading stopped. Congratulations on reaching your profit target!")
            self._paused = True
            self._pause_ticks_remaining = 999999  # Pause indefinitely
            return
            
        # Stop Loss check
        if self.strategy.total_profit <= -STOP_LOSS:
            print(f"🛑 STOP LOSS TRIGGERED! Loss: ${self.strategy.total_profit:.2f} (Limit: -${STOP_LOSS:.2f})")
            print(f"⚠️ Trading stopped to prevent further losses.")
            self._paused = True
            self._pause_ticks_remaining = 999999  # Pause indefinitely
            return
            
        # Daily loss limit (existing logic)
        if self.strategy.total_profit <= -MAX_DAILY_LOSS:
            print(f"[Bot] Daily loss limit reached (${MAX_DAILY_LOSS:.2f}). Trading stopped.")
            self._paused = True
            self._pause_ticks_remaining = 999999
            return

        if self.strategy.consecutive_losses >= MAX_CONSEC_LOSSES and self.strategy.phase != TradingPhase.RECOVERY:
            print(f"[Bot] {self.strategy.consecutive_losses} consecutive losses. Pausing 30 ticks.")
            self._paused = True
            self._pause_ticks_remaining = 30
            return
        elif self.strategy.consecutive_losses >= MAX_CONSEC_LOSSES and self.strategy.phase == TradingPhase.RECOVERY:
            # In recovery mode, don't pause for consecutive losses - let martingale handle it
            if self.tick_count % 50 == 0:  # Log occasionally to avoid spam
                print(f"[Bot] {self.strategy.consecutive_losses} consecutive losses in RECOVERY mode - continuing with martingale strategy.")
            pass

        # Check if market reanalysis is needed after phase switch
        if self.strategy.needs_market_reanalysis:
            print("[Bot] Re-analyzing market after phase switch...")

            # Only clear the feature buffer when entering RECOVERY — preserve data on normal resets
            if self.strategy.phase == TradingPhase.RECOVERY:
                if hasattr(self.features, 'ticks') and len(self.features.ticks) > 30:
                    recent_ticks = list(self.features.ticks)[-30:]
                    self.features.ticks.clear()
                    for tick in recent_ticks:
                        self.features.ticks.append(tick)
                    print("[Bot] Cleared feature buffer for recovery re-analysis.")

            # Try forced reanalysis first, then fall back to regular training
            if self.model.force_reanalysis():
                print(f"[Bot] Market re-analysis complete. CV accuracy: {self.model.cv_accuracy:.3f}")
            elif self.model.train():
                print(f"[Bot] Market re-analysis via regular training. CV accuracy: {self.model.cv_accuracy:.3f}")
            else:
                print("[Bot] Market re-analysis: Insufficient data, will rely on heuristic predictions.")

            self.strategy.needs_market_reanalysis = False

        with self._trade_lock:
            if self.in_trade:
                self._trade_timeout_ticks += 1
                if self._trade_timeout_ticks > 20:
                    print("[Bot] WARNING: Trade result never received. Force-resetting trade lock.")
                    self.in_trade = False
                    self._trade_timeout_ticks = 0
                    self.last_features = None
                    self.last_prediction = None
                    self.last_contract_type = None
                return

        # Use standard cooldown and confidence
        min_confidence = MIN_CONFIDENCE
        cooldown = TRADE_COOLDOWN_TICKS

        self._ticks_since_last_trade += 1
        if self._ticks_since_last_trade < cooldown:
            return

        # Track ticks without good trades for symbol switching
        self._ticks_without_trade += 1

        # Check if we should switch symbols due to lack of opportunities
        if self._ticks_without_trade >= SYMBOL_SWITCH_THRESHOLD:
            if self._try_switch_symbol():
                return  # Symbol switched, wait for new data

        # --- Regime check: skip if market is too random ---
        if self._is_high_entropy(feat):
            if self.tick_count % 20 == 0:
                print(f"[Bot] Skipping — high entropy (ret={feat[FEAT['entropy']]:.2f}, digit={feat[FEAT['digit_entropy']]:.2f})")
            return

        # --- HMC regime check: skip if HMC detects unfavorable state ---
        # Bypass HMC in recovery mode — recovery needs to trade to recover losses
        if self.strategy.phase != TradingPhase.RECOVERY:
            hmc_skip, hmc_reason = self.hmc.should_skip_trade()
            if hmc_skip:
                if self.tick_count % 20 == 0:
                    print(f"[Bot] HMC skip — {hmc_reason}")
                return

        # Analyze current market bias
        self._analyze_market_bias(feat)

        prediction, confidence, source = self._decide(feat)

        # --- HMC direction override: if ML/heuristic has no signal, try HMC ---
        if prediction == -1:
            hmc_pred, hmc_conf, hmc_state = self.hmc.predict()
            if hmc_pred != -1:
                prediction, confidence, source = hmc_pred, hmc_conf, f"hmc:{hmc_state}"
                if self.tick_count % 10 == 0:
                    print(f"[Bot] HMC signal: pred={prediction} conf={confidence:.2f} state={hmc_state}")

        # Debug logging to see what's happening
        if self.tick_count % 5 == 0:  # More frequent logging
            print(f"[Bot] Debug - Prediction: {prediction}, Confidence: {confidence:.3f}, Source: {source}")
            if prediction != -1:
                print(f"[Bot] Signal found: {prediction} conf:{confidence:.2f} src:{source} bias:{self._market_bias or 'None'}({self._bias_confidence:.2f})")
            else:
                print(f"[Bot] No signal from {source} - checking why...")
                # Try to get more details about why no signal
                if source == "ml":
                    print(f"[Bot] ML model returned no prediction")
                else:
                    print(f"[Bot] Heuristic returned no prediction - insufficient consensus")

        if prediction == -1:
            if self.tick_count % 20 == 0:
                print("[Bot] Skipping — no signal")
            return

        # Debug: Show signal details periodically
        if self.tick_count % 30 == 0:
            print(f"[Bot] Signal found: {prediction} conf:{confidence:.2f} src:{source} bias:{self._market_bias or 'None'}({self._bias_confidence:.2f})")

        # INTELLIGENT MARKET ADAPTATION: 
        # If we need a specific trade type but market favors the opposite, adapt!
        adapted_prediction = self._adapt_to_market_conditions(prediction, confidence)
        if adapted_prediction != prediction:
            print(f"[Bot] Market adaptation: Changed {prediction} to {adapted_prediction} based on market bias")
            prediction = adapted_prediction

        # Signal confirmation system - require consistent signals (temporarily relaxed)
        # if not self._confirm_signal_consistency(prediction, confidence):
        #     if self.tick_count % 30 == 0:  # Reduced logging frequency
        #         print("[Bot] Skipping — signal not confirmed by consistency check")
        #     return

        # Dynamic confidence adjustment based on recent performance
        required_confidence = self._get_dynamic_confidence()
        
        print(f"[Bot] Confidence check: signal={confidence:.3f}, required={required_confidence:.3f}")
        
        if confidence < required_confidence:
            if self.tick_count % 20 == 0:
                print(f"[Bot] Skipping — low confidence {confidence:.2f} < {required_confidence:.2f} ({source})")
            return

        # Additional signal quality check
        quality_ok = self._is_high_quality_signal(feat, prediction, confidence)
        print(f"[Bot] Quality check: {quality_ok}")
        
        if not quality_ok:
            if self.tick_count % 20 == 0:
                print(f"[Bot] Skipping — signal quality check failed (pred:{prediction}, conf:{confidence:.3f})")
            return

        # Final safety check (optional - can be disabled for more trades)
        # if not self._final_safety_check(feat, prediction, confidence):
        #     print(f"[Bot] Skipping — final safety check failed")
        #     return

        # Check if we should trade this prediction type based on current phase targets
        if not self.strategy.should_trade_type(prediction):
            target = self.strategy.get_current_target()
            trade_type = "OVER" if prediction == 1 else "UNDER"
            completed = self.strategy.over_trades_completed if prediction == 1 else self.strategy.under_trades_completed
            if self.tick_count % 20 == 0:
                print(f"[Bot] Skipping {trade_type} — target reached ({completed}/{target})")
            return

        # Reset ticks without trade counter since we found a good trade
        self._ticks_without_trade = 0

        contract_type = self.strategy.get_contract_type(prediction)

        # Record the trade attempt
        self.strategy.record_trade_attempt(prediction)

        self.last_features      = feat
        self.last_prediction    = prediction
        self.last_contract_type = contract_type

        with self._trade_lock:
            self.in_trade = True
            self._trade_timeout_ticks = 0
        self._ticks_since_last_trade = 0

        # Execute the trade with themed output
        is_martingale = self.strategy.phase == TradingPhase.RECOVERY
        print_trade_execution(contract_type, self.strategy.stake, confidence, source, self.strategy.phase.value, is_martingale)
        self.client.buy_contract(contract_type, self.strategy.stake)

    def _final_safety_check(self, feat: np.ndarray, prediction: int, confidence: float) -> bool:
        """
        Ultra-conservative final check before placing trade.
        Re-enabled with enhanced logic for better win rate.
        """
        # For very high confidence signals, add extra scrutiny
        if confidence >= 0.95:
            # Check if market conditions support such high confidence
            momentum = feat[FEAT["short_mom"]]
            imbalance = feat[FEAT["imbalance"]]
            digit_bias = feat[FEAT["digit_bias"]]
            
            # Verify that multiple strong signals support this confidence
            strong_signals = 0
            
            if prediction == 1:  # OVER
                if momentum > 0.000003:  # Very strong momentum up
                    strong_signals += 1
                if imbalance > 0.15:  # Strong upward imbalance
                    strong_signals += 1
                if digit_bias > 0.7:  # Very strong high digit bias
                    strong_signals += 1
            else:  # UNDER
                if momentum < -0.000003:  # Very strong momentum down
                    strong_signals += 1
                if imbalance < -0.15:  # Strong downward imbalance
                    strong_signals += 1
                if digit_bias < 0.3:  # Very strong low digit bias
                    strong_signals += 1
                    
            # For 95%+ confidence, require at least 2 very strong supporting signals
            if strong_signals < 2:
                return False
        
        # Additional check for 100% confidence signals - require perfect alignment
        if confidence >= 1.0:
            momentum = feat[FEAT["short_mom"]]
            imbalance = feat[FEAT["imbalance"]]
            digit_bias = feat[FEAT["digit_bias"]]
            
            if prediction == 1:  # OVER
                # All indicators must strongly support OVER
                if momentum <= 0 or imbalance <= 0.1 or digit_bias <= 0.6:
                    return False
            else:  # UNDER
                # All indicators must strongly support UNDER
                if momentum >= 0 or imbalance >= -0.1 or digit_bias >= 0.4:
                    return False
                    
        # Additional check: avoid trading during transition periods
        streak = feat[FEAT["streak"]]
        if streak > 0.25:  # Very long streak might be ending
            return False
            
        return True
        self.client.buy_contract(contract_type, self.strategy.stake)

    def _handle_result(self, status: str, profit: float):
        with self._trade_lock:
            self.in_trade = False
            self._trade_timeout_ticks = 0

        won = profit > 0
        result_text = "WIN" if won else "LOSS"
        print(f"{get_timestamp()} {format_trade_result(result_text, profit)}")

        # Track recent performance for dynamic confidence adjustment
        self._recent_losses.append(not won)
        self._update_dynamic_confidence()

        # Update HMC with trade outcome
        trade_type = "OVER" if (self.last_contract_type or "").startswith("DIGITOVER") else "UNDER"
        self.hmc.update(won, trade_type)
        print(f"{get_timestamp()} [HMC] {self.hmc.get_state_summary()}")
        self.hmc.save_state()

        # After a loss, pause briefly — but not in recovery (martingale needs to continue)
        if not won and self.strategy.phase != TradingPhase.RECOVERY:
            self._paused = True
            self._pause_ticks_remaining = 15
            print(f"{get_timestamp()} {Emojis.WARNING} {colored_text('Pausing 15 ticks after loss to reassess market conditions', Colors.YELLOW)}")

        # --- Correct labeling: use ACTUAL outcome, not inverted wrong guess ---
        if self.last_features is not None and self.last_contract_type is not None:
            actual_outcome = self._outcome_from_result(won, self.last_contract_type)
            self.model.add_sample(self.last_features, actual_outcome)
            self.samples_since_retrain += 1

        if won:
            self.strategy.on_win(abs(profit))
        else:
            self.strategy.on_loss(abs(profit))

        if self.samples_since_retrain >= RETRAIN_EVERY:
            print(f"{get_timestamp()} {Emojis.INFO} {colored_text('Retraining model...', Colors.CYAN)}")
            if self.model.train():
                print(f"{get_timestamp()} {Emojis.SUCCESS} {colored_text('Model retrained. CV accuracy:', Colors.GREEN)} {colored_text(f'{self.model.cv_accuracy:.3f}', Colors.BRIGHT_GREEN, Colors.BOLD)}")
            self.samples_since_retrain = 0

        self.last_features      = None
        self.last_prediction    = None
        self.last_contract_type = None

    def _outcome_from_result(self, won: bool, contract_type: str) -> int:
        """
        Derive the actual digit outcome from the contract result.
        DIGITOVER won  → last digit was HIGH (1)
        DIGITOVER lost → last digit was LOW  (0)
        DIGITUNDER won  → last digit was LOW  (0)
        DIGITUNDER lost → last digit was HIGH (1)
        """
        is_over = contract_type.startswith("DIGITOVER")
        if is_over:
            return 1 if won else 0
        else:
            return 0 if won else 1

    def _decide(self, feat: np.ndarray) -> tuple[int, float, str]:
        """
        Returns (prediction, confidence, source).
        Tries ML first; falls back to heuristic if model isn't ready or not beating chance.
        """
        prediction, confidence = self.model.predict(feat)
        if prediction != -1:
            return prediction, confidence, "ml"

        prediction, confidence = self._heuristic_predict(feat)
        return prediction, confidence, "heuristic"

    def _is_high_entropy(self, feat: np.ndarray) -> bool:
        """
        Much more permissive entropy detection to allow trading opportunities.
        Only block when both entropy measures are extremely high.
        """
        entropy       = feat[FEAT["entropy"]]
        digit_entropy = feat[FEAT["digit_entropy"]]
        # Very permissive thresholds - only block extreme randomness
        return entropy >= 1.0 and digit_entropy > 3.5  # Both must be at maximum levels

    def _is_unfavorable_market(self, feat: np.ndarray) -> bool:
        """
        Improved market condition checks to avoid trading in poor conditions.
        """
        # Check for high volatility
        vol_short = feat[FEAT["vol_short"]]
        vol_std = feat[FEAT["vol_std"]]
        
        # Skip during high volatility periods
        if vol_short > 0.002 or vol_std > 0.001:  # Stricter thresholds
            return True
            
        # Check for conflicting signals
        momentum = feat[FEAT["short_mom"]]
        mean_rev = feat[FEAT["mean_rev"]]
        
        # Skip when momentum and mean reversion strongly conflict
        if abs(momentum) > 0.0002 and abs(mean_rev) > 1.5:  # Lower thresholds
            if (momentum > 0 and mean_rev > 0) or (momentum < 0 and mean_rev < 0):
                return True
        
        # Check for low entropy (too predictable/random)
        entropy = feat[FEAT["entropy"]]
        if entropy < 0.3 or entropy > 0.95:  # Avoid extreme entropy
            return True
            
        # Check for extreme autocorrelation (market too choppy)
        ac_lag1 = feat[FEAT["ac_lag1"]]
        if abs(ac_lag1) > 0.8:  # Very high autocorrelation
            return True
                
        return False

    def _get_dynamic_confidence(self) -> float:
        """
        Adaptive confidence adjustment based on recent performance.
        Increases requirements after losses to improve quality.
        """
        if len(self._recent_losses) < 3:
            return MIN_CONFIDENCE
            
        recent_loss_rate = sum(self._recent_losses) / len(self._recent_losses)
        
        # Adaptive confidence based on performance
        if recent_loss_rate > 0.6:  # More than 60% losses recently
            return ULTRA_CONFIDENCE   # Require 85% confidence
        elif recent_loss_rate > 0.4:  # More than 40% losses recently
            return HIGH_CONFIDENCE    # Require 75% confidence
        elif recent_loss_rate > 0.2:  # More than 20% losses recently
            return MIN_CONFIDENCE + 0.05  # Require 70% confidence
        else:
            return MIN_CONFIDENCE + 0.05  # Floor at 65% even when winning

    def _detect_market_regime_change(self, feat: np.ndarray) -> bool:
        """
        Detect sudden changes in market behavior that could invalidate signals.
        """
        current_state = {
            'volatility': feat[FEAT["vol_short"]],
            'momentum': feat[FEAT["short_mom"]],
            'entropy': feat[FEAT["entropy"]],
            'hurst': feat[FEAT["hurst"]]
        }
        
        if self._last_market_state is None:
            self._last_market_state = current_state
            return False
            
        # Check for significant changes in market characteristics
        vol_change = abs(current_state['volatility'] - self._last_market_state['volatility'])
        momentum_change = abs(current_state['momentum'] - self._last_market_state['momentum'])
        entropy_change = abs(current_state['entropy'] - self._last_market_state['entropy'])
        hurst_change = abs(current_state['hurst'] - self._last_market_state['hurst'])
        
        # Update state
        self._last_market_state = current_state
        
        # Detect regime change
        if (vol_change > 0.0002 or momentum_change > 0.00005 or 
            entropy_change > 0.1 or hurst_change > 0.15):
            return True
            
        return False

    def _confirm_signal_consistency(self, prediction: int, confidence: float) -> bool:
        """
        Balanced signal confirmation for quality trades.
        """
        self._signal_confirmation.append((prediction, confidence))
        
        # For good performance (like current 100% win rate), be less strict
        if len(self.strategy.trade_history) > 5:
            recent_wins = sum(1 for trade in self.strategy.trade_history[-5:] if trade["result"] == "win")
            win_rate = recent_wins / min(5, len(self.strategy.trade_history))
            
            # If win rate is high, require only 1 signal
            if win_rate >= 0.8:
                return confidence >= self._dynamic_confidence
        
        # Otherwise require 2 consistent signals
        if len(self._signal_confirmation) < 2:
            return False
            
        # Check for signal consistency
        recent_predictions = [p for p, c in self._signal_confirmation[-2:]]
        recent_confidences = [c for p, c in self._signal_confirmation[-2:]]
        
        # Require consistent direction
        if len(set(recent_predictions)) > 1:
            return False
            
        # Require good average confidence
        avg_confidence = sum(recent_confidences) / len(recent_confidences)
        if avg_confidence >= self._dynamic_confidence:
            return True
            
        return False

    def _final_safety_check(self, feat: np.ndarray, prediction: int, confidence: float) -> bool:
        """
        Ultra-conservative final check before placing trade.
        """
        # For very high confidence signals, add extra scrutiny
        if confidence >= 0.95:
            # Check if market conditions support such high confidence
            momentum = feat[FEAT["short_mom"]]
            imbalance = feat[FEAT["imbalance"]]
            digit_bias = feat[FEAT["digit_bias"]]
            
            # Verify that multiple strong signals support this confidence
            strong_signals = 0
            
            if prediction == 1:  # OVER
                if momentum > 0.000005:  # Very strong momentum up
                    strong_signals += 1
                if imbalance > 0.2:  # Strong upward imbalance
                    strong_signals += 1
                if digit_bias > 0.75:  # Very strong high digit bias
                    strong_signals += 1
            else:  # UNDER
                if momentum < -0.000005:  # Very strong momentum down
                    strong_signals += 1
                if imbalance < -0.2:  # Strong downward imbalance
                    strong_signals += 1
                if digit_bias < 0.25:  # Very strong low digit bias
                    strong_signals += 1
                    
            # For 95%+ confidence, require at least 2 very strong supporting signals
            if strong_signals < 2:
                return False
                
        # Additional check: avoid trading during transition periods
        streak = feat[FEAT["streak"]]
        if streak > 0.3:  # Very long streak might be ending
            return False
            
        return True

    def _analyze_market_bias(self, feat: np.ndarray):
        """
        Analyze current market conditions to determine if market favors OVER or UNDER trades.
        """
        momentum = feat[FEAT["short_mom"]]
        imbalance = feat[FEAT["imbalance"]]
        digit_bias = feat[FEAT["digit_bias"]]
        mean_rev = feat[FEAT["mean_rev"]]
        
        # Calculate bias signals
        over_signals = 0
        under_signals = 0
        total_confidence = 0
        
        # Momentum bias
        if momentum > 0.000002:
            over_signals += 1
            total_confidence += abs(momentum) * 1000000  # Scale for confidence
        elif momentum < -0.000002:
            under_signals += 1
            total_confidence += abs(momentum) * 1000000
            
        # Imbalance bias
        if imbalance > 0.1:
            over_signals += 1
            total_confidence += abs(imbalance)
        elif imbalance < -0.1:
            under_signals += 1
            total_confidence += abs(imbalance)
            
        # Digit bias
        if digit_bias > 0.6:
            over_signals += 1
            total_confidence += abs(digit_bias - 0.5) * 2
        elif digit_bias < 0.4:
            under_signals += 1
            total_confidence += abs(0.5 - digit_bias) * 2
            
        # Mean reversion (inverse signal)
        if mean_rev > 0.5:
            under_signals += 1  # Price high, expect pullback
            total_confidence += abs(mean_rev) * 0.5
        elif mean_rev < -0.5:
            over_signals += 1   # Price low, expect bounce
            total_confidence += abs(mean_rev) * 0.5
        
        # Determine market bias
        if over_signals > under_signals:
            self._market_bias = "OVER"
            self._bias_confidence = min(0.9, total_confidence / max(1, over_signals))
        elif under_signals > over_signals:
            self._market_bias = "UNDER"
            self._bias_confidence = min(0.9, total_confidence / max(1, under_signals))
        else:
            self._market_bias = None
            self._bias_confidence = 0.0

    def _adapt_to_market_conditions(self, prediction: int, confidence: float) -> int:
        """
        Intelligent market adaptation: if we need OVER but market favors UNDER, trade UNDER instead.
        """
        if self._market_bias is None or self._bias_confidence < 0.6:
            return prediction  # No strong bias, keep original prediction
            
        # Check what we need vs what market favors
        needed_type = "OVER" if prediction == 1 else "UNDER"
        
        # If market strongly favors opposite direction and we can trade that type
        if (self._market_bias != needed_type and 
            self._bias_confidence > 0.7 and 
            confidence > 0.75):  # Only adapt for high confidence signals
            
            # Check if we can trade the market-favored direction
            market_prediction = 1 if self._market_bias == "OVER" else 0
            if self.strategy.should_trade_type(market_prediction):
                return market_prediction
                
        return prediction  # Keep original if can't adapt

    def _try_switch_symbol(self) -> bool:
        """
        Switch to next available symbol if current one isn't providing good trades.
        """
        if len(AVAILABLE_SYMBOLS) <= 1:
            self._ticks_without_trade = 0  # Reset counter if no alternatives
            return False
            
        # Try next symbol
        self._symbol_index = (self._symbol_index + 1) % len(AVAILABLE_SYMBOLS)
        new_symbol = AVAILABLE_SYMBOLS[self._symbol_index]
        
        if new_symbol == self.current_symbol:
            self._ticks_without_trade = 0  # Cycled through all, reset
            return False
            
        print(f"[Bot] Switching from {self.current_symbol} to {new_symbol} - seeking better opportunities")
        
        # Switch symbol
        old_symbol = self.current_symbol
        self.current_symbol = new_symbol
        
        try:
            # Update client with new symbol
            self.client.symbol = new_symbol
            # Resubscribe to new symbol ticks
            self.client.subscribe_ticks()
            
            # Reset feature engine for new symbol
            self.features = FeatureEngine(window=50)
            
            # Reset counters
            self._ticks_without_trade = 0
            self.tick_count = 0
            
            print(f"[Bot] Successfully switched to {new_symbol}")
            return True
            
        except Exception as e:
            print(f"[Bot] Failed to switch to {new_symbol}: {e}")
            # Revert to old symbol
            self.current_symbol = old_symbol
            self.client.symbol = old_symbol
            self.client.subscribe_ticks()
            self._ticks_without_trade = 0
            return False

    def _update_dynamic_confidence(self):
        """
        Update the dynamic confidence based on recent performance.
        """
        self._dynamic_confidence = self._get_dynamic_confidence()

    def _is_high_quality_signal(self, feat: np.ndarray, prediction: int, confidence: float) -> bool:
        """
        Signal quality gate — require meaningful confidence and momentum alignment.
        """
        if confidence < 0.65:
            return False

        momentum = feat[FEAT["short_mom"]]

        # For medium confidence (0.65–0.74), require momentum to at least not oppose the trade
        if confidence < 0.75:
            if prediction == 1 and momentum < -0.000005:  # Strong opposing momentum → skip
                return False
            if prediction == 0 and momentum > 0.000005:
                return False

        return True

    def _heuristic_predict(self, feat: np.ndarray) -> tuple[int, float]:
        """
        Improved heuristic with stricter quality requirements for better performance.
        """
        momentum    = feat[FEAT["short_mom"]]
        med_mom     = feat[FEAT["med_mom"]]
        mean_rev    = feat[FEAT["mean_rev"]]
        imbalance   = feat[FEAT["imbalance"]]
        ac_lag1     = feat[FEAT["ac_lag1"]]
        hurst       = feat[FEAT["hurst"]]
        digit_bias  = feat[FEAT["digit_bias"]]
        d_streak    = feat[FEAT["digit_streak"]]

        votes = []  # (prediction, weight)

        # Balanced momentum signals
        if abs(momentum) > 3e-6:  # Slightly reduced from 5e-6
            votes.append((1 if momentum > 0 else 0, 0.35))

        # Balanced mean reversion
        if abs(mean_rev) > 0.8:  # Reduced from 1.0
            votes.append((0 if mean_rev > 0 else 1, 0.35))

        # Balanced imbalance
        if abs(imbalance) > 0.15:  # Reduced from 0.20
            votes.append((1 if imbalance > 0 else 0, 0.30))

        # Balanced autocorrelation with trend confirmation
        if abs(ac_lag1) > 0.08:  # Reduced from 0.12
            trend_dir = 1 if med_mom > 0 else 0
            # Only vote if momentum and autocorr agree
            if (ac_lag1 > 0 and momentum > 0) or (ac_lag1 < 0 and momentum < 0):
                votes.append((trend_dir if ac_lag1 > 0 else 1 - trend_dir, 0.30))

        # Balanced Hurst with momentum confirmation
        if hurst > 0.60:  # Reduced from 0.65
            if abs(momentum) > 1e-6:  # Reduced confirmation requirement
                votes.append((1 if momentum > 0 else 0, 0.25))
        elif hurst < 0.40:  # Increased from 0.35
            if abs(mean_rev) > 0.6:  # Reduced confirmation requirement
                votes.append((0 if mean_rev > 0 else 1, 0.25))

        # Balanced digit bias
        if digit_bias > 0.70:  # Reduced from 0.75
            votes.append((1, 0.30))
        elif digit_bias < 0.30:  # Increased from 0.25
            votes.append((0, 0.30))

        # Balanced streak reversal with confirmation
        if d_streak > 0.20:   # Reduced from 0.25
            current_side = 1 if feat[FEAT["last_digit"]] > 0.44 else 0
            # Only reverse if we have other confirming signals
            if len(votes) >= 1:  # Require at least one other signal
                votes.append((1 - current_side, 0.25))

        # Debug logging for heuristic analysis
        if len(votes) > 0:
            print(f"[Bot] Heuristic votes: {len(votes)} - {votes}")
        else:
            print(f"[Bot] Heuristic: No votes - mom:{momentum:.6f}, rev:{mean_rev:.2f}, imb:{imbalance:.3f}, ac:{ac_lag1:.3f}, hurst:{hurst:.3f}, dbias:{digit_bias:.3f}, dstreak:{d_streak:.3f}")

        # Require minimum number of supporting votes (balanced at 2)
        if len(votes) < 2:
            return -1, 0.0

        over_score  = sum(w for p, w in votes if p == 1)
        under_score = sum(w for p, w in votes if p == 0)
        total = over_score + under_score

        # Require good consensus (balanced at 65%)
        if over_score > under_score:
            confidence = over_score / total
            if confidence >= 0.65:  # Balanced threshold
                return 1, confidence
        else:
            confidence = under_score / total
            if confidence >= 0.65:  # Balanced threshold
                return 0, confidence

        return -1, 0.0


if __name__ == "__main__":
    bot = Bot()
    bot.run()
