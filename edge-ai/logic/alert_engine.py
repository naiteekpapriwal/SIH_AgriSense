"""
Unified Alert Engine — Orchestrates irrigation advisor and risk monitor.

Collects alerts from all sub-systems, deduplicates them (no repeated alert
within a cooldown window), and pushes to Supabase advisory_alerts table.
Also supports a local SQLite buffer for offline resilience.
"""

import os
import time
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

from irrigation_advisor import IrrigationAdvisor, IrrigationConfig, SensorReading, Alert
from risk_monitor import RiskMonitor, RiskConfig

# Load environment
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR.parent / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("alert_engine")


# ─── SQLite Offline Buffer ───────────────────────────────────────────────────
class OfflineBuffer:
    """
    Local SQLite buffer for storing alerts when Supabase is unreachable.
    Flushes buffered alerts when connectivity is restored.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(BASE_DIR / "offline_buffer.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buffered_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                created_at TEXT NOT NULL,
                flushed INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buffered_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                soil_moisture REAL NOT NULL,
                created_at TEXT NOT NULL,
                flushed INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def buffer_alert(self, alert: Alert):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO buffered_alerts (device_id, alert_type, message, severity, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (alert.device_id, alert.alert_type, alert.message, alert.severity,
             alert.timestamp or datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        log.info(f"Buffered alert locally: [{alert.severity}] {alert.alert_type}")

    def buffer_reading(self, reading: SensorReading):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO buffered_readings (device_id, temperature, humidity, soil_moisture, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (reading.device_id, reading.temperature, reading.humidity,
             reading.soil_moisture, reading.timestamp or datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_pending_alerts(self) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT id, device_id, alert_type, message, severity FROM buffered_alerts WHERE flushed = 0"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "device_id": r[1], "alert_type": r[2], "message": r[3], "severity": r[4]}
            for r in rows
        ]

    def get_pending_readings(self) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT id, device_id, temperature, humidity, soil_moisture FROM buffered_readings WHERE flushed = 0"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "device_id": r[1], "temperature": r[2], "humidity": r[3], "soil_moisture": r[4]}
            for r in rows
        ]

    def mark_flushed(self, table: str, ids: list[int]):
        if not ids:
            return
        conn = sqlite3.connect(self.db_path)
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"UPDATE {table} SET flushed = 1 WHERE id IN ({placeholders})", ids)
        conn.commit()
        conn.close()

    def pending_count(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        alerts = conn.execute("SELECT COUNT(*) FROM buffered_alerts WHERE flushed = 0").fetchone()[0]
        readings = conn.execute("SELECT COUNT(*) FROM buffered_readings WHERE flushed = 0").fetchone()[0]
        conn.close()
        return {"alerts": alerts, "readings": readings}


# ─── Alert Engine ────────────────────────────────────────────────────────────
class AlertEngine:
    """
    Central alert orchestrator.

    Combines irrigation advisor + risk monitor, deduplicates alerts,
    and handles Supabase push with offline fallback.
    """

    def __init__(
        self,
        irrigation_config: IrrigationConfig = None,
        risk_config: RiskConfig = None,
        cooldown_minutes: int = 15,
        enable_offline_buffer: bool = True,
    ):
        self.irrigation_advisor = IrrigationAdvisor(irrigation_config)
        self.risk_monitor = RiskMonitor(risk_config)
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self.enable_offline_buffer = enable_offline_buffer

        # Track last alert time per (device_id, alert_type) for deduplication
        self._last_alert: dict[tuple[str, str], datetime] = {}

        # Supabase client (lazy init)
        self._supabase = None
        self._supabase_available = True

        # Offline buffer
        self.buffer = OfflineBuffer() if enable_offline_buffer else None

    def _get_supabase(self):
        """Lazy-initialize Supabase client."""
        if self._supabase is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
            if url and key:
                from supabase import create_client
                self._supabase = create_client(url, key)
            else:
                log.warning("Supabase credentials not configured. Using offline-only mode.")
                self._supabase_available = False
        return self._supabase

    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if this alert was already sent within the cooldown window."""
        key = (alert.device_id, alert.alert_type)
        now = datetime.now()

        if key in self._last_alert:
            elapsed = now - self._last_alert[key]
            if elapsed < self.cooldown:
                return True

        self._last_alert[key] = now
        return False

    def _push_alert(self, alert: Alert) -> bool:
        """Push alert to Supabase. Returns True on success."""
        supabase = self._get_supabase()
        if supabase is None:
            return False

        try:
            supabase.table("advisory_alerts").insert(alert.to_dict()).execute()
            self._supabase_available = True
            return True
        except Exception as e:
            log.error(f"Supabase push failed: {e}")
            self._supabase_available = False
            return False

    def _push_reading(self, reading: SensorReading) -> bool:
        """Push sensor reading to Supabase. Returns True on success."""
        supabase = self._get_supabase()
        if supabase is None:
            return False

        try:
            data = {
                "device_id": reading.device_id,
                "temperature": reading.temperature,
                "humidity": reading.humidity,
                "soil_moisture": reading.soil_moisture,
            }
            supabase.table("sensor_readings").insert(data).execute()
            self._supabase_available = True
            return True
        except Exception as e:
            log.error(f"Supabase reading push failed: {e}")
            self._supabase_available = False
            return False

    def flush_buffer(self):
        """Attempt to flush offline buffer to Supabase."""
        if not self.buffer:
            return

        pending = self.buffer.pending_count()
        if pending["alerts"] == 0 and pending["readings"] == 0:
            return

        log.info(f"Flushing offline buffer: {pending['alerts']} alerts, {pending['readings']} readings")

        # Flush alerts
        buffered_alerts = self.buffer.get_pending_alerts()
        flushed_ids = []
        for ba in buffered_alerts:
            alert = Alert(
                device_id=ba["device_id"],
                alert_type=ba["alert_type"],
                message=ba["message"],
                severity=ba["severity"],
            )
            if self._push_alert(alert):
                flushed_ids.append(ba["id"])
            else:
                break  # Stop if Supabase is down again

        self.buffer.mark_flushed("buffered_alerts", flushed_ids)

        # Flush readings
        buffered_readings = self.buffer.get_pending_readings()
        flushed_ids = []
        for br in buffered_readings:
            reading = SensorReading(
                device_id=br["device_id"],
                temperature=br["temperature"],
                humidity=br["humidity"],
                soil_moisture=br["soil_moisture"],
            )
            if self._push_reading(reading):
                flushed_ids.append(br["id"])
            else:
                break

        self.buffer.mark_flushed("buffered_readings", flushed_ids)

        if flushed_ids:
            log.info(f"Buffer flush complete")

    def process_reading(self, reading: SensorReading) -> list[Alert]:
        """
        Process a sensor reading through all sub-systems.

        1. Push reading to Supabase (or buffer locally)
        2. Run irrigation advisor
        3. Run risk monitor
        4. Deduplicate alerts
        5. Push alerts to Supabase (or buffer locally)
        6. Attempt to flush any buffered data

        Returns list of new (non-duplicate) alerts generated.
        """
        # Push reading
        if not self._push_reading(reading):
            if self.buffer:
                self.buffer.buffer_reading(reading)

        # Collect alerts from all sub-systems
        all_alerts = []

        irrigation_alert = self.irrigation_advisor.evaluate(reading)
        if irrigation_alert:
            all_alerts.append(irrigation_alert)

        risk_alerts = self.risk_monitor.evaluate(reading)
        all_alerts.extend(risk_alerts)

        # Deduplicate and push
        new_alerts = []
        for alert in all_alerts:
            if self._is_duplicate(alert):
                log.debug(f"Suppressed duplicate: [{alert.alert_type}]")
                continue

            new_alerts.append(alert)

            if not self._push_alert(alert):
                if self.buffer:
                    self.buffer.buffer_alert(alert)

            log.info(f"[{alert.severity.upper()}] {alert.alert_type}: {alert.message[:80]}...")

        # Attempt to flush buffer if Supabase is available
        if self._supabase_available and self.buffer:
            self.flush_buffer()

        return new_alerts


# ─── CLI Testing ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    engine = AlertEngine(cooldown_minutes=1)  # Short cooldown for testing

    test_readings = [
        SensorReading("edge-01", 28.0, 55.0, 50.0),   # Normal
        SensorReading("edge-01", 34.0, 35.0, 22.0),   # Critical moisture
        SensorReading("edge-01", 34.5, 34.0, 21.0),   # Duplicate (within cooldown)
        SensorReading("edge-01", 39.0, 40.0, 35.0),   # First high-temp reading
        SensorReading("edge-01", 40.0, 38.0, 30.0),   # Second → heat stress!
        SensorReading("edge-01", 25.0, 90.0, 50.0),   # Disease risk
    ]

    print("=" * 70)
    print("  Alert Engine — Integration Test")
    print("=" * 70)

    for i, reading in enumerate(test_readings, 1):
        print(f"\n--- Reading {i}: temp={reading.temperature}°C, "
              f"humidity={reading.humidity}%, moisture={reading.soil_moisture}% ---")
        alerts = engine.process_reading(reading)
        if not alerts:
            print("  (no new alerts)")
