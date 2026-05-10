"""
ML model: RandomForest with proper outcome-based labeling.
Label = actual outcome (1 if last digit > barrier, 0 if under barrier),
NOT the inverse of a wrong prediction.
"""

import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from collections import deque
from datetime import datetime


MODEL_PATH = "deriv_ml_bot/model.pkl"
MIN_SAMPLES = 100   # Reduced from 200 for faster startup
RETRAIN_CV_FOLDS = 3


class MLModel:
    def __init__(self):
        self.pipeline = self._build_pipeline()
        self.X_buffer = deque(maxlen=2000)
        self.y_buffer = deque(maxlen=2000)
        self.trained = False
        self.cv_accuracy = 0.0   # last cross-val accuracy — tracks if model is actually learning
        
        # Learning tracking
        self.training_history = []  # Track accuracy over time
        self.prediction_history = deque(maxlen=100)  # Track recent predictions vs actual
        self.feature_importance = None
        self.samples_added = 0
        self.retraining_count = 0
        
        self._load()

    def _build_pipeline(self) -> Pipeline:
        return Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=300,      # Increased from 200
                max_depth=10,          # Increased from 8
                min_samples_leaf=5,    # Decreased from 8 for more flexibility
                min_samples_split=10,  # Decreased from 16
                max_features='sqrt',   # Added for better generalization
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ))
        ])

    def add_sample(self, features: np.ndarray, actual_outcome: int):
        """
        actual_outcome: the TRUE result of the trade.
          1 = last digit was HIGH (> barrier, OVER won)
          0 = last digit was LOW  (<= barrier, UNDER won)
        This must come from the actual contract result, not from inverting a wrong prediction.
        """
        self.X_buffer.append(features)
        self.y_buffer.append(actual_outcome)
        self.samples_added += 1
        
        # Log learning progress periodically
        if self.samples_added % 25 == 0:
            self._log_learning_progress()

    def _log_learning_progress(self):
        """Log current learning statistics"""
        total_samples = len(self.X_buffer)
        if total_samples < 10:
            return
            
        # Calculate class distribution
        y_array = np.array(self.y_buffer)
        over_count = np.sum(y_array == 1)
        under_count = np.sum(y_array == 0)
        over_pct = (over_count / total_samples) * 100
        under_pct = (under_count / total_samples) * 100
        
        print(f"📊 [Model Learning] Samples: {total_samples} | OVER: {over_count} ({over_pct:.1f}%) | UNDER: {under_count} ({under_pct:.1f}%)")
        
        if self.trained and self.cv_accuracy > 0:
            print(f"🧠 [Model Performance] CV Accuracy: {self.cv_accuracy:.3f} | Retrainings: {self.retraining_count}")
            
        # Show recent prediction accuracy if we have enough data
        if len(self.prediction_history) >= 10:
            recent_correct = sum(1 for pred, actual in self.prediction_history if pred == actual)
            recent_accuracy = recent_correct / len(self.prediction_history)
            print(f"🎯 [Recent Predictions] Accuracy: {recent_accuracy:.3f} ({recent_correct}/{len(self.prediction_history)})")

    def track_prediction(self, prediction: int, actual_outcome: int):
        """Track prediction vs actual outcome for performance monitoring"""
        if prediction != -1:  # Only track when model made a prediction
            self.prediction_history.append((prediction, actual_outcome))

    def get_learning_stats(self) -> dict:
        """Get comprehensive learning statistics"""
        stats = {
            'total_samples': len(self.X_buffer),
            'samples_added': self.samples_added,
            'retraining_count': self.retraining_count,
            'cv_accuracy': self.cv_accuracy,
            'trained': self.trained,
            'training_history': self.training_history[-10:],  # Last 10 training sessions
        }
        
        if len(self.prediction_history) > 0:
            recent_correct = sum(1 for pred, actual in self.prediction_history if pred == actual)
            stats['recent_accuracy'] = recent_correct / len(self.prediction_history)
            stats['recent_predictions'] = len(self.prediction_history)
        
        if self.feature_importance is not None:
            stats['top_features'] = self.feature_importance[:5]  # Top 5 important features
            
        return stats

    def force_reanalysis(self) -> bool:
        """
        Force a reanalysis with current data, even with fewer samples.
        Used when switching trading phases to adapt to new market conditions.
        """
        if len(self.X_buffer) < 30:  # Minimum viable samples
            return False
            
        X = np.array(self.X_buffer)
        y = np.array(self.y_buffer)
        if len(np.unique(y)) < 2:
            return False

        try:
            # Use fewer CV folds for faster reanalysis
            scores = cross_val_score(self._build_pipeline(), X, y,
                                     cv=min(2, len(X)//10), scoring="accuracy", n_jobs=-1)
            self.cv_accuracy = float(np.mean(scores))
            print(f"🔄 [Model Reanalysis] CV accuracy: {self.cv_accuracy:.3f} (±{np.std(scores):.3f})")
            
            # Retrain the model
            self.pipeline.fit(X, y)
            self.trained = True
            self.retraining_count += 1
            
            # Update feature importance
            self._update_feature_importance()
            
            # Record training session
            self.training_history.append({
                'timestamp': datetime.now().isoformat(),
                'samples': len(X),
                'cv_accuracy': self.cv_accuracy,
                'type': 'reanalysis'
            })
            
            self._save()
            return True
        except Exception as e:
            print(f"❌ [Model] Reanalysis failed: {e}")
            return False

    def train(self) -> bool:
        if len(self.X_buffer) < MIN_SAMPLES:
            return False
        X = np.array(self.X_buffer)
        y = np.array(self.y_buffer)
        if len(np.unique(y)) < 2:
            return False

        # Cross-validate before committing — if accuracy is near chance, don't trust it
        try:
            scores = cross_val_score(self._build_pipeline(), X, y,
                                     cv=RETRAIN_CV_FOLDS, scoring="accuracy", n_jobs=-1)
            self.cv_accuracy = float(np.mean(scores))
            std_dev = np.std(scores)
            print(f"🧠 [Model Training] CV accuracy: {self.cv_accuracy:.3f} (±{std_dev:.3f}) | Samples: {len(X)}")
            
            # Show learning trend
            if len(self.training_history) > 0:
                last_accuracy = self.training_history[-1]['cv_accuracy']
                improvement = self.cv_accuracy - last_accuracy
                trend = "📈" if improvement > 0.01 else "📉" if improvement < -0.01 else "➡️"
                print(f"📊 [Learning Trend] {trend} Change: {improvement:+.3f} from last training")
                
        except Exception as e:
            print(f"❌ [Model] CV failed: {e}")
            self.cv_accuracy = 0.0

        self.pipeline.fit(X, y)
        self.trained = True
        self.retraining_count += 1
        
        # Update feature importance
        self._update_feature_importance()
        
        # Record training session
        self.training_history.append({
            'timestamp': datetime.now().isoformat(),
            'samples': len(X),
            'cv_accuracy': self.cv_accuracy,
            'type': 'full_training'
        })
        
        self._save()
        return True

    def _update_feature_importance(self):
        """Update and log feature importance from the trained model"""
        try:
            if hasattr(self.pipeline.named_steps['clf'], 'feature_importances_'):
                importances = self.pipeline.named_steps['clf'].feature_importances_
                
                # Create feature names (you can customize these based on your features)
                feature_names = [
                    'price_change', 'volatility', 'trend', 'momentum', 'rsi',
                    'bollinger_pos', 'volume_ratio', 'price_position', 'entropy',
                    'digit_entropy', 'last_digit', 'digit_pattern', 'time_features'
                ]
                
                # Pad or truncate to match actual feature count
                if len(feature_names) < len(importances):
                    feature_names.extend([f'feature_{i}' for i in range(len(feature_names), len(importances))])
                elif len(feature_names) > len(importances):
                    feature_names = feature_names[:len(importances)]
                
                # Sort by importance
                feature_importance_pairs = list(zip(feature_names, importances))
                feature_importance_pairs.sort(key=lambda x: x[1], reverse=True)
                
                self.feature_importance = feature_importance_pairs
                
                # Log top 5 most important features
                print("🔍 [Feature Importance] Top 5:")
                for i, (name, importance) in enumerate(feature_importance_pairs[:5]):
                    print(f"   {i+1}. {name}: {importance:.3f}")
                    
        except Exception as e:
            print(f"⚠️ [Model] Could not update feature importance: {e}")

    def predict(self, features: np.ndarray) -> tuple[int, float]:
        """
        Returns (predicted_class, confidence).
        Stricter requirements for better quality predictions.
        """
        if not self.trained:
            return -1, 0.0
        # Stricter CV accuracy requirement
        if self.cv_accuracy > 0 and self.cv_accuracy < 0.58:  # Increased from 0.52
            return -1, 0.0
        X = features.reshape(1, -1)
        pred = self.pipeline.predict(X)[0]
        proba = self.pipeline.predict_proba(X)[0]
        confidence = float(np.max(proba))
        
        # Stricter model confidence requirement
        if confidence < 0.65:  # Increased from 0.55
            return -1, 0.0
            
        return int(pred), confidence

    def _save(self):
        # Save model with learning history
        model_data = {
            'pipeline': self.pipeline,
            'cv_accuracy': self.cv_accuracy,
            'training_history': self.training_history,
            'feature_importance': self.feature_importance,
            'samples_added': self.samples_added,
            'retraining_count': self.retraining_count
        }
        joblib.dump(model_data, MODEL_PATH)

    def _load(self):
        if os.path.exists(MODEL_PATH):
            try:
                loaded = joblib.load(MODEL_PATH)
                if isinstance(loaded, dict):
                    # New format with learning history
                    self.pipeline = loaded['pipeline']
                    self.cv_accuracy = loaded.get('cv_accuracy', 0.0)
                    self.training_history = loaded.get('training_history', [])
                    self.feature_importance = loaded.get('feature_importance', None)
                    self.samples_added = loaded.get('samples_added', 0)
                    self.retraining_count = loaded.get('retraining_count', 0)
                elif isinstance(loaded, tuple):
                    # Legacy tuple format
                    self.pipeline, self.cv_accuracy = loaded
                else:
                    # Very old format
                    self.pipeline = loaded
                    
                self.trained = True
                print(f"🧠 [Model] Loaded existing model. CV accuracy: {self.cv_accuracy:.3f} | Retrainings: {self.retraining_count}")
                
                if self.feature_importance:
                    print("🔍 [Model] Top 3 features:", [f"{name}({imp:.3f})" for name, imp in self.feature_importance[:3]])
                    
            except Exception as e:
                print(f"❌ [Model] Failed to load model: {e}")
