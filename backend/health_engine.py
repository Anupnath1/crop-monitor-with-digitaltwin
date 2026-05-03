class HealthEngine:
    OPTIMAL = {
        'moisture':    {'min': 50, 'max': 80},
        'temperature': {'min': 18, 'max': 30},
        'humidity':    {'min': 50, 'max': 80},
        'light':       {'min': 300, 'max': 700},
    }
    WEIGHTS = {
        'moisture':    0.40,
        'temperature': 0.25,
        'humidity':    0.20,
        'light':       0.15,
    }
    def _score_param(self, value, param):
        lo = self.OPTIMAL[param]['min']
        hi = self.OPTIMAL[param]['max']
        if lo <= value <= hi:
            return 100.0
        if value < lo:
            deviation = lo - value
            worst = lo
        else:
            deviation = value - hi
            worst = (100 - hi) if param != 'light' else (1000 - hi)
        if worst == 0:
            return 0.0
        return max(0.0, 100.0 - min(deviation / worst, 1.0) * 100)
    def compute_health(self, moisture, temperature, humidity, light):
        scores = {
            'moisture':    self._score_param(moisture,    'moisture'),
            'temperature': self._score_param(temperature, 'temperature'),
            'humidity':    self._score_param(humidity,    'humidity'),
            'light':       self._score_param(light,       'light'),
        }
        return round(sum(scores[k] * self.WEIGHTS[k] for k in scores), 2)
    def health_label(self, score):
        if score >= 75: return 'Healthy'
        if score >= 50: return 'Moderate'
        return 'Critical'
    def health_color(self, score):
        if score >= 75: return '#4CAF50'
        if score >= 50: return '#FF9800'
        return '#F44336'
    def explain(self, moisture, temperature, humidity, light):
        OPT = self.OPTIMAL
        issues = []
        if moisture < OPT['moisture']['min']:
            issues.append(('low moisture', 0.40, 'critical' if moisture < 30 else 'warn'))
        elif moisture > OPT['moisture']['max']:
            issues.append(('excess moisture', 0.40, 'warn'))
        if temperature > OPT['temperature']['max']:
            issues.append(('high temperature', 0.25, 'critical' if temperature > 38 else 'warn'))
        elif temperature < OPT['temperature']['min']:
            issues.append(('low temperature', 0.25, 'warn'))
        if humidity < OPT['humidity']['min']:
            issues.append(('low humidity', 0.20, 'warn'))
        elif humidity > OPT['humidity']['max']:
            issues.append(('excess humidity', 0.20, 'warn'))
        if light < OPT['light']['min']:
            issues.append(('low light', 0.15, 'critical' if light < 100 else 'warn'))
        elif light > OPT['light']['max']:
            issues.append(('excess light', 0.15, 'warn'))
        if not issues:
            return 'All conditions optimal → plant is healthy'
        issues.sort(key=lambda x: (0 if x[2] == 'critical' else 1, -x[1]))
        top = [i[0] for i in issues[:2]]
        outcomes = {
            ('high temperature', 'low moisture'): 'heat stress',
            ('low moisture', 'high temperature'): 'heat stress',
            ('low moisture',):     'drought stress',
            ('high temperature',): 'heat stress',
            ('low light',):        'poor photosynthesis',
            ('excess moisture',):  'waterlogging risk',
            ('low humidity',):     'transpiration stress',
            ('excess humidity',):  'fungal disease risk',
            ('low temperature',):  'cold stress',
            ('excess light',):     'light burn risk',
        }
        key2 = tuple(sorted(top[:2])) if len(top) >= 2 else (top[0],)
        key1 = (top[0],)
        outcome = outcomes.get(tuple(top[:2])) or outcomes.get(key2) or outcomes.get(key1, 'plant stress')
        if len(top) == 1:
            return f'{top[0].capitalize()} → {outcome}'
        return f'{top[0].capitalize()} + {top[1]} → {outcome}'