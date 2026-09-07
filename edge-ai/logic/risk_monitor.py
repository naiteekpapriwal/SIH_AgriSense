"""
Environmental Risk Monitor — Detects sustained hazardous conditions.

Maintains a rolling window of recent sensor readings per device and
applies pattern-based rules to detect risks that require consecutive
readings above/below thresholds (e.g., heat stress needs 2+ consecutive
high-temp readings to avoid false positives from transient spikes).
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

from irrigation_advisor import SensorReading, Alert


# ─── Configuration ───────────────────────────────────────────────────────────
@dataclass
class RiskConfig:
    """Thresholds for environmental risk detection."""
    # Heat stress
    heat_stress_temp: float = 38.0         # °C — sustained high temp
    heat_stress_consecutive: int = 2       # Consecutive readings required

    # Frost risk
    frost_temp: float = 4.0               # °C — single reading is enough

    # Drought
    drought_moisture: float = 20.0        # %
    drought_humidity: float = 30.0        # %

    # Disease-favorable (fungal)
    disease_humidity_high: float = 85.0   # %
    disease_temp_low: float = 20.0        # °C
    disease_temp_high: float = 30.0       # °C

    # Waterlogging
    waterlog_moisture: float = 80.0       # %

    # Rolling window size (number of readings to keep per device)
    window_size: int = 10


# ─── Risk Monitor ────────────────────────────────────────────────────────────
class RiskMonitor:
    """
    Pattern-based environmental risk detection engine.

    Detects:
        1. Heat Stress — sustained high temperature
        2. Frost Risk — dangerously low temperature
        3. Drought Warning — combined low moisture + dry air
        4. Disease-Favorable — high humidity + moderate temp (fungal risk)
        5. Waterlogging — excessive soil moisture (drainage issues)
    """

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        # Per-device rolling window of recent readings
        self._history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.config.window_size)
        )

    def add_reading(self, reading: SensorReading):
        """Add a new reading to the device's history."""
        self._history[reading.device_id].append(reading)

    def evaluate(self, reading: SensorReading) -> list[Alert]:
        """
        Evaluate a new reading and return any triggered risk alerts.

        Automatically adds the reading to the rolling history before evaluation.
        Returns a list of alerts (may be empty, or contain multiple simultaneous risks).
        """
        self.add_reading(reading)
        history = list(self._history[reading.device_id])
        alerts = []

        # ── 1. Heat Stress (requires consecutive readings) ───────────────
        heat_alert = self._check_heat_stress(reading, history)
        if heat_alert:
            alerts.append(heat_alert)

        # ── 2. Frost Risk (single reading) ───────────────────────────────
        frost_alert = self._check_frost(reading)
        if frost_alert:
            alerts.append(frost_alert)

        # ── 3. Drought Warning ───────────────────────────────────────────
        drought_alert = self._check_drought(reading)
        if drought_alert:
            alerts.append(drought_alert)

        # ── 4. Disease-Favorable Conditions ──────────────────────────────
        disease_alert = self._check_disease_risk(reading)
        if disease_alert:
            alerts.append(disease_alert)

        # ── 5. Waterlogging ──────────────────────────────────────────────
        waterlog_alert = self._check_waterlogging(reading)
        if waterlog_alert:
            alerts.append(waterlog_alert)

        return alerts

    # ── Private detection methods ────────────────────────────────────────

    def _check_heat_stress(self, reading: SensorReading, history: list) -> Optional[Alert]:
        """Heat stress requires N consecutive readings above threshold."""
        c = self.config
        if reading.temperature <= c.heat_stress_temp:
            return None

        # Check last N readings are all above threshold
        required = c.heat_stress_consecutive
        if len(history) < required:
            return None

        recent = history[-required:]
        if all(r.temperature > c.heat_stress_temp for r in recent):
            return Alert(
                device_id=reading.device_id,
                alert_type="heat_stress",
                severity="critical",
                message=(
                    f"🌡️ HEAT STRESS: Temperature sustained above {c.heat_stress_temp}°C "
                    f"for {required} consecutive readings (current: {reading.temperature:.1f}°C). "
                    f"Protect crops with shade netting. Increase irrigation frequency. "
                    f"Avoid fieldwork during peak hours."
                ),
            )
        return None

    def _check_frost(self, reading: SensorReading) -> Optional[Alert]:
        """Frost risk — immediate alert on single low-temp reading."""
        if reading.temperature < self.config.frost_temp:
            return Alert(
                device_id=reading.device_id,
                alert_type="frost",
                severity="critical",
                message=(
                    f"❄️ FROST RISK: Temperature dropped to {reading.temperature:.1f}°C. "
                    f"Activate frost protection measures immediately. "
                    f"Cover sensitive crops. Consider smudge pots or windbreaks."
                ),
            )
        return None

    def _check_drought(self, reading: SensorReading) -> Optional[Alert]:
        """Drought — combined low moisture and dry air."""
        c = self.config
        if reading.soil_moisture < c.drought_moisture and reading.humidity < c.drought_humidity:
            return Alert(
                device_id=reading.device_id,
                alert_type="irrigation",
                severity="high",
                message=(
                    f"🏜️ DROUGHT CONDITIONS: Soil moisture at {reading.soil_moisture:.1f}% "
                    f"with extremely dry air ({reading.humidity:.1f}% humidity). "
                    f"Severe moisture deficit detected. Immediate deep irrigation required. "
                    f"Apply mulch to reduce further evaporation."
                ),
            )
        return None

    def _check_disease_risk(self, reading: SensorReading) -> Optional[Alert]:
        """Fungal disease risk — high humidity + moderate temperature."""
        c = self.config
        if (reading.humidity > c.disease_humidity_high and
                c.disease_temp_low <= reading.temperature <= c.disease_temp_high):
            return Alert(
                device_id=reading.device_id,
                alert_type="disease_risk",
                severity="medium",
                message=(
                    f"🍄 DISEASE RISK: High humidity ({reading.humidity:.1f}%) with moderate "
                    f"temperature ({reading.temperature:.1f}°C) creates ideal conditions for "
                    f"fungal diseases (blight, powdery mildew, rust). "
                    f"Inspect crops for early signs. Consider preventive fungicide application."
                ),
            )
        return None

    def _check_waterlogging(self, reading: SensorReading) -> Optional[Alert]:
        """Waterlogging — excess soil moisture indicating drainage issues."""
        if reading.soil_moisture > self.config.waterlog_moisture:
            return Alert(
                device_id=reading.device_id,
                alert_type="waterlogging",
                severity="medium",
                message=(
                    f"🌊 WATERLOGGING: Soil moisture excessively high at "
                    f"{reading.soil_moisture:.1f}%. "
                    f"Check field drainage systems. Prolonged waterlogging can cause "
                    f"root rot and oxygen deprivation. Suspend irrigation."
                ),
            )
        return None

    def get_risk_summary(self, device_id: str) -> dict:
        """Returns a summary of the current risk state for a device."""
        history = list(self._history.get(device_id, []))
        if not history:
            return {"status": "no_data", "risks": []}

        latest = history[-1]
        alerts = []

        # Re-evaluate latest without adding to history again
        if latest.temperature > self.config.heat_stress_temp:
            alerts.append("heat_stress")
        if latest.temperature < self.config.frost_temp:
            alerts.append("frost")
        if latest.soil_moisture < self.config.drought_moisture:
            alerts.append("drought")
        if latest.humidity > self.config.disease_humidity_high:
            alerts.append("disease_risk")
        if latest.soil_moisture > self.config.waterlog_moisture:
            alerts.append("waterlogging")

        return {
            "status": "alert" if alerts else "normal",
            "risks": alerts,
            "latest_reading": {
                "temperature": latest.temperature,
                "humidity": latest.humidity,
                "soil_moisture": latest.soil_moisture,
            },
        }


# ─── CLI Testing ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    monitor = RiskMonitor()

    test_sequences = [
        ("Normal", [
            SensorReading("dev-01", 28.0, 55.0, 45.0),
            SensorReading("dev-01", 29.0, 53.0, 44.0),
        ]),
        ("Heat Stress (2 consecutive high-temp readings)", [
            SensorReading("dev-02", 39.0, 40.0, 35.0),
            SensorReading("dev-02", 40.5, 38.0, 33.0),
        ]),
        ("Frost Risk", [
            SensorReading("dev-03", 2.0, 60.0, 40.0),
        ]),
        ("Disease-Favorable (high humidity + moderate temp)", [
            SensorReading("dev-04", 25.0, 90.0, 50.0),
        ]),
        ("Drought (low moisture + dry air)", [
            SensorReading("dev-05", 35.0, 22.0, 15.0),
        ]),
        ("Waterlogging", [
            SensorReading("dev-06", 26.0, 70.0, 85.0),
        ]),
    ]

    print("=" * 70)
    print("  Environmental Risk Monitor — Test Scenarios")
    print("=" * 70)

    for name, readings in test_sequences:
        # Fresh monitor per scenario for independent testing
        monitor = RiskMonitor()
        print(f"\n  Scenario: {name}")

        for reading in readings:
            alerts = monitor.evaluate(reading)

        if alerts:
            for alert in alerts:
                print(f"    [{alert.severity.upper()}] {alert.alert_type}: {alert.message[:100]}...")
        else:
            print(f"    ✓ No risks detected")
