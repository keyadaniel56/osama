"""
Machine Learning Predictor for trading decisions.
Uses ensemble of models to predict price direction.
"""

import numpy as np
import pickle
import os
from typing import Dict, Tuple, Optional
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from collections import deque
from logger import agent_logger


class MLPredictor:
    """
    ML-based price direction predictor.
    Combines multiple models for robust predictions.
    """
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self.scaler = StandardScaler()
        
        # Ensemble of models
        self.rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            random_state=42
        )
        
        self.gb_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        
        # Training data buffer
        self.training_buffer = deque(maxlen=1000)
        self.min_training_samples = 50
        
        # Model state
        self.is_trained = False
        self.model_accuracy = 0.5
        self.predictions_made = 0
        self.correct_predictions = 0
        
        # Load existing models if available
        self._load_models()
    
    def prepare_features(self, market_data: Dict) -> np.ndarray:
        """
        Prepare feature vector from market data.
        Returns normalized feature array.
        """
        features = market_data.get('features', {})
        
        # Select key features for ML
        feature_list = [
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
        ]
        
        return np.array(feature_list).reshape(1, -1)
    
    def predict(self, market_data: Dict) -> Tuple[str, float]:
        """
        Predict price direction using ML models.
        
        Returns:
            (prediction, confidence)
            prediction: 'UP' or 'DOWN'
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
            
            # Adjust confidence based on model accuracy
            confidence = confidence * self.model_accuracy
            
            self.predictions_made += 1
            
            agent_logger.log_info(f"ML Prediction: {prediction} (confidence: {confidence:.2f})")
            
            return prediction, float(confidence)
            
        except Exception as e:
            agent_logger.log_error(f"ML prediction error: {e}")
            return 'HOLD', 0.0
    
    def add_training_sample(self, market_data: Dict, actual_direction: str):
        """
        Add a training sample (features + actual outcome).
        
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
        """Train/retrain the ML models with buffered data."""
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
            
            # Fit scaler
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            
            # Train models
            self.rf_model.fit(X_scaled, y)
            self.gb_model.fit(X_scaled, y)
            
            # Calculate training accuracy
            rf_score = self.rf_model.score(X_scaled, y)
            gb_score = self.gb_model.score(X_scaled, y)
            self.model_accuracy = (rf_score + gb_score) / 2
            
            self.is_trained = True
            
            agent_logger.log_info(f"ML models trained: {len(self.training_buffer)} samples, accuracy: {self.model_accuracy:.2%}")
            
            # Save models
            self._save_models()
            
        except Exception as e:
            agent_logger.log_error(f"ML training error: {e}")
    
    def record_prediction_result(self, was_correct: bool):
        """Record if the prediction was correct."""
        if was_correct:
            self.correct_predictions += 1
        
        if self.predictions_made > 0:
            accuracy = self.correct_predictions / self.predictions_made
            agent_logger.log_info(f"ML Accuracy: {accuracy:.1%} ({self.correct_predictions}/{self.predictions_made})")
    
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
            
            agent_logger.log_info("ML models saved")
            
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
                
                agent_logger.log_info(f"ML models loaded - Accuracy: {self.model_accuracy:.2%}")
            else:
                agent_logger.log_info("No existing ML models found, will train from scratch")
                
        except Exception as e:
            agent_logger.log_error(f"Error loading models: {e}")
    
    def get_stats(self) -> Dict:
        """Get ML predictor statistics."""
        return {
            'is_trained': self.is_trained,
            'model_accuracy': self.model_accuracy,
            'predictions_made': self.predictions_made,
            'correct_predictions': self.correct_predictions,
            'training_samples': len(self.training_buffer),
            'live_accuracy': self.correct_predictions / self.predictions_made if self.predictions_made > 0 else 0.0
        }
