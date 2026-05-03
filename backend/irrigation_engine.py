import math
class IrrigationEngine:
    MOISTURE_THRESHOLD = 35.0    
    HEALTH_THRESHOLD = 55.0      
    TARGET_MOISTURE = 70.0       
    FIELD_AREA_M2 = 1.0          
    FLOW_RATE_LPM = 2.0          
    def compute_irrigation(
        self,
        predicted_moisture: float,
        predicted_health: float
    ) -> dict:
        needed = (
            predicted_moisture < self.MOISTURE_THRESHOLD
            or predicted_health < self.HEALTH_THRESHOLD
        )
        moisture_deficit = max(0.0, self.TARGET_MOISTURE - predicted_moisture)
        water_needed_liters = round(moisture_deficit * self.FIELD_AREA_M2 * 1.0, 2)
        runtime_minutes = round(water_needed_liters / self.FLOW_RATE_LPM, 1) if needed else 0
        return {
            'irrigation_needed': needed,
            'moisture_deficit': round(moisture_deficit, 2),
            'water_needed_liters': water_needed_liters,
            'runtime_minutes': runtime_minutes,
            'pump_status': 'ON' if needed else 'OFF',
            'flow_rate_lpm': self.FLOW_RATE_LPM,
        }
    def simulate_pump(self, current_moisture: float, water_liters: float) -> dict:
        steps = []
        moisture = current_moisture
        liters_per_step = water_liters / 10  
        for i in range(10):
            gain = liters_per_step * (1 - (moisture / 100) ** 2)
            moisture = min(100.0, moisture + gain)
            steps.append(round(moisture, 2))
        runtime_minutes = round(water_liters / self.FLOW_RATE_LPM, 1)
        return {
            'pump_status': 'ON',
            'initial_moisture': current_moisture,
            'final_moisture': steps[-1],
            'moisture_curve': steps,
            'water_added_liters': water_liters,
            'runtime_minutes': runtime_minutes,
        }