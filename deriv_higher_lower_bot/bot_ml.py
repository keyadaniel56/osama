"""
ML-Enhanced Higher/Lower Trading Bot for Volatility 15s
Uses machine learning to predict optimal trade entries
"""

import os
import time
import json
import websocket
import numpy as np
from datetime import datetime
from collections import deque
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import pickle

load_dotenv()

# Configuration
API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
APP_ID = os.getenv("DERIV_APP_ID", "1089")
SYMBOL = "1HZ15V"  # Volatility 15s
STAKE = float(os.getenv("STAKE", "1.0"))
DURATION = 5  # 5 ticks

# ML Configuration
MIN_CONFIDENCE = 0.70  # Only trade when model is 70%+ confident
MIN_TRAINING_SAMPLES = 50  # Minimum samples before using ML
FEATURE_WINDOW = 20  # Look back 20 ticks for features


class MLHigherLowerBot:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.authorized = False
        
        # Price tracking
        self.price_history = deque(maxlen=100)
        self.last_price = None
        self.current_price = None
        
        # Trade tracking
        self.in_trade = False
        self.trade_history = []
        self.total_profit = 0.0
        self.processed_contracts = set()
        self.ticks_since_trade = 0
        self.cooldown_ticks = 3
        self.active_contract_id = None
        self.tick_count = 0
        
        # ML components
        self.model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        self.scaler = StandardScaler()
        self.training_data = []  # (features, label)
        self.model_trained = False
        self.pending_trade_features = None
        
        # Load saved model if exists
        self._load_model()
        
    def _load_model(self):
        """Load pre-trained model if available"""
        try:
            with open('ml_model.pkl', 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.scaler = data['scaler']
                self.model_trained = True
                print(f"[{self._timestamp()}] 🧠 Loaded pre-trained model")
        except FileNotFoundError:
            print(f"[{self._timestamp()}] 🧠 No pre-trained model found, will train from scratch")
    
    def _save_model(self):
        """Save trained model"""
        if self.model_trained:
            with open('ml_model.pkl', 'wb') as f:
                pickle.dump({'model': self.model, 'scaler': self.scaler}, f)
            print(f"[{self._timestamp()}] 💾 Model saved")
    
    def _extract_features(self):
        """Extract features from price history"""
        if len(self.price_history) < FEATURE_WINDOW:
            return None
        
        prices = np.array(list(self.price_history)[-FEATURE_WINDOW:])
        
        # Price-based features
        returns = np.diff(prices) / prices[:-1]
        
        features = [
            # Momentum features
            returns[-1],  # Last return
            np.mean(returns[-3:]),  # Short-term momentum
            np.mean(returns[-5:]),  # Medium-term momentum
            np.mean(returns[-10:]),  # Long-term momentum
            
            # Volatility features
            np.std(returns[-5:]),  # Short-term volatility
            np.std(returns[-10:]),  # Long-term volatility
            
            # Trend features
            1 if returns[-1] < 0 else 0,  # Is red (down)
            np.sum(returns[-3:] < 0),  # Consecutive red count (last 3)
            np.sum(returns[-5:] < 0),  # Red count (last 5)
            
            # Price level features
            (prices[-1] - np.mean(prices)) / np.std(prices),  # Z-score
            (prices[-1] - np.min(prices)) / (np.max(prices) - np.min(prices)),  # Normalized position
            
            # Decimal features
            self._get_decimal_value(prices[-1]),  # Current decimal
            1 if self._get_decimal_value(prices[-1]) < 200 else 0,  # Decimal < 200
            
            # Pattern features
            1 if returns[-1] < returns[-2] else 0,  # Accelerating down
            np.mean(np.abs(returns[-5:])),  # Average absolute return
        ]
        
        return np.array(features)
    
    def _get_decimal_value(self, price):
        """Extract decimal part from price"""
        price_str = f"{price:.3f}"
        decimal_part = price_str.split('.')[1] if '.' in price_str else "000"
        return int(decimal_part)
    
    def _should_trade_ml(self):
        """Use ML model to decide if we should trade"""
        features = self._extract_features()
        if features is None:
            return False, 0.0
        
        # If model not trained yet, use simple rule
        if not self.model_trained:
            if len(self.training_data) >= MIN_TRAINING_SAMPLES:
                self._train_model()
            
            # Fallback to simple strategy
            is_red = features[6] == 1  # Is red feature
            decimal_ok = features[12] == 1  # Decimal < 200 feature
            return is_red and decimal_ok, 0.6
        
        # Use ML model
        features_scaled = self.scaler.transform([features])
        prediction_proba = self.model.predict_proba(features_scaled)[0]
        
        # Probability of winning (class 1)
        confidence = prediction_proba[1] if len(prediction_proba) > 1 else 0.5
        should_trade = confidence >= MIN_CONFIDENCE
        
        return should_trade, confidence
    
    def _train_model(self):
        """Train the ML model on collected data"""
        if len(self.training_data) < MIN_TRAINING_SAMPLES:
            return
        
        print(f"[{self._timestamp()}] 🧠 Training model with {len(self.training_data)} samples...")
        
        X = np.array([x[0] for x in self.training_data])
        y = np.array([x[1] for x in self.training_data])
        
        # Check if we have both classes
        if len(np.unique(y)) < 2:
            print(f"[{self._timestamp()}] ⚠️ Need both win and loss samples to train")
            return
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled, y)
        self.model_trained = True
        
        # Calculate accuracy
        accuracy = self.model.score(X_scaled, y)
        print(f"[{self._timestamp()}] ✅ Model trained! Accuracy: {accuracy:.1%}")
        
        # Save model
        self._save_model()
    
    def connect(self):
        """Connect to Deriv WebSocket API"""
        url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.run_forever()
    
    def _on_open(self, ws):
        """Handle connection open"""
        self.connected = True
        print(f"[{self._timestamp()}] ✅ Connected to Deriv API")
        self._authorize()
    
    def _authorize(self):
        """Authorize with API token"""
        self.ws.send(json.dumps({"authorize": API_TOKEN}))
    
    def _subscribe_ticks(self):
        """Subscribe to tick stream"""
        self.ws.send(json.dumps({
            "ticks": SYMBOL,
            "subscribe": 1
        }))
        print(f"[{self._timestamp()}] 📊 Subscribed to {SYMBOL} ticks")
    
    def _on_message(self, ws, message):
        """Handle incoming messages"""
        data = json.loads(message)
        msg_type = data.get("msg_type")
        
        if msg_type == "authorize":
            if "error" in data:
                print(f"[{self._timestamp()}] ❌ Auth error: {data['error']['message']}")
                return
            self.authorized = True
            account_id = data['authorize']['loginid']
            print(f"[{self._timestamp()}] ✅ Authorized as {account_id}")
            self._subscribe_ticks()
        
        elif msg_type == "tick":
            self._handle_tick(data["tick"])
        
        elif msg_type == "buy":
            self._handle_buy_response(data)
        
        elif msg_type == "proposal_open_contract":
            self._handle_contract_update(data)
    
    def _handle_tick(self, tick):
        """Process incoming tick"""
        price = float(tick["quote"])
        self.tick_count += 1
        
        # Update price tracking
        self.last_price = self.current_price
        self.current_price = price
        self.price_history.append(price)
        
        # Skip if we don't have enough history
        if len(self.price_history) < FEATURE_WINDOW:
            if self.tick_count % 10 == 0:
                print(f"[{self._timestamp()}] 📊 Collecting data: {len(self.price_history)}/{FEATURE_WINDOW}")
            return
        
        # Skip if already in trade
        if self.in_trade:
            return
        
        # Increment cooldown counter
        self.ticks_since_trade += 1
        
        # Skip if in cooldown period
        if self.ticks_since_trade < self.cooldown_ticks:
            return
        
        # Use ML to decide if we should trade
        should_trade, confidence = self._should_trade_ml()
        
        # Log decision periodically
        if self.tick_count % 10 == 0:
            decimal = self._get_decimal_value(price)
            is_red = price < self.last_price if self.last_price else False
            status = "🧠 ML" if self.model_trained else "📏 Rule"
            print(f"[{self._timestamp()}] {status} | Price: {price:.3f} | Red: {is_red} | "
                  f"Decimal: {decimal} | Confidence: {confidence:.1%} | Trade: {should_trade}")
        
        if should_trade:
            # Store features for later labeling
            self.pending_trade_features = self._extract_features()
            self._buy_lower(confidence)
    
    def _buy_lower(self, confidence):
        """Execute LOWER trade"""
        self.in_trade = True
        self.ticks_since_trade = 0
        
        payload = {
            "buy": "1",
            "price": STAKE,
            "parameters": {
                "amount": STAKE,
                "basis": "stake",
                "contract_type": "PUT",
                "currency": "USD",
                "duration": DURATION,
                "duration_unit": "t",
                "symbol": SYMBOL,
                "barrier": "+1"
            }
        }
        
        self.ws.send(json.dumps(payload))
        print(f"[{self._timestamp()}] 🎯 Buying LOWER | Confidence: {confidence:.1%} | Stake: ${STAKE}")
    
    def _handle_buy_response(self, data):
        """Handle buy confirmation"""
        if "error" in data:
            print(f"[{self._timestamp()}] ❌ Buy error: {data['error']['message']}")
            self.in_trade = False
            return
        
        buy_info = data.get("buy", {})
        contract_id = buy_info.get("contract_id")
        buy_price = buy_info.get("buy_price", STAKE)
        
        print(f"[{self._timestamp()}] ✅ Contract bought: {contract_id} (Buy price: ${buy_price})")
        
        # Subscribe to contract updates
        self.ws.send(json.dumps({
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1
        }))
        
        self.active_contract_id = contract_id
    
    def _handle_contract_update(self, data):
        """Handle contract status updates"""
        contract = data.get("proposal_open_contract", {})
        contract_id = contract.get("contract_id")
        is_sold = contract.get("is_sold")
        is_expired = contract.get("is_expired")
        
        if (is_sold or is_expired) and contract_id not in self.processed_contracts:
            self.processed_contracts.add(contract_id)
            
            profit = float(contract.get("profit", 0))
            won = profit > 0
            result_status = "WIN" if won else "LOSS"
            
            # Add to training data
            if self.pending_trade_features is not None:
                label = 1 if won else 0
                self.training_data.append((self.pending_trade_features, label))
                self.pending_trade_features = None
                
                # Retrain periodically
                if len(self.training_data) % 10 == 0:
                    self._train_model()
            
            self.total_profit += profit
            self.trade_history.append({
                "contract_id": contract_id,
                "profit": profit,
                "status": result_status,
                "timestamp": self._timestamp()
            })
            
            result_emoji = "🎉" if won else "😞"
            print(f"[{self._timestamp()}] {result_emoji} Trade {result_status} | "
                  f"Profit: ${profit:.2f} | Total P&L: ${self.total_profit:.2f}")
            
            self.in_trade = False
            self.active_contract_id = None
            self._print_stats()
    
    def _print_stats(self):
        """Print trading statistics"""
        if not self.trade_history:
            return
        
        wins = sum(1 for t in self.trade_history if t["status"] == "WIN")
        losses = len(self.trade_history) - wins
        win_rate = (wins / len(self.trade_history) * 100) if self.trade_history else 0
        
        model_status = "🧠 ML Active" if self.model_trained else f"📊 Learning ({len(self.training_data)}/{MIN_TRAINING_SAMPLES})"
        
        print(f"[{self._timestamp()}] 📊 Stats: {len(self.trade_history)} trades | "
              f"W/L: {wins}/{losses} | Win Rate: {win_rate:.1f}% | P&L: ${self.total_profit:.2f} | {model_status}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"[{self._timestamp()}] ❌ WebSocket error: {error}")
    
    def _on_close(self, ws, code, msg):
        """Handle connection close"""
        self.connected = False
        self.authorized = False
        print(f"[{self._timestamp()}] 🔌 Connection closed: {code} {msg}")
    
    def _timestamp(self):
        """Get formatted timestamp"""
        return datetime.now().strftime("%H:%M:%S")
    
    def run(self):
        """Start the bot"""
        print("=" * 60)
        print("🤖 ML-Enhanced Higher/Lower Trading Bot - Volatility 15s")
        print("=" * 60)
        print(f"Symbol: {SYMBOL}")
        print(f"Stake: ${STAKE}")
        print(f"Duration: {DURATION} ticks")
        print(f"Min Confidence: {MIN_CONFIDENCE:.0%}")
        print(f"Strategy: Machine Learning + Pattern Recognition")
        print("=" * 60)
        
        try:
            self.connect()
        except KeyboardInterrupt:
            print(f"\n[{self._timestamp()}] 🛑 Bot stopped by user")
            self._print_final_summary()
            self._save_model()
    
    def _print_final_summary(self):
        """Print final trading summary"""
        if not self.trade_history:
            print("No trades executed.")
            return
        
        wins = sum(1 for t in self.trade_history if t["status"] == "WIN")
        losses = len(self.trade_history) - wins
        win_rate = (wins / len(self.trade_history) * 100)
        
        print("\n" + "=" * 60)
        print("📊 FINAL SUMMARY")
        print("=" * 60)
        print(f"Total Trades: {len(self.trade_history)}")
        print(f"Wins: {wins}")
        print(f"Losses: {losses}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Total P&L: ${self.total_profit:.2f}")
        print(f"Training Samples: {len(self.training_data)}")
        print(f"Model Status: {'Trained ✅' if self.model_trained else 'Not Trained ❌'}")
        print("=" * 60)


if __name__ == "__main__":
    bot = MLHigherLowerBot()
    bot.run()
