"""
anomaly.py
----------
Simple statistical anomaly detector for IoT sensor readings.
Uses IQR + z-score on a rolling window — no ML dependency.
Production-ready: handles cold start (< 10 readings) gracefully.
"""

import math
from collections import deque


SENSOR_LIMITS = {
    'soil':     (0,   100),
    'temp':     (-10, 60),
    'humidity': (0,   100),
    'light':    (0,   150000),
}

OPTIMAL = {
    'soil':     (50, 80),
    'temp':     (18, 30),
    'humidity': (50, 80),
    'light':    (300, 700),
}

WINDOW = 30          # rolling window size
Z_THRESHOLD = 3.0    # z-score beyond which a reading is anomalous
IQR_MULTIPLIER = 2.0 # IQR fence multiplier


class AnomalyDetector:

    def __init__(self, window: int = WINDOW):
        self._window = window
        self._buffers: dict[str, deque] = {
            k: deque(maxlen=window)
            for k in SENSOR_LIMITS
        }

    # ── public ────────────────────────────────────────────────────

    def update(self, reading: dict):
        """Push a new reading into the rolling buffers."""
        for key in SENSOR_LIMITS:
            val = reading.get(key)
            if val is not None:
                try:
                    self._buffers[key].append(float(val))
                except (ValueError, TypeError):
                    pass

    def check(self, reading: dict) -> dict:
        """
        Check a reading for anomalies.
        Returns:
            {
              'has_anomaly': bool,
              'anomalies': [
                  {
                    'sensor': str,
                    'value': float,
                    'reason': str,        # 'out_of_range' | 'z_score' | 'iqr'
                    'severity': str,      # 'warning' | 'critical'
                    'message': str,
                  }, ...
              ]
            }
        """
        anomalies = []

        for key, (hard_min, hard_max) in SENSOR_LIMITS.items():
            val = reading.get(key)
            if val is None:
                continue
            try:
                val = float(val)
            except (ValueError, TypeError):
                continue

            # 1. Hard limits — always check
            if val < hard_min or val > hard_max:
                anomalies.append({
                    'sensor':   key,
                    'value':    val,
                    'reason':   'out_of_range',
                    'severity': 'critical',
                    'message':  f'{key} value {val} is outside physical limits [{hard_min}, {hard_max}]',
                })
                continue

            buf = list(self._buffers[key])
            if len(buf) < 5:
                # not enough history — skip statistical checks
                continue

            # 2. Z-score check
            mean = sum(buf) / len(buf)
            variance = sum((x - mean) ** 2 for x in buf) / len(buf)
            std = math.sqrt(variance) if variance > 0 else 0

            if std > 0:
                z = abs(val - mean) / std
                if z > Z_THRESHOLD:
                    anomalies.append({
                        'sensor':   key,
                        'value':    val,
                        'reason':   'z_score',
                        'severity': 'warning' if z < Z_THRESHOLD * 1.5 else 'critical',
                        'message':  f'{key} is {z:.1f}σ from recent mean ({mean:.1f})',
                    })
                    continue

            # 3. IQR check
            sorted_buf = sorted(buf)
            n = len(sorted_buf)
            q1 = sorted_buf[n // 4]
            q3 = sorted_buf[(3 * n) // 4]
            iqr = q3 - q1
            if iqr > 0:
                lo_fence = q1 - IQR_MULTIPLIER * iqr
                hi_fence = q3 + IQR_MULTIPLIER * iqr
                if val < lo_fence or val > hi_fence:
                    anomalies.append({
                        'sensor':   key,
                        'value':    val,
                        'reason':   'iqr',
                        'severity': 'warning',
                        'message':  f'{key} ({val}) outside IQR fence [{lo_fence:.1f}, {hi_fence:.1f}]',
                    })

        return {
            'has_anomaly': len(anomalies) > 0,
            'anomalies':   anomalies,
        }

    def get_stats(self) -> dict:
        """Return current rolling stats for all sensors — useful for the history page."""
        stats = {}
        for key in SENSOR_LIMITS:
            buf = list(self._buffers[key])
            if not buf:
                stats[key] = {'count': 0}
                continue
            mean = sum(buf) / len(buf)
            variance = sum((x - mean) ** 2 for x in buf) / len(buf)
            std = math.sqrt(variance) if variance > 0 else 0
            stats[key] = {
                'count': len(buf),
                'mean':  round(mean, 2),
                'std':   round(std, 2),
                'min':   round(min(buf), 2),
                'max':   round(max(buf), 2),
            }
        return stats
