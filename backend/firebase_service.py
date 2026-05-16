"""
firebase_service.py
-------------------
Firebase Realtime Database interface.
Fixes: ROOT was undefined in original. Now uses __file__-relative path.
"""

import os
import json
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

# Fix: ROOT was never defined in the original — crashed on import
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, '.env'))


class FirebaseService:

    def __init__(self):
        config_path = os.path.join(ROOT, 'config', 'firebase_admin.json')
        db_url = os.environ.get('FIREBASE_DB_URL', '')

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Firebase admin credentials not found at {config_path}\n"
                "Download from: Firebase Console → Project Settings → "
                "Service Accounts → Generate new private key"
            )

        with open(config_path) as f:
            cfg = json.load(f)

        if cfg.get('project_id', '').startswith('your-') or not db_url:
            raise ValueError(
                "Firebase not configured.\n"
                "1. Replace config/firebase_admin.json with your real service account JSON.\n"
                "2. Set FIREBASE_DB_URL in your .env file:\n"
                "   FIREBASE_DB_URL=https://YOUR_PROJECT-default-rtdb.firebaseio.com"
            )

        if not firebase_admin._apps:
            cred = credentials.Certificate(config_path)
            firebase_admin.initialize_app(cred, {'databaseURL': db_url})

        self.current_ref     = db.reference('farm/current')
        self.sensors_ref     = db.reference('farm/sensors')
        self.predictions_ref = db.reference('predictions')
        self.irrigation_ref  = db.reference('irrigation')
        self.health_ref      = db.reference('health')
        self.anomaly_ref     = db.reference('anomalies')

    # ── reads ─────────────────────────────────────────────────────

    def get_latest_reading(self) -> dict | None:
        data = self.current_ref.get()
        if not data:
            return None
        return self._normalize(data)

    def get_recent_readings(self, n: int = 10) -> list:
        data = self.sensors_ref.order_by_key().limit_to_last(n).get()
        if not data:
            latest = self.get_latest_reading()
            return [latest] * 3 if latest else []
        return [self._normalize(v) for v in data.values()]

    def get_historical_data(self, limit: int = 500) -> list:
        data = self.sensors_ref.order_by_key().limit_to_last(limit).get()
        if not data:
            return []
        return [self._normalize(v) for v in data.values()]

    # ── writes ────────────────────────────────────────────────────

    def write_sensor(self, reading: dict):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        payload = {**reading, 'timestamp': ts}
        self.sensors_ref.child(ts).set(payload)
        self.current_ref.set({
            'soil_moisture':   reading.get('soil', 0),
            'temperature':     reading.get('temp', 0),
            'humidity':        reading.get('humidity', 0),
            'light_intensity': reading.get('light', 0),
            'timestamp':       ts,
        })

    def write_predictions(self, predictions: dict, hours: float):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.predictions_ref.child(ts).set(
            {**predictions, 'horizon_hours': hours, 'timestamp': ts}
        )

    def write_health(self, score: float):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.health_ref.set({'score': score, 'timestamp': ts})

    def write_irrigation(self, irrigation_data: dict):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.irrigation_ref.set({**irrigation_data, 'timestamp': ts})

    def write_anomaly(self, anomaly_result: dict):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.anomaly_ref.child(ts).set({**anomaly_result, 'timestamp': ts})

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _normalize(raw: dict) -> dict:
        """Map Firebase field names → internal field names."""
        return {
            'soil':      raw.get('soil_moisture') or raw.get('soil'),
            'temp':      raw.get('temperature')   or raw.get('temp'),
            'humidity':  raw.get('humidity'),
            'light':     raw.get('light_intensity') or raw.get('light'),
            'timestamp': raw.get('timestamp'),
        }
