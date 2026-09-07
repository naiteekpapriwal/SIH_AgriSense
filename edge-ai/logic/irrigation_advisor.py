"""
Smart Irrigation Advisor — Multi-factor threshold decision engine.

Analyzes soil moisture, temperature, and humidity readings to determine
whether irrigation is needed and at what urgency level. Produces
structured advisory alerts that can be pushed to the dashboard.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ─── Data Models ─────────────────────────────────────────────────────────────
@dataclass
class SensorReading:
    """A single sensor reading from an edge device."""
    device_id: str
    temperature: float       # Celsius
    humidity: float          # Percentage (0-100)
    soil_moisture: float     # Percentage (0-100)
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Alert:
    """A structured advisory alert."""
    device_id: str
    alert_type: str          # 'irrigation', 'pest', 'heat_stress', 'frost', etc.
    message: str             # Human-readable advisory message
    severity: str            # 'critical', 'high', 'medium', 'low'
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "alert_type": self.alert_type,
            "message": self.message,
            "severity": self.severity,
        }


# ─── Configuration ───────────────────────────────────────────────────────────
@dataclass
class IrrigationConfig:
    """
    Configurable thresholds for irrigation decisions.
    Default values are based on common agricultural guidelines for
    Indian farming conditions (tropical/subtropical climate).
    """
    # Soil moisture thresholds (percentage)
    moisture_critical: float = 25.0    # Below this = irrigate immediately
    moisture_low: float = 35.0         # Below this + high temp = urgent
    moisture_watch: float = 40.0       # Below this + dry air = schedule irrigation

    # Environmental thresholds
    temp_high: float = 32.0            # High temperature threshold (°C)
    temp_very_high: float = 38.0       # Extreme heat (°C)
    humidity_dry: float = 40.0         # Low humidity threshold (%)

    # Optimal ranges (for "all clear" messaging)
    moisture_optimal_low: float = 40.0
    moisture_optimal_high: float = 70.0


# ─── Irrigation Advisor ─────────────────────────────────────────────────────
class IrrigationAdvisor:
    """
    Multi-factor irrigation decision engine.

    Decision flowchart:
        1. moisture < critical → IRRIGATE NOW (critical)
        2. moisture < low AND temp > high → IRRIGATE NOW (critical)
        3. moisture < watch AND humidity < dry → SCHEDULE (high)
        4. moisture < watch → SCHEDULE (medium)
        5. Otherwise → NO ACTION (optimal)
    """

    def __init__(self, config: IrrigationConfig = None):
        self.config = config or IrrigationConfig()

    def evaluate(self, reading: SensorReading) -> Optional[Alert]:
        """
        Evaluate a sensor reading and return an irrigation alert if needed.

        Returns None if no action is required (soil moisture is optimal).
        """
        c = self.config
        m = reading.soil_moisture
        t = reading.temperature
        h = reading.humidity

        # ── Rule 1: Critical moisture deficit ────────────────────────────
        if m < c.moisture_critical:
            if t > c.temp_very_high:
                return Alert(
                    device_id=reading.device_id,
                    alert_type="irrigation",
                    severity="critical",
                    message=(
                        f"🚨 CRITICAL: Soil moisture dangerously low at {m:.1f}% "
                        f"with extreme heat ({t:.1f}°C). "
                        f"Activate emergency irrigation immediately to prevent crop loss."
                    ),
                )
            return Alert(
                device_id=reading.device_id,
                alert_type="irrigation",
                severity="critical",
                message=(
                    f"🚨 Soil moisture critically low at {m:.1f}%. "
                    f"Immediate irrigation required. "
                    f"Current conditions: {t:.1f}°C, {h:.1f}% humidity."
                ),
            )

        # ── Rule 2: Low moisture + high temperature ──────────────────────
        if m < c.moisture_low and t > c.temp_high:
            return Alert(
                device_id=reading.device_id,
                alert_type="irrigation",
                severity="high",
                message=(
                    f"⚠️ Soil moisture low ({m:.1f}%) with high temperature ({t:.1f}°C). "
                    f"Irrigate within the next 1-2 hours to avoid water stress. "
                    f"Consider irrigating during cooler hours (early morning/evening)."
                ),
            )

        # ── Rule 3: Watch-level moisture + dry air ───────────────────────
        if m < c.moisture_watch and h < c.humidity_dry:
            return Alert(
                device_id=reading.device_id,
                alert_type="irrigation",
                severity="medium",
                message=(
                    f"💧 Soil moisture declining ({m:.1f}%) with dry air ({h:.1f}% humidity). "
                    f"Rapid evaporation expected. Schedule irrigation for today."
                ),
            )

        # ── Rule 4: Watch-level moisture alone ───────────────────────────
        if m < c.moisture_watch:
            return Alert(
                device_id=reading.device_id,
                alert_type="irrigation",
                severity="low",
                message=(
                    f"💧 Soil moisture at {m:.1f}% — approaching lower threshold. "
                    f"Monitor closely. Plan irrigation if no rain is expected."
                ),
            )

        # ── No action needed ─────────────────────────────────────────────
        return None

    def get_status_summary(self, reading: SensorReading) -> str:
        """Returns a human-readable status summary for the dashboard."""
        m = reading.soil_moisture
        c = self.config

        if m >= c.moisture_optimal_high:
            return "🟢 Soil moisture optimal — no irrigation needed"
        elif m >= c.moisture_optimal_low:
            return "🟢 Soil moisture adequate"
        elif m >= c.moisture_watch:
            return "🟡 Soil moisture declining — monitor closely"
        elif m >= c.moisture_low:
            return "🟠 Soil moisture low — irrigation recommended"
        else:
            return "🔴 Soil moisture critical — immediate irrigation required"


# ─── CLI Testing ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    advisor = IrrigationAdvisor()

    # Test scenarios
    test_cases = [
        SensorReading("test-01", temperature=28.0, humidity=55.0, soil_moisture=50.0),
        SensorReading("test-01", temperature=34.0, humidity=35.0, soil_moisture=38.0),
        SensorReading("test-01", temperature=35.0, humidity=45.0, soil_moisture=30.0),
        SensorReading("test-01", temperature=40.0, humidity=25.0, soil_moisture=18.0),
        SensorReading("test-01", temperature=42.0, humidity=20.0, soil_moisture=15.0),
    ]

    print("=" * 70)
    print("  Irrigation Advisor — Test Scenarios")
    print("=" * 70)

    for i, reading in enumerate(test_cases, 1):
        print(f"\n  Scenario {i}: temp={reading.temperature}°C, "
              f"humidity={reading.humidity}%, moisture={reading.soil_moisture}%")

        alert = advisor.evaluate(reading)
        status = advisor.get_status_summary(reading)
        print(f"  Status: {status}")

        if alert:
            print(f"  Alert [{alert.severity.upper()}]: {alert.message}")
        else:
            print(f"  No alert — conditions are optimal.")
