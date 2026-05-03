# 🌱 AgroTwin — Smart Agriculture Digital Twin

A real-time digital twin where IoT sensor data is collected via ESP32, stored in Firebase,
future conditions are predicted using a multi-output Random Forest model with user-defined
time horizons, and irrigation is intelligently simulated and visualised through a 3D plant model.

---

## How to Run
python start.py

## System Architecture

```
ESP32 Sensors
    │
    ▼
Firebase Realtime DB  ◄──────────────────────────────────┐
    │                                                     │
    ▼                                                     │
Flask Backend                                            │
  ├── feature_engineering.py  (lag + time features)      │
  ├── train_model.py           (Random Forest training)   │
  ├── predict.py               (multi-output inference)   │
  ├── health_engine.py         (weighted health score)    │
  ├── irrigation_engine.py     (irrigation decision)      │
  └── recommendation_engine.py (action generation)        │
    │                                                     │
    ▼                                                     │
Frontend Dashboard  ──── writes predictions + health ────┘
  ├── Three.js 3D plant (colour = health)
  ├── Chart.js realtime + prediction charts
  └── Firebase SDK live listener
```

---

## Project Structure

```
smart-agri-twin/
├── backend/
│   ├── app.py                   Flask API server
│   ├── firebase_service.py      Firebase read/write
│   ├── health_engine.py         Plant health scoring
│   ├── irrigation_engine.py     Irrigation logic + pump simulation
│   └── recommendation_engine.py Human-readable action recommendations
│
├── ml/
│   ├── train_model.py           Trains MultiOutput RandomForest, saves model.pkl
│   ├── predict.py               Auto-regressive multi-step prediction
│   └── feature_engineering.py  Lag features, rolling means, time features
│
├── frontend/
│   ├── index.html               Dashboard layout
│   ├── css/style.css            Dark agri-industrial theme
│   └── js/
│       ├── dashboard.js         Central orchestrator, realtime chart
│       ├── firebase_listener.js Firebase subscription → DOM events
│       ├── three_scene.js       Three.js 3D plant, colour by health
│       ├── prediction.js        Prediction UI, chart, API calls
│       └── irrigation.js        Pump simulation UI, recommendations
│
├── config/
│   ├── firebase_config.js       Frontend Firebase SDK config (edit this!)
│   └── firebase_admin.json      Backend service account (replace with yours!)
│
├── esp32/
│   └── sensor_upload.ino        Arduino sketch for ESP32 sensor upload
│
├── assets/
│   └── plant.glb                (optional) 3D plant model from Blender
│
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Firebase Setup

1. Create a project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable **Realtime Database** (start in test mode for development)
3. Enable **Anonymous Authentication** (for ESP32)
4. Go to **Project Settings → Service Accounts → Generate new private key**
   → Save as `config/firebase_admin.json`
5. Go to **Project Settings → Your apps → SDK setup**
   → Copy config into `config/firebase_config.js`

### 2. Backend

```bash
cd smart-agri-twin
pip install -r requirements.txt

# Set environment variables
export FIREBASE_DB_URL="https://your-project-default-rtdb.firebaseio.com"

# Start Flask server
cd backend
python app.py
```

Server starts on `http://localhost:5000`

### 3. Train the Model

Before using predictions you need data in Firebase, OR use the synthetic data generator:

```bash
cd ml
python train_model.py   # trains on 300 synthetic samples, saves model.pkl
```

Or push real data first via the **⚡ Simulate Sensor** button in the dashboard,
then click **🧠 Train Model**.

### 4. Frontend

Serve the frontend folder with any static server:

```bash
# Option A: Python
cd frontend
python -m http.server 8080

# Option B: VS Code Live Server extension
# Option C: npx serve frontend
```

Open `http://localhost:8080` in your browser.

### 5. ESP32

1. Install [Arduino IDE](https://www.arduino.cc/en/software)
2. Add ESP32 board support
3. Install libraries: `Firebase ESP Client`, `DHT sensor library`, `Adafruit Unified Sensor`
4. Edit `esp32/sensor_upload.ino`:
   - Set `WIFI_SSID`, `WIFI_PASS`
   - Set `API_KEY`, `DATABASE_URL`
5. Flash to your ESP32

---

## API Reference

| Method | Endpoint             | Body                   | Description                        |
|--------|----------------------|------------------------|------------------------------------|
| POST   | `/train_model`       | —                      | Train Random Forest on Firebase data |
| POST   | `/predict`           | `{ "hours": 3 }`       | Predict all sensors + health score |
| GET    | `/get_health`        | —                      | Current health score from latest data |
| POST   | `/get_recommendation`| `{ "hours": 3 }`       | Irrigation recommendation          |
| POST   | `/simulate_irrigation`| `{ "water_liters": 2 }`| Simulate pump cycle                |
| POST   | `/sync_firebase`     | —                      | Sync health score to Firebase      |
| POST   | `/simulate_sensor`   | —                      | Push fake sensor data (demo/test)  |

---

## Health Score Formula

```
health = 0.40 × moisture_score
       + 0.25 × temperature_score
       + 0.20 × humidity_score
       + 0.15 × light_score

Each sub-score: 100 if within optimal range, decreasing linearly outside it.

Optimal ranges:
  Moisture:    50–80%
  Temperature: 18–30°C
  Humidity:    50–80%
  Light:       300–700 lux
```

---

## Plant Health Colour Mapping

| Score | Colour | Status   |
|-------|--------|----------|
| ≥ 75  | 🟢 Green  | Healthy  |
| 50–75 | 🟡 Yellow | Moderate |
| < 50  | 🔴 Red    | Critical |

---

## Prediction Features

| Feature      | Description                         |
|--------------|-------------------------------------|
| `soil_t1-3`  | Soil moisture at t-1, t-2, t-3      |
| `temp_t1`    | Temperature at t-1                  |
| `humidity_t1`| Humidity at t-1                     |
| `light_t1`   | Light at t-1                        |
| `soil_roll3` | 3-reading rolling mean for moisture |
| `temp_roll3` | 3-reading rolling mean for temp     |
| `hour`       | Hour of day (0–23)                  |
| `day_of_week`| Day of week (0=Mon … 6=Sun)         |

---

## Irrigation Decision Logic

```python
if predicted_moisture < 45%  OR  predicted_health < 55:
    irrigation_needed = True
    water_needed = (70 - predicted_moisture) × field_area_m²
    runtime_min  = water_needed / 2.0 L/min
```

---

## Adding a Custom 3D Plant Model

1. Create a plant model in Blender and export as `.glb`
2. Place it at `assets/plant.glb`
3. The `three_scene.js` will auto-load it via `GLTFLoader`
   (make sure to include the GLTFLoader CDN script in `index.html`)

```html
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
```

---

## Environment Variables

| Variable           | Description                          | Default                          |
|--------------------|--------------------------------------|----------------------------------|
| `FIREBASE_DB_URL`  | Firebase Realtime Database URL       | `https://your-project-rtdb...`   |
| `PORT`             | Flask server port                    | `5000`                           |

---

## Tech Stack

| Layer     | Technology                   |
|-----------|------------------------------|
| IoT       | ESP32 + DHT22 + Capacitive moisture sensor |
| Database  | Firebase Realtime Database   |
| Backend   | Python + Flask               |
| ML        | scikit-learn RandomForest (MultiOutputRegressor) |
| 3D        | Three.js (procedural or .glb plant) |
| Charts    | Chart.js                     |
| Frontend  | Vanilla HTML/CSS/JS          |

---

## License

MIT — free to use, modify, and deploy.
