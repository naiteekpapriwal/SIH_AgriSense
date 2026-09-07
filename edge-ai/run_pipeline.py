"""
End-to-end pipeline orchestrator.

Runs the mock sensor stream and camera capture simulation together,
feeding data through the alert engine to Supabase. This is the single
entry point that demonstrates the complete edge-to-cloud flow.
"""

import sys
import time
import argparse
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "logic"))
sys.path.insert(0, str(BASE_DIR / "inference"))

from mock_sensor_stream import SensorSimulator, DEVICE_ID
from alert_engine import AlertEngine
from irrigation_advisor import SensorReading


def run_sensor_thread(simulator, engine, scenario, interval, duration, results):
    """Thread: generate sensor readings and process through alert engine."""
    import time
    from datetime import datetime

    start = time.time()
    count = 0

    while True:
        if duration and (time.time() - start) >= duration:
            break

        reading = simulator.generate(scenario)
        count += 1
        ts = datetime.now().strftime("%H:%M:%S")

        print(
            f"  [SENSOR {ts}] #{count:04d} | "
            f"🌡️  {reading.temperature:5.1f}°C | "
            f"💧 {reading.humidity:5.1f}% | "
            f"🌱 {reading.soil_moisture:5.1f}%"
        )

        alerts = engine.process_reading(reading)
        for alert in alerts:
            print(f"  [ALERT] ⚡ [{alert.severity.upper()}] {alert.message[:70]}...")

        results["sensor_count"] = count
        results["alert_count"] = results.get("alert_count", 0) + len(alerts)

        time.sleep(interval)


def run_camera_thread(interval, max_captures, results):
    """Thread: run camera capture simulation (if model is available)."""
    from datetime import datetime

    try:
        from onnx_inference import CropDiseaseClassifier
        from camera_capture import run_capture_loop, get_supabase_client

        classifier = CropDiseaseClassifier()
        supabase = get_supabase_client()
        run_capture_loop(classifier, supabase, interval=interval, max_captures=max_captures)
    except FileNotFoundError:
        print("  [CAMERA] ONNX model not found — skipping camera simulation.")
        print("  [CAMERA] Run training/export_onnx.py to enable this feature.")
    except Exception as e:
        print(f"  [CAMERA] Camera simulation error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run the complete edge-to-cloud pipeline")
    parser.add_argument("--scenario", type=str, default="normal",
                        choices=["normal", "drought", "disease", "heat_wave"],
                        help="Sensor simulation scenario")
    parser.add_argument("--sensor-interval", type=float, default=5.0,
                        help="Seconds between sensor readings")
    parser.add_argument("--camera-interval", type=int, default=30,
                        help="Seconds between camera captures")
    parser.add_argument("--duration", type=int, default=120,
                        help="Total pipeline duration in seconds")
    parser.add_argument("--no-camera", action="store_true",
                        help="Disable camera simulation")
    args = parser.parse_args()

    print("=" * 60)
    print("  Smart Farming Assistant — Full Pipeline")
    print("=" * 60)
    print(f"  Scenario: {args.scenario}")
    print(f"  Duration: {args.duration}s")
    print(f"  Sensor interval: {args.sensor_interval}s")
    print(f"  Camera: {'disabled' if args.no_camera else f'every {args.camera_interval}s'}")
    print("=" * 60)

    simulator = SensorSimulator()
    engine = AlertEngine(cooldown_minutes=2)
    results = {"sensor_count": 0, "alert_count": 0}

    # Start sensor thread
    sensor_thread = threading.Thread(
        target=run_sensor_thread,
        args=(simulator, engine, args.scenario, args.sensor_interval, args.duration, results),
        daemon=True,
    )

    threads = [sensor_thread]

    # Start camera thread (optional)
    if not args.no_camera:
        camera_thread = threading.Thread(
            target=run_camera_thread,
            args=(args.camera_interval, args.duration // args.camera_interval, results),
            daemon=True,
        )
        threads.append(camera_thread)

    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=args.duration + 10)
    except KeyboardInterrupt:
        print("\n  Pipeline interrupted by user.")

    print(f"\n{'='*60}")
    print(f"  Pipeline Complete")
    print(f"  Sensor readings: {results.get('sensor_count', 0)}")
    print(f"  Alerts generated: {results.get('alert_count', 0)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
