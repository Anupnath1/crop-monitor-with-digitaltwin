import pandas as pd
import numpy as np
from datetime import datetime
def build_features(readings: list, lag: int = 3) -> pd.DataFrame:
    df = pd.DataFrame(readings)
    for col in ['soil', 'temp', 'humidity', 'light']:
        if col not in df.columns:
            df[col] = 50.0  
    if 'timestamp' in df.columns:
        df['dt'] = pd.to_datetime(df['timestamp'], format='%Y%m%d_%H%M%S', errors='coerce')
    else:
        df['dt'] = pd.Timestamp.now()
    df['hour'] = df['dt'].dt.hour
    df['day_of_week'] = df['dt'].dt.dayofweek
    for i in range(1, lag + 1):
        df[f'soil_t{i}'] = df['soil'].shift(i)
    df['temp_t1'] = df['temp'].shift(1)
    df['humidity_t1'] = df['humidity'].shift(1)
    df['light_t1'] = df['light'].shift(1)
    df['soil_roll3'] = df['soil'].rolling(3, min_periods=1).mean()
    df['temp_roll3'] = df['temp'].rolling(3, min_periods=1).mean()
    lag_cols = ['soil_t1', 'soil_t2', 'soil_t3', 'temp_t1', 'humidity_t1', 'light_t1']
    df = df.dropna(subset=lag_cols).reset_index(drop=True)
    return df
def get_feature_columns() -> list:
    return [
        'soil_t1', 'soil_t2', 'soil_t3',
        'temp_t1', 'humidity_t1', 'light_t1',
        'soil_roll3', 'temp_roll3',
        'hour', 'day_of_week',
    ]
def get_target_columns() -> list:
    return ['soil', 'temp', 'humidity', 'light']
def build_prediction_row(recent_readings: list) -> pd.DataFrame:
    df = build_features(recent_readings)
    if df.empty:
        last = recent_readings[-1] if recent_readings else {}
        row = {col: last.get(col.split('_')[0], 50.0) for col in get_feature_columns()}
        return pd.DataFrame([row])
    feature_cols = get_feature_columns()
    available = [c for c in feature_cols if c in df.columns]
    return df[available].iloc[[-1]]