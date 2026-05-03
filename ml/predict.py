import os
import pickle
import numpy as np
from datetime import datetime
from feature_engineering import build_prediction_row, get_feature_columns, get_target_columns
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model.pkl')
class Predictor:
    def __init__(self):
        self._model = None
        self._feature_cols = None
        self._target_cols = None
    def _load(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                "model.pkl not found. Call /train_model first or run ml/train_model.py directly."
            )
        with open(MODEL_PATH, 'rb') as f:
            payload = pickle.load(f)
        self._model = payload['model']
        self._feature_cols = payload['feature_cols']
        self._target_cols = payload['target_cols']
    def predict(self, recent_readings: list, hours: float) -> dict:
        if self._model is None:
            self._load()
        steps = max(1, int(round(hours)))
        working_readings = list(recent_readings)  
        pred_dict = {}
        for step in range(steps):
            row_df = build_prediction_row(working_readings)
            for col in self._feature_cols:
                if col not in row_df.columns:
                    row_df[col] = 0.0
            X = row_df[self._feature_cols].values
            y_pred = self._model.predict(X)[0]  
            pred_dict = {
                tgt: round(float(y_pred[i]), 2)
                for i, tgt in enumerate(self._target_cols)
            }
            working_readings.append({
                'soil': pred_dict.get('soil', 50),
                'temp': pred_dict.get('temp', 25),
                'humidity': pred_dict.get('humidity', 60),
                'light': pred_dict.get('light', 400),
                'timestamp': f'pred_step_{step}',
            })
        pred_dict['soil'] = max(0, min(100, pred_dict.get('soil', 50)))
        pred_dict['temp'] = max(-10, min(60, pred_dict.get('temp', 25)))
        pred_dict['humidity'] = max(0, min(100, pred_dict.get('humidity', 60)))
        pred_dict['light'] = max(0, min(1200, pred_dict.get('light', 400)))
        return pred_dict