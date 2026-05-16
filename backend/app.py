"""
app.py - Production-ready Flask API
Changes from original:
  - ROOT bug fixed in firebase_service (that file patched separately)
  - Anomaly detection on every /get_health call
  - Input validation on all POST endpoints
  - Rate limiting on /simulate_irrigation (10 calls / 5 min)
  - /predict_timeline fixed: only soil is ML-predicted, others labelled as current
  - /history endpoint added for data log page
  - /anomaly_stats endpoint added
  - Consistent error shape: {success, error}
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys, time, math, random
from datetime import datetime
from functools import wraps
from collections import defaultdict

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ml'))

from health_engine         import HealthEngine
from irrigation_engine     import IrrigationEngine
from recommendation_engine import RecommendationEngine
from predict               import Predictor
from train_model           import ModelTrainer, generate_synthetic_data
from anomaly               import AnomalyDetector

app = Flask(__name__)
CORS(app)

health_engine         = HealthEngine()
irrigation_engine     = IrrigationEngine()
recommendation_engine = RecommendationEngine()
predictor             = Predictor()
anomaly_detector      = AnomalyDetector(window=30)

_firebase    = None
_rate_store  = defaultdict(list)


def _rate_limit(key, max_calls, window_seconds):
    now   = time.time()
    calls = [t for t in _rate_store[key] if now - t < window_seconds]
    _rate_store[key] = calls
    if len(calls) >= max_calls:
        return False
    _rate_store[key].append(now)
    return True


def err(msg, code=400, **kw):
    return jsonify({'success': False, 'error': msg, **kw}), code


def get_firebase():
    global _firebase
    if _firebase is None:
        from firebase_service import FirebaseService
        _firebase = FirebaseService()
    return _firebase


def firebase_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            get_firebase()
            return fn(*args, **kwargs)
        except (FileNotFoundError, ValueError) as e:
            return err(str(e), 503, setup_required=True)
        except Exception as e:
            return err(str(e), 500)
    return wrapper


def _validate_hours(body):
    hours = body.get('hours', 1)
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        return 0, "'hours' must be a number"
    if not (0.08 <= hours <= 24):
        return 0, "'hours' must be between 0.08 and 24"
    return hours, None


def _validate_sensor(data):
    ranges = {'soil':(0,100),'temp':(-20,60),'humidity':(0,100),'light':(0,150000)}
    for field, (lo, hi) in ranges.items():
        val = data.get(field)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            return f"'{field}' must be a number"
        if not (lo <= v <= hi):
            return f"'{field}' must be in [{lo}, {hi}], got {v}"
    return None


# ── Routes ────────────────────────────────────────────────────────

@app.route('/health_check', methods=['GET'])
def health_check():
    firebase_ok = False
    try:
        get_firebase(); firebase_ok = True
    except Exception:
        pass
    return jsonify({
        'status': 'ok', 'firebase': firebase_ok,
        'model':  os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'ml', 'model.pkl')),
        'timestamp': datetime.utcnow().isoformat(),
    })


@app.route('/train_model', methods=['POST'])
def train_model():
    try:
        trainer = ModelTrainer()
        df_raw  = trainer.load_csv()
        if df_raw is not None:
            trainer._source = 'csv'
        else:
            try:
                fb       = get_firebase()
                readings = fb.get_historical_data(limit=500)
                if readings and len(readings) >= 50:
                    import pandas as pd
                    df_raw = pd.DataFrame(readings)
                    df_raw = df_raw.rename(columns={'soil':'soil_moisture','temp':'temperature','light':'light_intensity'})
                    trainer._source = 'firebase'
                else:
                    raise ValueError('not enough data')
            except Exception:
                import pandas as pd
                synth  = generate_synthetic_data(1500)
                df_raw = pd.DataFrame(synth)
                df_raw = df_raw.rename(columns={'soil':'soil_moisture','temp':'temperature','light':'light_intensity'})
                trainer._source = 'synthetic'
        metrics = trainer.train(df_raw)
        return jsonify({'success': True, 'metrics': metrics})
    except Exception as e:
        return err(str(e), 500)


@app.route('/predict', methods=['POST'])
@firebase_required
def predict():
    body = request.get_json(silent=True) or {}
    hours, verr = _validate_hours(body)
    if verr: return err(verr)
    fb     = get_firebase()
    recent = fb.get_recent_readings(n=10)
    if not recent: return err('No recent sensor data.', 404)
    predictions = predictor.predict(recent, hours)
    predictions['health_score'] = health_engine.compute_health(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light'])
    predictions['explanation'] = health_engine.explain(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light'])
    fb.write_predictions(predictions, hours)
    return jsonify({'success': True, 'predictions': predictions, 'hours': hours})


@app.route('/get_health', methods=['GET'])
@firebase_required
def get_health():
    fb     = get_firebase()
    latest = fb.get_latest_reading()
    if not latest: return err('No sensor data in Firebase.', 404)
    soil = latest.get('soil') or 50; temp = latest.get('temp') or 25
    humidity = latest.get('humidity') or 60; light = latest.get('light') or 500
    anomaly_detector.update({'soil':soil,'temp':temp,'humidity':humidity,'light':light})
    anomaly_result = anomaly_detector.check({'soil':soil,'temp':temp,'humidity':humidity,'light':light})
    if anomaly_result['has_anomaly']:
        fb.write_anomaly(anomaly_result)
    score = health_engine.compute_health(soil, temp, humidity, light)
    return jsonify({
        'success': True, 'health_score': score,
        'label':   health_engine.health_label(score),
        'color':   health_engine.health_color(score),
        'explanation': health_engine.explain(soil, temp, humidity, light),
        'sensor_data': latest, 'anomaly': anomaly_result,
    })


@app.route('/get_recommendation', methods=['POST'])
@firebase_required
def get_recommendation():
    body = request.get_json(silent=True) or {}
    hours, verr = _validate_hours(body)
    if verr: return err(verr)
    fb     = get_firebase()
    recent = fb.get_recent_readings(n=10)
    if not recent: return err('No recent sensor data.', 404)
    predictions      = predictor.predict(recent, hours)
    predicted_health = health_engine.compute_health(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light'])
    predictions['health_score'] = predicted_health
    predictions['explanation']  = health_engine.explain(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light'])
    irrigation_data = irrigation_engine.compute_irrigation(predictions['soil'], predicted_health)
    recommendation  = recommendation_engine.generate(predicted_health, predictions['soil'], irrigation_data, hours)
    return jsonify({'success':True,'recommendation':recommendation,'irrigation':irrigation_data,'predictions':predictions})


@app.route('/simulate_irrigation', methods=['POST'])
@firebase_required
def simulate_irrigation():
    if not _rate_limit('irrigate', max_calls=10, window_seconds=300):
        return err('Too many irrigation requests. Wait a few minutes.', 429)
    body = request.get_json(silent=True) or {}
    try:
        water_liters = float(body.get('water_liters', 2.0))
    except (TypeError, ValueError):
        return err("'water_liters' must be a number")
    if not (0.1 <= water_liters <= 50):
        return err("'water_liters' must be between 0.1 and 50")
    fb = get_firebase()
    latest = fb.get_latest_reading()
    current_moisture = (latest.get('soil') or 40) if latest else 40
    simulation = irrigation_engine.simulate_pump(current_moisture, water_liters)
    fb.write_irrigation(simulation)
    return jsonify({'success': True, 'simulation': simulation})


@app.route('/sync_firebase', methods=['POST'])
@firebase_required
def sync_firebase():
    fb = get_firebase(); latest = fb.get_latest_reading()
    if not latest: return err('No data to sync.', 404)
    score = health_engine.compute_health(
        latest.get('soil') or 50, latest.get('temp') or 25,
        latest.get('humidity') or 60, latest.get('light') or 500)
    fb.write_health(score)
    return jsonify({'success': True, 'synced': True, 'health_score': score})


@app.route('/simulate_sensor', methods=['POST'])
@firebase_required
def simulate_sensor():
    fb   = get_firebase()
    hour = datetime.now().hour
    reading = {
        'soil':     round(max(0,min(100, random.uniform(30,85)+math.sin(hour/4)*10)), 1),
        'temp':     round(max(-10,min(60, random.uniform(20,38)+math.cos(hour/6)*3)), 1),
        'humidity': round(max(0,min(100,  random.uniform(40,90)+math.sin(hour/3)*5)), 1),
        'light':    round(max(0, random.uniform(100,900)*max(0.1,math.sin(math.pi*hour/12))), 0),
    }
    anomaly_detector.update(reading)
    fb.write_sensor(reading)
    return jsonify({'success': True, 'reading': reading})


@app.route('/whatif', methods=['POST'])
def whatif():
    body = request.get_json(silent=True) or {}
    verr = _validate_sensor(body)
    if verr: return err(verr)
    soil=float(body.get('soil',50)); temp=float(body.get('temp',25))
    humidity=float(body.get('humidity',60)); light=float(body.get('light',400))
    score      = health_engine.compute_health(soil, temp, humidity, light)
    irrigation = irrigation_engine.compute_irrigation(soil, score)
    soil_forecast = None
    try:
        fake = [{'soil':soil,'temp':temp,'humidity':humidity,'light':light,
                 'timestamp':datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}]*35
        result = predictor.predict(fake, hours=1.0)
        soil_forecast = {'soil_in_1h': result['soil'], 'all_horizons': result.get('all_horizons',{})}
    except Exception:
        pass
    return jsonify({
        'success':True,'health_score':score,
        'label':health_engine.health_label(score),'color':health_engine.health_color(score),
        'explanation':health_engine.explain(soil,temp,humidity,light),
        'irrigation':irrigation,'soil_forecast':soil_forecast,
    })


@app.route('/predict_timeline', methods=['GET'])
@firebase_required
def predict_timeline():
    fb     = get_firebase()
    recent = fb.get_recent_readings(n=10)
    if not recent: return err('No recent sensor data.', 404)
    current = recent[-1]
    steps   = []
    for i in range(11):
        hrs      = i * 0.5
        soil_val = (current.get('soil') or 50) if hrs == 0 else predictor.predict(recent, hrs)['soil']
        score    = health_engine.compute_health(soil_val, current.get('temp') or 25,
                                                current.get('humidity') or 60, current.get('light') or 400)
        irr      = irrigation_engine.compute_irrigation(soil_val, score)
        steps.append({
            'hours': hrs, 'soil': round(soil_val, 1),
            'temp':     current.get('temp') or 25,
            'humidity': current.get('humidity') or 60,
            'light':    current.get('light') or 400,
            'health_score': score,
            'explanation': health_engine.explain(soil_val, current.get('temp') or 25,
                                                  current.get('humidity') or 60, current.get('light') or 400),
            'irrigation_needed': irr['irrigation_needed'],
            'soil_is_predicted': hrs > 0,
        })
    return jsonify({'success': True, 'timeline': steps})


@app.route('/history', methods=['GET'])
@firebase_required
def history():
    try:
        limit = max(10, min(500, int(request.args.get('limit', 100))))
    except (TypeError, ValueError):
        limit = 100
    fb   = get_firebase()
    data = fb.get_historical_data(limit=limit)
    if not data:
        return jsonify({'success': True, 'readings': [], 'count': 0})
    enriched = []
    for r in data:
        soil=r.get('soil') or 50; temp=r.get('temp') or 25
        humidity=r.get('humidity') or 60; light=r.get('light') or 400
        enriched.append({**r, 'health_score': health_engine.compute_health(soil,temp,humidity,light)})
    return jsonify({'success': True, 'readings': enriched, 'count': len(enriched)})


@app.route('/anomaly_stats', methods=['GET'])
def anomaly_stats():
    return jsonify({'success': True, 'stats': anomaly_detector.get_stats()})


if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print(f"[AgroTwin] Starting on port {port}  debug={debug}")
    app.run(debug=debug, host='0.0.0.0', port=port)
