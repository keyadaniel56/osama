"""
ML model for Rise/Fall prediction using Random Forest.
Includes cross-validation and confidence scoring.
"""

import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from collections import deque


MODEL_PATH = "deriv_rise_fall_bot/model.pkl"
MIN_SAMPLES = 100
RETRAIN_CV_FOLDS = 3


class MLModel:
    def __init__(self):
        self.pipeline = self._build_pipeline()
        self.X_buffer = deque(maxlen=2000)
        self.y_buffer = deque(maxlen=2000)
        self.trained = False
        self.cv_accuracy = 0.0
        
        self._load()

    def _build_pipeline(self) -> Pipeline:
        return Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=300,
                max_depth=10,
                min_samples_leaf=5,
                min_samples_split=10,
                max_features='sqrt',
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ))
        ])

    def add_sample(self, features: np.ndarray, outcome: int):
        """
        Add training sample.
        outcome: 1 = RISE (price went up), 0 = FALL (price went down)
        """
        self.X_buffer.append(features)
        self.y_buffer.append(outcome)

    def train(self) -> bool:
        if len(self.X_buffer) < MIN_SAMPLES:
            return False
        
        X = np.array(self.X_buffer)
        y = np.array(self.y_buffer)
        
        if len(np.unique(y)) < 2:
            return False

        try:
            scores = cross_val_score(self._build_pipeline(), X, y,
                                     cv=RETRAIN_CV_FOLDS, scoring="accuracy", n_jobs=-1)
            self.cv_accuracy = float(np.mean(scores))
            print(f"🧠 [Model] CV accuracy: {self.cv_accuracy:.3f} (±{np.std(scores):.3f})")
        except Exception as e:
            print(f"❌ [Model] CV failed: {e}")
            self.cv_accuracy = 0.0

        self.pipeline.fit(X, y)
        self.trained = True
        self._save()
        return True

    def predict(self, features: np.ndarray) -> tuple[int, float]:
        """
        Returns (predicted_class, confidence).
        predicted_class: 1 = RISE, 0 = FALL, -1 = no prediction
        """
        if not self.trained:
            return -1, 0.0
        
        if self.cv_accuracy > 0 and self.cv_accuracy < 0.55:
            return -1, 0.0
        
        X = features.reshape(1, -1)
        pred = self.pipeline.predict(X)[0]
        proba = self.pipeline.predict_proba(X)[0]
        confidence = float(np.max(proba))
        
        if confidence < 0.60:
            return -1, 0.0
            
        return int(pred), confidence

    def _save(self):
        joblib.dump((self.pipeline, self.cv_accuracy), MODEL_PATH)

    def _load(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.pipeline, self.cv_accuracy = joblib.load(MODEL_PATH)
                self.trained = True
                print(f"🧠 [Model] Loaded. CV accuracy: {self.cv_accuracy:.3f}")
            except Exception as e:
                print(f"❌ [Model] Failed to load: {e}")
