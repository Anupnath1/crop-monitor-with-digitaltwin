import os
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))

class FirebaseService:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'firebase_admin.json')
        db_url = os.environ.get('FIREBASE_DB_URL', '')
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Firebase admin credentials not found at {config_path}\n"
                "Download from: Firebase Console → Project Settings → Service Accounts → Generate new private key"
            )
        with open(config_path) as f:
            cfg = json.load(f)
        if cfg.get('project_id', '').startswith('your-') or not db_url:
            raise ValueError(
                "Firebase not configured.\n"
                "1. Replace config/firebase_admin.json with your real service account JSON.\n"
                "2. Set environment variable: export FIREBASE_DB_URL=https://YOUR_PROJECT-default-rtdb.firebaseio.com"
            )
        if not firebase_admin._apps:
            cred = credentials.Certificate(config_path)
            firebase_admin.initialize_app(cred, {'databaseURL': db_url})
            self.current_ref     = db.reference('farm/current')
            self.sensors_ref     = db.reference('farm/sensors')
            self.predictions_ref = db.reference('predictions')
            self.irrigation_ref  = db.reference('irrigation')
            self.health_ref      = db.reference('health')
    def get_latest_reading(self):
        data = self.current_ref.get()
        if not data:
            return None
        return {
            'soil':      data.get('soil_moisture'),
            'temp':      data.get('temperature'),
            'humidity':  data.get('humidity'),
            'light':     data.get('light_intensity'),
            'timestamp': data.get('timestamp'),
        }
    def get_recent_readings(self, n=10):
        data = self.sensors_ref.order_by_key().limit_to_last(n).get()
        if not data:
            latest = self.get_latest_reading()
            return [latest] * 3 if latest else []
        readings = []
        for entry in data.values():
            readings.append({
                'soil':      entry.get('soil_moisture'),
                'temp':      entry.get('temperature'),
                'humidity':  entry.get('humidity'),
                'light':     entry.get('light_intensity'),
                'timestamp': entry.get('timestamp'),
            })
        return readings
    def get_historical_data(self, limit=500):
        data = self.sensors_ref.order_by_key().limit_to_last(limit).get()
        if not data:
            return []
        return list(data.values())
    def write_sensor(self, reading: dict):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.sensors_ref.child(ts).set({**reading, 'timestamp': ts})
    def write_predictions(self, predictions: dict, hours: float):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.predictions_ref.child(ts).set({**predictions, 'horizon_hours': hours, 'timestamp': ts})
    def write_health(self, score: float):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.health_ref.set({'score': score, 'timestamp': ts})
    def write_irrigation(self, irrigation_data: dict):
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.irrigation_ref.set({**irrigation_data, 'timestamp': ts})