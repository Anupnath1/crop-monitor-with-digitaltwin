import os
import sys
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
sys.path.insert(0, os.path.dirname(__file__))
from feature_engineering import build_features, get_feature_columns, get_target_columns
MODEL_PATH   = os.path.join(os.path.dirname(__file__), 'model.pkl')
DATASET_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'sensor_data.csv')
COLUMN_MAP = {
    'timestamp': 'timestamp',
    'soil_moisture':      'soil',       
    'temperature':      'temp',       
    'humidity':  'humidity',   
    'light_intensity':     'light',      
}
class ModelTrainer:
    def load_csv(self) -> list:
        path = os.path.abspath(DATASET_PATH)
        if not os.path.exists(path):
            return None
        print(f"[ModelTrainer] Reading dataset: {path}")
        df = pd.read_csv(path)
        rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns and k != v}
        if rename:
            df = df.rename(columns=rename)
            print(f"[ModelTrainer] Renamed columns: {rename}")
        required = ['soil', 'temp', 'humidity', 'light']
        missing  = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"CSV is missing columns: {missing}\n"
                f"CSV has: {list(df.columns)}\n"
                f"Edit COLUMN_MAP in ml/train_model.py to fix this."
            )
        if 'timestamp' not in df.columns:
            df['timestamp'] = pd.date_range(
                start='2024-01-01', periods=len(df), freq='1H'
            ).strftime('%Y%m%d_%H%M%S')
        df = df.dropna(subset=required)
        print(f"[ModelTrainer] CSV loaded: {len(df)} rows")
        return df[required + ['timestamp']].to_dict('records')
    def train(self, readings: list) -> dict:
        df = build_features(readings)
        feature_cols = get_feature_columns()
        target_cols  = get_target_columns()
        available_features = [c for c in feature_cols if c in df.columns]
        available_targets  = [c for c in target_cols  if c in df.columns]
        if len(df) < 10:
            raise ValueError(
                f"Only {len(df)} usable rows after feature engineering. "
                "Need at least 10. Check your CSV has enough rows."
            )
        X = df[available_features].values
        y = df[available_targets].values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        print(f"[ModelTrainer] Training on {len(X_train)} samples…")
        model = MultiOutputRegressor(
            RandomForestRegressor(
                n_estimators=150,
                max_depth=12,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1,
            )
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        mae    = mean_absolute_error(y_test, y_pred, multioutput='raw_values')
        r2     = r2_score(y_test, y_pred, multioutput='raw_values')
        metrics = {
            'n_samples': len(df),
            'n_train':   len(X_train),
            'n_test':    len(X_test),
            'features':  available_features,
            'targets':   available_targets,
            'data_source': getattr(self, '_source', 'unknown'),
        }
        for i, tgt in enumerate(available_targets):
            metrics[f'mae_{tgt}'] = round(float(mae[i]), 3)
            metrics[f'r2_{tgt}']  = round(float(r2[i]),  3)
        payload = {
            'model':        model,
            'feature_cols': available_features,
            'target_cols':  available_targets,
        }
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(payload, f)
        print(f"[ModelTrainer] ✓ Saved → {MODEL_PATH}")
        print(f"[ModelTrainer] Metrics: {metrics}")
        return metrics
def generate_synthetic_data(n: int = 300) -> list:
    import math, random
    readings = []
    for i in range(n):
        hour = i % 24
        soil     = 65 + 15 * math.sin(i / 12)       + random.gauss(0, 3)
        temp     = 25 +  8 * math.sin(math.pi * hour / 12 - 1) + random.gauss(0, 1)
        humidity = 62 + 10 * math.cos(i / 8)         + random.gauss(0, 2)
        light    = max(0, 500 * max(0, math.sin(math.pi * hour / 12)) + random.gauss(0, 30))
        day      = i // 24
        readings.append({
            'soil':      round(soil,     1),
            'temp':      round(temp,     1),
            'humidity':  round(humidity, 1),
            'light':     round(light,    0),
            'timestamp': f'2024{day:03d}_{hour:02d}0000',
        })
    return readings
if __name__ == '__main__':
    trainer = ModelTrainer()
    data = trainer.load_csv()
    if data:
        trainer._source = 'csv'
        print(f"[ModelTrainer] Using CSV dataset ({len(data)} rows)")
    else:
        trainer._source = 'synthetic'
        print("[ModelTrainer] No CSV found → using synthetic data")
        print(f"[ModelTrainer] To use real data: place your CSV at data/sensor_data.csv")
        data = generate_synthetic_data(300)
    metrics = trainer.train(data)
    print("\n[ModelTrainer] ═══ Training complete ═══")
    for k, v in metrics.items():
        if k not in ('features', 'targets'):
            print(f"  {k:20s} = {v}")