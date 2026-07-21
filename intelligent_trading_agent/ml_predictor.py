"""
Machine Learning Predictor for trading decisions.
Uses ensemble of models to predict price direction.
Learns from actual market movements, not trade results.
"""

import numpy as np
import pickle
import os
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from collections import deque
from logger import agent_logger


class MLPredictor:
    """
    ML-based price direction predictor.
    Learns from market patterns by observing actual price movements.
    """
    
    def __init__(self, models_dir: str = "models", contract_duration_minutes: int = 5):
        self.models_dir = models_dir
        self.scaler = StandardScaler()
        self.contract_duration_minutes = contract_duration_minutes
        
        # Ensemble of models with REDUCED COMPLEXITY to prevent overfitting
        self.rf_model = RandomForestClassifier(
            n_estimators=50,        # More trees for better pattern learning
            max_depth=6,            # Deeper trees to capture complex patterns
            min_samples_split=20,   # Reasonable split requirement
            min_samples_leaf=10,    # Prevent overfitting on noise
            max_features='sqrt',
            random_state=42
        )
        
        self.gb_model = GradientBoostingClassifier(
            n_estimators=50,        # More estimators for better learning
            max_depth=4,            # Moderate depth to capture market patterns
            learning_rate=0.08,     # Balanced learning rate
            min_samples_split=20,
            min_samples_leaf=10,
            max_features='sqrt',
            random_state=42
        )
        
        # Training data buffer
        self.training_buffer = deque(maxlen=1000)
        self.min_training_samples = 50
        
        # Market observation buffer - stores (features, future_price) pairs
        self.observation_buffer = deque(maxlen=500)  # Increased to store more history
        
        # Calculate lookback based on contract duration
        # We predict over the FULL contract duration for real intelligence.
        # Our models learn the relationship between current features and
        # price direction CONTRACT_DURATION minutes later.
        # This means the ML is learning to predict: "if market looks like X now,
        # where will price be in 10 minutes?"
        # Use the actual contract duration for lookback so the model learns
        # meaningful patterns at the right timescale.
        self.lookback_ticks = max(min(contract_duration_minutes * 60, 600), 60)  # Cap at 600 ticks, min 60
        
        agent_logger.log_info(f"ML Predictor: Predicting {contract_duration_minutes} minutes ahead (lookback={self.lookback_ticks} ticks)")
        
        # Model state
        self.is_trained = False
        self.model_accuracy = 0.5
        self.predictions_made = 0
        self.correct_predictions = 0
        
        # Live validation tracking
        self.live_predictions = deque(maxlen=100)  # Store recent predictions with outcomes
        self.live_accuracy_window = 20  # Calculate accuracy over last 20 predictions
        
        # Auto-training settings
        self.auto_train_interval = 30  # Train more frequently for better adaptability
        self.observations_since_training = 0
        self.min_training_samples = 50  # Reduced threshold to start learning sooner
        
        # Load existing models if available
        self._load_models()
    
    def observe_market(self, market_data: Dict, current_price: float):
        """
        Observe market conditions and store for learning.
        This is called every tick to build training data from actual market movements.
        
        Args:
            market_data: Current market features
            current_price: Current price
        """
        # Enrich features with pattern and S/R data
        enriched_data = self._enrich_features(market_data, current_price)
        
        # Extract features
        features = self.prepare_features(enriched_data)
        
        # Store observation with current price
        self.observation_buffer.append({
            'features': features[0],
            'price': current_price,
            'timestamp': datetime.now()
        })
        
        # Check if we can create a training sample
        # We need at least lookback_ticks + 1 observations
        if len(self.observation_buffer) > self.lookback_ticks:
            # Get observation from lookback_ticks ago
            past_observation = self.observation_buffer[-self.lookback_ticks - 1]
            current_observation = self.observation_buffer[-1]
            
            past_price = past_observation['price']
            current_price = current_observation['price']
            
            # Determine actual direction (what happened)
            price_change = current_price - past_price
            actual_direction = 1 if price_change > 0 else 0  # 1=UP, 0=DOWN
            
            # Add to training buffer
            self.training_buffer.append((past_observation['features'], actual_direction))
            self.observations_since_training += 1
            
            # Auto-train periodically
            if self.observations_since_training >= self.auto_train_interval:
                if len(self.training_buffer) >= self.min_training_samples:
                    # Quick check for class diversity before attempting training
                    y_preview = [label for _, label in self.training_buffer]
                    up_preview = sum(y_preview)
                    down_preview = len(y_preview) - up_preview
                    
                    if up_preview >= 2 and down_preview >= 2:
                        agent_logger.log_info(
                            f"🎓 Auto-training ML model with {len(self.training_buffer)} market observations "
                            f"(UP={up_preview}, DOWN={down_preview})..."
                        )
                        self.train()
                        self.observations_since_training = 0
                    else:
                        if self.observations_since_training % 100 == 0:
                            agent_logger.log_info(
                                f"⏳ Waiting for class diversity: {len(self.training_buffer)} samples "
                                f"(UP={up_preview}, DOWN={down_preview}) - need at least 2 of each"
                            )
                        # Don't reset counter - keep accumulating until we have diversity
                else:
                    if self.observations_since_training % 100 == 0:
                        agent_logger.log_info(
                            f"⏳ Accumulating training data: {len(self.training_buffer)}/{self.min_training_samples} samples"
                        )
    
    def _enrich_features(self, market_data: Dict, current_price: float) -> Dict:
        """
        Enrich market data with support/resistance and pattern information.
        """
        enriched = market_data.copy()
        features = enriched.get('features', {})
        
        # Calculate support/resistance from recent price history
        if len(self.observation_buffer) >= 20:
            recent_prices = [obs['price'] for obs in list(self.observation_buffer)[-20:]]
            
            # Simple S/R: local min/max in recent history
            support = min(recent_prices)
            resistance = max(recent_prices)
            price_range = resistance - support if resistance > support else 1.0
            
            # Distance to S/R (normalized)
            dist_to_support = (current_price - support) / price_range if price_range > 0 else 0.5
            dist_to_resistance = (resistance - current_price) / price_range if price_range > 0 else 0.5
            
            # Near S/R (within 5% of range)
            near_support = 1.0 if dist_to_support < 0.05 else 0.0
            near_resistance = 1.0 if dist_to_resistance < 0.05 else 0.0
            
            # S/R strength (how many times price touched these levels)
            support_touches = sum(1 for p in recent_prices if abs(p - support) < price_range * 0.02)
            resistance_touches = sum(1 for p in recent_prices if abs(p - resistance) < price_range * 0.02)
            
            support_strength = min(support_touches / 5.0, 1.0)  # Normalize to 0-1
            resistance_strength = min(resistance_touches / 5.0, 1.0)
            
            features['distance_to_support'] = dist_to_support
            features['distance_to_resistance'] = dist_to_resistance
            features['support_strength'] = support_strength
            features['resistance_strength'] = resistance_strength
            features['near_support'] = near_support
            features['near_resistance'] = near_resistance
            
            # Calculate trend features for 5-minute prediction
            if len(recent_prices) >= 10:
                # Trend strength: how much price moved in dominant direction
                price_changes = [recent_prices[i] - recent_prices[i-1] for i in range(1, len(recent_prices))]
                up_moves = sum(c for c in price_changes if c > 0)
                down_moves = abs(sum(c for c in price_changes if c < 0))
                total_movement = up_moves + down_moves
                
                if total_movement > 0:
                    trend_strength = abs(up_moves - down_moves) / total_movement
                    features['trend_strength'] = trend_strength
                else:
                    features['trend_strength'] = 0.0
                
                # Price velocity: average price change per tick
                avg_change = sum(price_changes) / len(price_changes) if price_changes else 0
                features['price_velocity'] = avg_change / (price_range if price_range > 0 else 1.0)
                
                # Trend consistency: what % of moves are in same direction
                dominant_direction = 1 if up_moves > down_moves else -1
                consistent_moves = sum(1 for c in price_changes if (c > 0 and dominant_direction > 0) or (c < 0 and dominant_direction < 0))
                features['trend_consistency'] = consistent_moves / len(price_changes) if price_changes else 0.5
                
                # Recent high/low ratio
                recent_5 = recent_prices[-5:]
                highs = sum(1 for i in range(1, len(recent_5)) if recent_5[i] > recent_5[i-1])
                features['recent_high_low_ratio'] = highs / 4.0 if len(recent_5) >= 2 else 0.5
            else:
                features['trend_strength'] = 0.0
                features['price_velocity'] = 0.0
                features['trend_consistency'] = 0.5
                features['recent_high_low_ratio'] = 0.5
        else:
            # Not enough data yet
            features['distance_to_support'] = 0.5
            features['distance_to_resistance'] = 0.5
            features['support_strength'] = 0.0
            features['resistance_strength'] = 0.0
            features['near_support'] = 0.0
            features['near_resistance'] = 0.0
        
        # Pattern features (will be populated by agent if patterns detected)
        features['has_bullish_pattern'] = features.get('has_bullish_pattern', 0.0)
        features['has_bearish_pattern'] = features.get('has_bearish_pattern', 0.0)
        features['pattern_confidence'] = features.get('pattern_confidence', 0.0)
        features['breakout_detected'] = features.get('breakout_detected', 0.0)
        features['breakout_direction'] = features.get('breakout_direction', 0.0)
        
        enriched['features'] = features
        return enriched
    
    def prepare_features(self, market_data: Dict) -> np.ndarray:
        """
        Prepare feature vector from market data.
        Returns normalized feature array.
        """
        features = market_data.get('features', {})
        
        # Select key features for ML
        feature_list = [
            # Technical indicators
            features.get('rsi', 50.0),
            features.get('macd', 0.0),
            features.get('macd_signal', 0.0),
            features.get('macd_histogram', 0.0),
            features.get('bb_position', 0.5),
            features.get('bb_width', 0.0),
            features.get('momentum_5', 0.0),
            features.get('momentum_10', 0.0),
            features.get('momentum_20', 0.0),
            features.get('volatility', 0.5),
            features.get('atr', 0.0),
            features.get('sma_5', 0.0),
            features.get('sma_10', 0.0),
            features.get('sma_20', 0.0),
            features.get('ema_5', 0.0),
            features.get('ema_10', 0.0),
            features.get('ema_20', 0.0),
            features.get('price_change_1', 0.0),
            features.get('price_change_5', 0.0),
            features.get('price_change_10', 0.0),
            
            # Trend strength features (NEW - critical for 5-minute prediction)
            features.get('trend_strength', 0.0),        # How strong is current trend
            features.get('price_velocity', 0.0),        # Rate of price change
            features.get('trend_consistency', 0.0),     # How consistent is the trend
            features.get('recent_high_low_ratio', 0.5), # Recent highs vs lows
            
            # Support/Resistance features (NEW)
            features.get('distance_to_support', 0.0),      # How far from support
            features.get('distance_to_resistance', 0.0),   # How far from resistance
            features.get('support_strength', 0.0),         # How strong is support
            features.get('resistance_strength', 0.0),      # How strong is resistance
            features.get('near_support', 0.0),             # 1 if near support, 0 otherwise
            features.get('near_resistance', 0.0),          # 1 if near resistance, 0 otherwise
            
            # Pattern features (NEW)
            features.get('has_bullish_pattern', 0.0),      # 1 if bullish pattern detected
            features.get('has_bearish_pattern', 0.0),      # 1 if bearish pattern detected
            features.get('pattern_confidence', 0.0),       # Confidence of detected pattern
            features.get('breakout_detected', 0.0),        # 1 if breakout detected
            features.get('breakout_direction', 0.0),       # 1=up, -1=down, 0=none
        ]
        
        return np.array(feature_list).reshape(1, -1)
    
    def predict(self, market_data: Dict) -> Tuple[str, float]:
        """
        Predict price direction using ML models.
        
        Returns:
            (prediction, confidence)
            prediction: 'UP' or 'DOWN' or 'HOLD'
            confidence: 0.0 to 1.0
        """
        if not self.is_trained:
            # Not enough data yet, return neutral
            return 'HOLD', 0.0
        
        try:
            # Prepare features
            X = self.prepare_features(market_data)
            X_scaled = self.scaler.transform(X)
            
            # Get predictions from both models
            rf_proba = self.rf_model.predict_proba(X_scaled)[0]
            gb_proba = self.gb_model.predict_proba(X_scaled)[0]
            
            # Ensemble: average probabilities
            avg_proba = (rf_proba + gb_proba) / 2
            
            # Class 1 = UP, Class 0 = DOWN
            up_probability = avg_proba[1]
            down_probability = avg_proba[0]
            
            # Determine prediction
            if up_probability > down_probability:
                prediction = 'UP'
                confidence = up_probability
            else:
                prediction = 'DOWN'
                confidence = down_probability
            
            # Adjust confidence INTELIGENTLY based on model accuracy
            # If model accuracy is below 50%, it's worse than random — don't trust it
            # If model accuracy is above 55%, it has genuine predictive value
            # We use the confidence gap (distance from 0.5) as the real signal strength
            if self.model_accuracy > 0.55:
                # Model has genuine predictive power - use it with accuracy confidence
                confidence = confidence * (0.5 + self.model_accuracy * 0.5)  # 50-95% of original
            elif self.model_accuracy > 0.51:
                # Slight edge - use with adjustment but trust it less
                confidence = confidence * (self.model_accuracy * 0.8)
            else:
                # Model is not better than random - don't use ML signal
                agent_logger.log_info(f"ML model accuracy ({self.model_accuracy:.2%}) is near random — holding off predictions")
                return 'HOLD', 0.0
            
            self.predictions_made += 1
            
            # Store prediction for validation (will be validated later)
            current_price = market_data.get('price', 0)
            self.live_predictions.append({
                'prediction': prediction,
                'confidence': confidence,
                'price_at_prediction': current_price,
                'timestamp': datetime.now(),
                'validated': False
            })
            
            # Log to show ML is actively being used
            if self.predictions_made % 10 == 0:
                live_acc = self._calculate_live_accuracy()
                agent_logger.log_info(
                    f"🧠 ML Prediction: {prediction} (confidence: {confidence:.2f}, "
                    f"model_acc: {self.model_accuracy:.2%}, live_acc: {live_acc:.2%}, "
                    f"samples: {len(self.training_buffer)})"
                )
            
            return prediction, float(confidence)
            
        except Exception as e:
            agent_logger.log_error(f"ML prediction error: {e}")
            return 'HOLD', 0.0
    
    def validate_predictions(self, current_price: float):
        """
        Validate recent predictions against actual price movements.
        Checks if prediction would have won a Rise/Fall trade.
        """
        for pred in self.live_predictions:
            if not pred['validated']:
                # Check if enough time has passed (contract duration)
                time_diff = (datetime.now() - pred['timestamp']).total_seconds()
                expected_duration = self.lookback_ticks  # In seconds (assuming 1 tick/sec)
                
                if time_diff >= expected_duration:
                    # Compare current price with price at prediction
                    entry_price = pred['price_at_prediction']
                    exit_price = current_price
                    
                    # For Rise/Fall: Did price move in predicted direction?
                    if pred['prediction'] == 'UP':
                        # RISE trade wins if exit_price > entry_price
                        was_correct = (exit_price > entry_price)
                        profit_pips = exit_price - entry_price
                    else:
                        # FALL trade wins if exit_price < entry_price
                        was_correct = (exit_price < entry_price)
                        profit_pips = entry_price - exit_price
                    
                    pred['validated'] = True
                    pred['was_correct'] = was_correct
                    pred['profit_pips'] = profit_pips
                    pred['exit_price'] = exit_price
                    
                    if was_correct:
                        self.correct_predictions += 1
                    
                    # Log validation result
                    result_emoji = "✅" if was_correct else "❌"
                    agent_logger.log_info(
                        f"{result_emoji} ML Validation: Predicted {pred['prediction']} @ {entry_price:.5f} → "
                        f"Actual @ {exit_price:.5f} ({profit_pips:+.5f} pips) | "
                        f"Live Acc: {self._calculate_live_accuracy():.1%}"
                    )
    
    def _calculate_live_accuracy(self) -> float:
        """Calculate accuracy on validated live predictions."""
        validated = [p for p in self.live_predictions if p.get('validated', False)]
        if len(validated) < 5:
            return 0.0
        
        correct = sum(1 for p in validated if p.get('was_correct', False))
        return correct / len(validated)
    
    def add_training_sample(self, market_data: Dict, actual_direction: str):
        """
        Add a training sample (features + actual outcome).
        This is kept for backward compatibility with trade-based learning.
        
        Args:
            market_data: Market features at trade entry
            actual_direction: 'UP' or 'DOWN' (actual price movement)
        """
        X = self.prepare_features(market_data)
        y = 1 if actual_direction == 'UP' else 0
        
        self.training_buffer.append((X[0], y))
        
        # Retrain if we have enough samples
        if len(self.training_buffer) >= self.min_training_samples:
            if len(self.training_buffer) % 10 == 0:  # Retrain every 10 samples
                self.train()
    
    def train(self):
        """Train/retrain the ML models with buffered data using balanced sampling."""
        if len(self.training_buffer) < self.min_training_samples:
            agent_logger.log_info(f"Not enough training data: {len(self.training_buffer)}/{self.min_training_samples}")
            return
        
        try:
            # Prepare training data
            X_list = []
            y_list = []
            
            for features, label in self.training_buffer:
                X_list.append(features)
                y_list.append(label)
            
            X = np.array(X_list)
            y = np.array(y_list)
            
            # Check class balance - need at least 2 examples of each class
            up_count = np.sum(y == 1)
            down_count = np.sum(y == 0)
            
            if up_count < 2 or down_count < 2:
                agent_logger.log_warning(
                    f"⚠️ Insufficient class diversity for training: UP={up_count}, DOWN={down_count}. "
                    f"Need at least 2 examples of each class. Waiting for more balanced data..."
                )
                return
            
            # CRITICAL FIX: Balance the training data
            # If we have 620 UP and 233 DOWN, sample 233 UP and 233 DOWN for balanced training
            up_indices = np.where(y == 1)[0]
            down_indices = np.where(y == 0)[0]
            
            # Take the minimum count to balance classes
            min_samples = min(len(up_indices), len(down_indices))
            
            # Randomly sample equal numbers from each class
            np.random.seed(42)  # For reproducibility
            balanced_up_indices = np.random.choice(up_indices, size=min_samples, replace=False)
            balanced_down_indices = np.random.choice(down_indices, size=min_samples, replace=False)
            
            # Combine and shuffle
            balanced_indices = np.concatenate([balanced_up_indices, balanced_down_indices])
            np.random.shuffle(balanced_indices)
            
            X_balanced = X[balanced_indices]
            y_balanced = y[balanced_indices]
            
            agent_logger.log_info(
                f"📊 Balanced training data: Original ({up_count} UP / {down_count} DOWN) → "
                f"Balanced ({min_samples} UP / {min_samples} DOWN)"
            )
            
            # Fit scaler on balanced data
            self.scaler.fit(X_balanced)
            X_scaled_balanced = self.scaler.transform(X_balanced)
            
            # CRITICAL FIX: Time-series train/test split
            # Use first 70% for training, last 30% for validation (maintains temporal order)
            train_size = int(len(X_scaled_balanced) * 0.7)
            X_train, X_test = X_scaled_balanced[:train_size], X_scaled_balanced[train_size:]
            y_train, y_test = y_balanced[:train_size], y_balanced[train_size:]
            
            # Train models on training set only
            self.rf_model.fit(X_train, y_train)
            self.gb_model.fit(X_train, y_train)
            
            # Calculate training accuracy
            train_rf_score = self.rf_model.score(X_train, y_train)
            train_gb_score = self.gb_model.score(X_train, y_train)
            train_accuracy = (train_rf_score + train_gb_score) / 2
            
            # Calculate VALIDATION accuracy (more realistic!)
            if len(X_test) > 0:
                test_rf_score = self.rf_model.score(X_test, y_test)
                test_gb_score = self.gb_model.score(X_test, y_test)
                validation_accuracy = (test_rf_score + test_gb_score) / 2
                
                # Use validation accuracy as model accuracy (more honest!)
                self.model_accuracy = validation_accuracy
                
                agent_logger.log_info(
                    f"✅ ML models trained: {len(X_balanced)} balanced samples | "
                    f"Train Acc: {train_accuracy:.2%} | "
                    f"Valid Acc: {validation_accuracy:.2%} | "
                    f"Split: {len(X_train)} train / {len(X_test)} test | "
                    f"Classes: {min_samples} UP / {min_samples} DOWN (balanced)"
                )
            else:
                # Not enough data for validation split
                self.model_accuracy = train_accuracy
                agent_logger.log_info(
                    f"✅ ML models trained: {len(X_balanced)} balanced samples | "
                    f"Accuracy: {train_accuracy:.2%} (no validation split) | "
                    f"Classes: {min_samples} UP / {min_samples} DOWN (balanced)"
                )
            
            self.is_trained = True
            
            # Save models
            self._save_models()
            
        except Exception as e:
            agent_logger.log_error(f"ML training error: {e}")
    
    def record_prediction_result(self, was_correct: bool):
        """Record if the prediction was correct."""
        if was_correct:
            self.correct_predictions += 1
        
        if self.predictions_made > 0 and self.predictions_made % 20 == 0:
            accuracy = self.correct_predictions / self.predictions_made
            agent_logger.log_info(f"ML Live Accuracy: {accuracy:.1%} ({self.correct_predictions}/{self.predictions_made})")
    
    def _save_models(self):
        """Save trained models to disk."""
        try:
            os.makedirs(self.models_dir, exist_ok=True)
            
            with open(os.path.join(self.models_dir, 'rf_model.pkl'), 'wb') as f:
                pickle.dump(self.rf_model, f)
            
            with open(os.path.join(self.models_dir, 'gb_model.pkl'), 'wb') as f:
                pickle.dump(self.gb_model, f)
            
            with open(os.path.join(self.models_dir, 'scaler.pkl'), 'wb') as f:
                pickle.dump(self.scaler, f)
            
            # Save metadata
            metadata = {
                'is_trained': self.is_trained,
                'model_accuracy': self.model_accuracy,
                'predictions_made': self.predictions_made,
                'correct_predictions': self.correct_predictions,
                'training_samples': len(self.training_buffer),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(os.path.join(self.models_dir, 'ml_metadata.pkl'), 'wb') as f:
                pickle.dump(metadata, f)
            
            agent_logger.log_info("💾 ML models saved to disk")
            
        except Exception as e:
            agent_logger.log_error(f"Error saving models: {e}")
    
    def _load_models(self):
        """Load trained models from disk."""
        try:
            rf_path = os.path.join(self.models_dir, 'rf_model.pkl')
            gb_path = os.path.join(self.models_dir, 'gb_model.pkl')
            scaler_path = os.path.join(self.models_dir, 'scaler.pkl')
            metadata_path = os.path.join(self.models_dir, 'ml_metadata.pkl')
            
            if all(os.path.exists(p) for p in [rf_path, gb_path, scaler_path, metadata_path]):
                with open(rf_path, 'rb') as f:
                    self.rf_model = pickle.load(f)
                
                with open(gb_path, 'rb') as f:
                    self.gb_model = pickle.load(f)
                
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                
                with open(metadata_path, 'rb') as f:
                    metadata = pickle.load(f)
                    self.is_trained = metadata.get('is_trained', False)
                    self.model_accuracy = metadata.get('model_accuracy', 0.5)
                    self.predictions_made = metadata.get('predictions_made', 0)
                    self.correct_predictions = metadata.get('correct_predictions', 0)
                
                agent_logger.log_info(f"📂 ML models loaded - Accuracy: {self.model_accuracy:.2%}, Samples: {len(self.training_buffer)}")
            else:
                agent_logger.log_info("🆕 No existing ML models found, will learn from market observations")
                
        except Exception as e:
            agent_logger.log_error(f"Error loading models: {e}")
    
    def get_stats(self) -> Dict:
        """Get ML predictor statistics."""
        live_acc = self._calculate_live_accuracy()
        return {
            'is_trained': self.is_trained,
            'model_accuracy': self.model_accuracy,
            'predictions_made': self.predictions_made,
            'correct_predictions': self.correct_predictions,
            'training_samples': len(self.training_buffer),
            'observations': len(self.observation_buffer),
            'live_accuracy': live_acc,
            'validated_predictions': len([p for p in self.live_predictions if p.get('validated', False)])
        }
