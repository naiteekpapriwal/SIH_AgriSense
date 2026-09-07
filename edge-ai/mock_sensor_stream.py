"""
Mock sensor data stream with scenario simulation.

Generates realistic environmental sensor readings (soil moisture, temperature,
humidity) with temporal patterns and pushes them to Supabase. Integrates with
the alert engine to generate advisory alerts in real-time.

Scenarios:
    normal     — Stable readings within safe ranges
    drought    — Soil moisture steadily declining, high temperatures
    disease    — High humidity, moderate temperature (fungal risk)
    heat_wave  — Temperature climbing to extreme levels
    full_demo  — Runs all scenarios sequentially
"""

import os
import sys
import math
import time
import random
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "logic"))

from irrigation_advisor import SensorReading
from alert_engine import AlertEngine

# Load environment
load_dotenv(dotenv_path=BASE_DIR.parent / ".env")


DEVICE_ID = "edge-device-sih-01"


# ─── Scenario Generators ────────────────────────────────────────────────────
class SensorSimulator:
    """
    Generates time-varying sensor readings with realistic patterns.
    Supports different scenario modes.
    """

    def __init__(self, device_id: str = DEVICE_ID):
        self.device_id = device_id
        self.tick = 0  # Simulation tick counter

    def _base_temperature(self) -> float:
        """Diurnal temperature pattern (warmer during day, cooler at night)."""
        # Simulate a ~24hr cycle over 48 ticks (5s each = 4 min cycle for demo)
        hour_sim = (self.tick % 48) / 48.0 * 24.0
        # Peak at ~14:00, trough at ~04:00
        base = 27.0 + 5.0 * math.sin(math.pi * (hour_sim - 8) / 12)
        return base + random.gauss(0, 0.5)  # Add noise

    def _base_humidity(self, temperature: float) -> float:
        """Humidity inversely correlated with temperature."""
        base = 80.0 - (temperature - 22.0) * 2.0
        return max(20.0, min(95.0, base + random.gauss(0, 2.0)))

    def _base_moisture(self) -> float:
        """Slowly declining soil moisture (simulating evaporation)."""
        base = 50.0 - self.tick * 0.1
        return max(10.0, min(80.0, base + random.gauss(0, 1.0)))

    def generate_normal(self) -> SensorReading:
        """Normal conditions — stable, within safe ranges."""
        temp = 26.0 + random.gauss(0, 1.5)
        humidity = 55.0 + random.gauss(0, 3.0)
        moisture = 48.0 + random.gauss(0, 2.0)

        return SensorReading(
            device_id=self.device_id,
            temperature=round(max(20.0, min(32.0, temp)), 2),
            humidity=round(max(40.0, min(70.0, humidity)), 2),
            soil_moisture=round(max(40.0, min(60.0, moisture)), 2),
        )

    def generate_drought(self) -> SensorReading:
        """Drought scenario — moisture declining, temp rising."""
        progress = min(self.tick / 24.0, 1.0)  # 0 to 1 over 24 ticks (~2 min)

        temp = 30.0 + progress * 8.0 + random.gauss(0, 0.5)
        humidity = 45.0 - progress * 25.0 + random.gauss(0, 1.0)
        moisture = 40.0 - progress * 28.0 + random.gauss(0, 0.5)

        return SensorReading(
            device_id=self.device_id,
            temperature=round(max(28.0, temp), 2),
            humidity=round(max(15.0, humidity), 2),
            soil_moisture=round(max(10.0, moisture), 2),
        )

    def generate_disease_risk(self) -> SensorReading:
        """Disease-risk scenario — high humidity, moderate temp."""
        progress = min(self.tick / 24.0, 1.0)

        temp = 24.0 + random.gauss(0, 1.0)
        humidity = 70.0 + progress * 22.0 + random.gauss(0, 1.0)
        moisture = 55.0 + progress * 10.0 + random.gauss(0, 1.0)

        return SensorReading(
            device_id=self.device_id,
            temperature=round(max(20.0, min(30.0, temp)), 2),
            humidity=round(min(95.0, humidity), 2),
            soil_moisture=round(min(75.0, moisture), 2),
        )

    def generate_heat_wave(self) -> SensorReading:
        """Heat wave scenario — temperature climbing to extreme levels."""
        progress = min(self.tick / 24.0, 1.0)

        temp = 32.0 + progress * 12.0 + random.gauss(0, 0.5)
        humidity = 50.0 - progress * 20.0 + random.gauss(0, 1.5)
        moisture = 45.0 - progress * 15.0 + random.gauss(0, 1.0)

        return SensorReading(
            device_id=self.device_id,
            temperature=round(temp, 2),
            humidity=round(max(20.0, humidity), 2),
            soil_moisture=round(max(20.0, moisture), 2),
        )

    def generate(self, scenario: str) -> SensorReading:
        """Generate a reading based on the selected scenario."""
        self.tick += 1

        generators = {
            "normal": self.generate_normal,
            "drought": self.generate_drought,
            "disease": self.generate_disease_risk,
            "disease_risk": self.generate_disease_risk,
            "heat_wave": self.generate_heat_wave,
        }

        generator = generators.get(scenario, self.generate_normal)
        return generator()


# ─── Stream Runner ───────────────────────────────────────────────────────────
def run_stream(
    scenario: str = "normal",
    interval: float = 5.0,
    duration: int = None,
    enable_alerts: bool = True,
):
    """
    Run the sensor stream for a given scenario.

    Args:
        scenario: One of 'normal', 'drought', 'disease', 'heat_wave', 'full_demo'
        interval: Seconds between readings
        duration: Total duration in seconds (None = run indefinitely)
        enable_alerts: Whether to run the alert engine on each reading
    """
    simulator = SensorSimulator()
    engine = AlertEngine(cooldown_minutes=1) if enable_alerts else None

    if scenario == "full_demo":
        run_full_demo(simulator, engine, interval)
        return

    print(f"\n{'='*60}")
    print(f"  Mock Sensor Stream — Scenario: {scenario.upper()}")
    print(f"  Device: {DEVICE_ID} | Interval: {interval}s")
    if duration:
        print(f"  Duration: {duration}s")
    print(f"  Alert engine: {'enabled' if enable_alerts else 'disabled'}")
    print(f"{'='*60}")
    print(f"  Press Ctrl+C to stop.\n")

    start_time = time.time()
    count = 0

    try:
        while True:
            reading = simulator.generate(scenario)
            count += 1

            # Display reading
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"  [{timestamp}] #{count:04d} | "
                f"🌡️  {reading.temperature:5.1f}°C | "
                f"💧 {reading.humidity:5.1f}% | "
                f"🌱 {reading.soil_moisture:5.1f}%",
                end=""
            )

            # Process through alert engine
            if engine:
                alerts = engine.process_reading(reading)
                if alerts:
                    print()
                    for alert in alerts:
                        print(f"         ⚡ [{alert.severity.upper()}] {alert.message[:70]}...")
                else:
                    print("  ✓")
            else:
                print()

            # Check duration
            if duration and (time.time() - start_time) >= duration:
                print(f"\n  Duration reached ({duration}s). Stopping.")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n  Stopped after {count} readings ({elapsed:.0f}s)")


def run_full_demo(simulator, engine, interval):
    """Run all scenarios sequentially for a complete demo."""
    scenarios = [
        ("normal", 24, "Normal — stable field conditions"),
        ("heat_wave", 24, "Heat Wave — temperature rising to extreme"),
        ("drought", 24, "Drought — soil moisture critically declining"),
        ("disease", 24, "Disease Risk — fungal-favorable humidity spike"),
    ]

    total_readings = sum(count for _, count, _ in scenarios)
    print(f"\n{'='*60}")
    print(f"  Full Demo — {len(scenarios)} scenarios, {total_readings} total readings")
    print(f"  Estimated duration: {total_readings * interval / 60:.1f} minutes")
    print(f"{'='*60}")

    for scenario_name, num_readings, description in scenarios:
        simulator.tick = 0  # Reset tick for each scenario

        print(f"\n  {'─'*50}")
        print(f"  📍 {description}")
        print(f"  {'─'*50}")

        for i in range(num_readings):
            reading = simulator.generate(scenario_name)
            timestamp = datetime.now().strftime("%H:%M:%S")

            print(
                f"  [{timestamp}] "
                f"🌡️  {reading.temperature:5.1f}°C | "
                f"💧 {reading.humidity:5.1f}% | "
                f"🌱 {reading.soil_moisture:5.1f}%",
                end=""
            )

            if engine:
                alerts = engine.process_reading(reading)
                if alerts:
                    print()
                    for alert in alerts:
                        print(f"         ⚡ [{alert.severity.upper()}] {alert.message[:70]}...")
                else:
                    print("  ✓")
            else:
                print()

            time.sleep(interval)

    print(f"\n  {'='*60}")
    print(f"  Full demo complete!")
    print(f"  {'='*60}")


# ─── CLI Entry Point ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Mock Sensor Stream — simulates edge device sensor data",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--scenario", type=str, default="normal",
        choices=["normal", "drought", "disease", "heat_wave", "full_demo"],
        help=(
            "Simulation scenario:\n"
            "  normal    — Stable readings within safe ranges\n"
            "  drought   — Moisture declining, temp rising\n"
            "  disease   — High humidity, fungal disease risk\n"
            "  heat_wave — Temperature climbing to extremes\n"
            "  full_demo — All scenarios sequentially"
        ),
    )
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between readings (default: 5)")
    parser.add_argument("--duration", type=int, default=None, help="Total duration in seconds")
    parser.add_argument("--no-alerts", action="store_true", help="Disable alert engine")
    args = parser.parse_args()

    run_stream(
        scenario=args.scenario,
        interval=args.interval,
        duration=args.duration,
        enable_alerts=not args.no_alerts,
    )


if __name__ == "__main__":
    main()
