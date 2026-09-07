/* ── Sensor Readings ──────────────────────────────────────────────────── */
export interface SensorReading {
  id: string;
  device_id: string;
  temperature: number;
  humidity: number;
  soil_moisture: number;
  timestamp: string;
}

/* ── Crop Diagnostics ─────────────────────────────────────────────────── */
export interface CropDiagnostic {
  id: string;
  device_id: string;
  image_url: string;
  disease_detected: string | null;
  confidence_score: number | null;
  timestamp: string;
}

/* ── Advisory Alerts ──────────────────────────────────────────────────── */
export type AlertType =
  | "irrigation"
  | "pest"
  | "heat_stress"
  | "frost"
  | "disease_risk"
  | "waterlogging";

export type Severity = "critical" | "high" | "medium" | "low";

export interface AdvisoryAlert {
  id: string;
  device_id: string;
  alert_type: AlertType;
  message: string;
  severity: Severity;
  timestamp: string;
}

/* ── UI Helpers ───────────────────────────────────────────────────────── */
export interface StatCardData {
  label: string;
  value: string | number;
  unit?: string;
  icon: string;
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  color?: string;
}

export const SEVERITY_CONFIG: Record<
  Severity,
  { color: string; bg: string; label: string }
> = {
  critical: {
    color: "var(--accent-red)",
    bg: "hsla(0, 72%, 55%, 0.15)",
    label: "Critical",
  },
  high: {
    color: "var(--accent-amber)",
    bg: "hsla(38, 92%, 55%, 0.15)",
    label: "High",
  },
  medium: {
    color: "var(--accent-yellow)",
    bg: "hsla(50, 90%, 55%, 0.15)",
    label: "Medium",
  },
  low: {
    color: "var(--accent-green)",
    bg: "hsla(142, 70%, 45%, 0.15)",
    label: "Low",
  },
};

export const ALERT_TYPE_ICONS: Record<AlertType, string> = {
  irrigation: "💧",
  pest: "🐛",
  heat_stress: "🌡️",
  frost: "❄️",
  disease_risk: "🍄",
  waterlogging: "🌊",
};
