from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ml'))

from health_engine import HealthEngine
from irrigation_engine import IrrigationEngine
from recommendation_engine import RecommendationEngine
from predict import Predictor
from train_model import ModelTrainer, generate_synthetic_data

app = Flask(__name__)
CORS(app)

health_engine         = HealthEngine()
irrigation_engine     = IrrigationEngine()
recommendation_engine = RecommendationEngine()
predictor             = Predictor()

_firebase = None

def get_firebase():
    global _firebase
    if _firebase is None:
        from firebase_service import FirebaseService
        _firebase = FirebaseService()
    return _firebase


def firebase_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            get_firebase()
            return fn(*args, **kwargs)
        except (FileNotFoundError, ValueError) as e:
            return jsonify({'success': False, 'error': str(e), 'setup_required': True}), 503
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return wrapper


@app.route('/health_check', methods=['GET'])
def health_check():
    firebase_ok = False
    try:
        get_firebase()
        firebase_ok = True
    except Exception:
        pass
    return jsonify({
        'status':     'ok',
        'firebase':   firebase_ok,
        'model':      os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'ml', 'model.pkl')),
    })


@app.route('/train_model', methods=['POST'])
def train_model():
    try:
        trainer = ModelTrainer()
        data = trainer.load_csv()
        if data:
            trainer._source = 'csv'
        else:
            try:
                fb = get_firebase()
                data = fb.get_historical_data(limit=500)
                if data and len(data) >= 20:
                    trainer._source = 'firebase'
                else:
                    raise ValueError('not enough firebase data')
            except Exception:
                data = generate_synthetic_data(300)
                trainer._source = 'synthetic'
        metrics = trainer.train(data)
        return jsonify({'success': True, 'metrics': metrics})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/predict', methods=['POST'])
@firebase_required
def predict():
    body  = request.get_json()
    hours = float(body.get('hours', 1))
    fb    = get_firebase()
    recent = fb.get_recent_readings(n=10)
    if not recent:
        return jsonify({'success': False, 'error': 'No recent sensor data in Firebase.'}), 400
    predictions = predictor.predict(recent, hours)
    predictions['health_score'] = health_engine.compute_health(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light']
    )
    predictions['explanation'] = health_engine.explain(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light']
    )
    fb.write_predictions(predictions, hours)
    return jsonify({'success': True, 'predictions': predictions, 'hours': hours})


@app.route('/get_health', methods=['GET'])
@firebase_required
def get_health():
    fb = get_firebase()
    latest = fb.get_latest_reading()
    if not latest:
        return jsonify({'success': False, 'error': 'No sensor data in Firebase. Push data from your ESP32 first.'}), 404
    soil     = latest.get('soil', 50)
    temp     = latest.get('temp', 25)
    humidity = latest.get('humidity', 60)
    light    = latest.get('light', 500)
    score    = health_engine.compute_health(soil, temp, humidity, light)
    return jsonify({
        'success':      True,
        'health_score': score,
        'label':        health_engine.health_label(score),
        'color':        health_engine.health_color(score),
        'explanation':  health_engine.explain(soil, temp, humidity, light),
        'sensor_data':  latest,
    })


@app.route('/get_recommendation', methods=['POST'])
@firebase_required
def get_recommendation():
    body  = request.get_json()
    hours = float(body.get('hours', 1))
    fb    = get_firebase()
    recent = fb.get_recent_readings(n=10)
    if not recent:
        return jsonify({'success': False, 'error': 'No recent sensor data.'}), 400
    predictions      = predictor.predict(recent, hours)
    predicted_health = health_engine.compute_health(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light']
    )
    predictions['health_score'] = predicted_health
    predictions['explanation']  = health_engine.explain(
        predictions['soil'], predictions['temp'], predictions['humidity'], predictions['light']
    )
    irrigation_data = irrigation_engine.compute_irrigation(predictions['soil'], predicted_health)
    recommendation  = recommendation_engine.generate(predicted_health, predictions['soil'], irrigation_data, hours)
    return jsonify({
        'success':        True,
        'recommendation': recommendation,
        'irrigation':     irrigation_data,
        'predictions':    predictions,
    })


@app.route('/simulate_irrigation', methods=['POST'])
@firebase_required
def simulate_irrigation():
    body         = request.get_json()
    water_liters = float(body.get('water_liters', 2.0))
    fb           = get_firebase()
    latest       = fb.get_latest_reading()
    current_moisture = latest.get('soil', 40) if latest else 40
    simulation   = irrigation_engine.simulate_pump(current_moisture, water_liters)
    fb.write_irrigation(simulation)
    return jsonify({'success': True, 'simulation': simulation})


@app.route('/sync_firebase', methods=['POST'])
@firebase_required
def sync_firebase():
    fb = get_firebase()
    latest = fb.get_latest_reading()
    if not latest:
        return jsonify({'success': False, 'error': 'No data to sync.'}), 400
    score = health_engine.compute_health(
        latest.get('soil', 50), latest.get('temp', 25),
        latest.get('humidity', 60), latest.get('light', 500)
    )
    fb.write_health(score)
    return jsonify({'success': True, 'synced': True, 'health_score': score})


@app.route('/simulate_sensor', methods=['POST'])
@firebase_required
def simulate_sensor():
    import random, math
    fb   = get_firebase()
    hour = datetime.now().hour
    reading = {
        'soil':     round(random.uniform(30, 85) + math.sin(hour / 4) * 10, 1),
        'temp':     round(random.uniform(20, 38) + math.cos(hour / 6) * 3,  1),
        'humidity': round(random.uniform(40, 90) + math.sin(hour / 3) * 5,  1),
        'light':    round(random.uniform(100, 900) * max(0.1, math.sin(math.pi * hour / 12)), 0),
    }
    fb.write_sensor(reading)
    return jsonify({'success': True, 'reading': reading})


@app.route('/whatif', methods=['POST'])
def whatif():
    try:
        body     = request.get_json()
        soil     = float(body.get('soil',     50))
        temp     = float(body.get('temp',     25))
        humidity = float(body.get('humidity', 60))
        light    = float(body.get('light',   400))
        score    = health_engine.compute_health(soil, temp, humidity, light)
        irrigation = irrigation_engine.compute_irrigation(soil, score)
        return jsonify({
            'success':      True,
            'health_score': score,
            'label':        health_engine.health_label(score),
            'color':        health_engine.health_color(score),
            'explanation':  health_engine.explain(soil, temp, humidity, light),
            'irrigation':   irrigation,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/predict_timeline', methods=['GET'])
@firebase_required
def predict_timeline():
    fb     = get_firebase()
    recent = fb.get_recent_readings(n=10)
    if not recent:
        return jsonify({'success': False, 'error': 'No recent sensor data.'}), 400
    steps = []
    for i in range(11):
        hrs = i * 0.5
        if hrs == 0:
            last = recent[-1]
            p = {'soil': last.get('soil', 50), 'temp': last.get('temp', 25),
                 'humidity': last.get('humidity', 60), 'light': last.get('light', 400)}
        else:
            p = predictor.predict(recent, hrs)
        score   = health_engine.compute_health(p['soil'], p['temp'], p['humidity'], p['light'])
        irr     = irrigation_engine.compute_irrigation(p['soil'], score)
        steps.append({
            'hours':             hrs,
            'soil':              round(p['soil'],     1),
            'temp':              round(p['temp'],     1),
            'humidity':          round(p['humidity'], 1),
            'light':             round(p['light'],    0),
            'health_score':      score,
            'explanation':       health_engine.explain(p['soil'], p['temp'], p['humidity'], p['light']),
            'irrigation_needed': irr['irrigation_needed'],
        })
    return jsonify({'success': True, 'timeline': steps})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
