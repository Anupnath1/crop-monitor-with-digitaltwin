class RecommendationEngine:
    def generate(
        self,
        predicted_health: float,
        predicted_moisture: float,
        irrigation_data: dict,
        hours: float
    ) -> dict:
        urgency = self._urgency(predicted_health, predicted_moisture)
        message = self._message(urgency, hours, predicted_health, predicted_moisture)
        actions = self._actions(irrigation_data, urgency)
        expected_improvement = self._expected_improvement(predicted_moisture, irrigation_data)
        return {
            'urgency': urgency,
            'message': message,
            'actions': actions,
            'expected_improvement': expected_improvement,
            'irrigation_needed': irrigation_data['irrigation_needed'],
            'water_liters': irrigation_data['water_needed_liters'],
            'runtime_minutes': irrigation_data['runtime_minutes'],
            'pump_status': irrigation_data['pump_status'],
        }
    def _urgency(self, health: float, moisture: float) -> str:
        if health < 40 or moisture < 25:
            return 'CRITICAL'
        elif health < 60 or moisture < 45:
            return 'SOON'
        else:
            return 'NONE'
    def _message(self, urgency: str, hours: float, health: float, moisture: float) -> str:
        h_str = f"{hours:.0f}h" if hours == int(hours) else f"{hours:.1f}h"
        if urgency == 'CRITICAL':
            return (
                f"⚠️ IMMEDIATE ACTION REQUIRED: In {h_str}, soil moisture will drop to "
                f"{moisture:.1f}% and health score to {health:.0f}/100. "
                "Irrigation must begin now to prevent plant stress."
            )
        elif urgency == 'SOON':
            return (
                f"🕐 Irrigation recommended within {h_str}: Predicted moisture is "
                f"{moisture:.1f}% and health score is {health:.0f}/100. "
                "Schedule irrigation soon to maintain optimal conditions."
            )
        else:
            return (
                f"✅ No irrigation needed for the next {h_str}. "
                f"Predicted moisture: {moisture:.1f}%, health score: {health:.0f}/100. "
                "Plant conditions remain optimal."
            )
    def _actions(self, irrigation_data: dict, urgency: str) -> list:
        if urgency == 'NONE':
            return [
                'Continue monitoring sensor data',
                'Check again in 2–3 hours',
                'Ensure sunlight exposure is adequate',
            ]
        else:
            return [
                f"Activate pump for {irrigation_data['runtime_minutes']} minutes",
                f"Apply approximately {irrigation_data['water_needed_liters']} litres of water",
                'Monitor soil moisture after irrigation',
                'Re-check health score in 30 minutes',
            ]
    def _expected_improvement(self, current_moisture: float, irrigation_data: dict) -> dict:
        if not irrigation_data['irrigation_needed']:
            return {'moisture_change': 0, 'expected_moisture': round(current_moisture, 1)}
        final = min(100.0, current_moisture + irrigation_data['moisture_deficit'])
        return {
            'moisture_change': round(final - current_moisture, 1),
            'expected_moisture': round(final, 1),
            'expected_health_improvement': '10–25 points (estimated)',
        }