"use client";

import { CropDiagnostic } from "@/lib/types";

interface DiagnosticCardProps {
  diagnostic: CropDiagnostic;
}

export default function DiagnosticCard({ diagnostic }: DiagnosticCardProps) {
  const confidence = diagnostic.confidence_score ?? 0;

  const getConfidenceLevel = (score: number) => {
    if (score >= 90) return "high";
    if (score >= 70) return "medium";
    return "low";
  };

  const formatDiseaseName = (name: string | null) => {
    if (!name) return "Unknown";
    return name.replace(/___/g, " — ").replace(/_/g, " ");
  };

  const formatTimestamp = (ts: string) => {
    try {
      const date = new Date(ts);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMin = Math.floor(diffMs / 60000);

      if (diffMin < 1) return "Just now";
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHrs = Math.floor(diffMin / 60);
      if (diffHrs < 24) return `${diffHrs}h ago`;
      return date.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
      });
    } catch {
      return "";
    }
  };

  const isHealthy =
    diagnostic.disease_detected?.toLowerCase().includes("healthy") ?? false;

  return (
    <div className="diagnostic-card">
      <div
        style={{
          width: "100%",
          height: "180px",
          background: `linear-gradient(135deg, hsla(160, 20%, 15%, 0.8), hsla(160, 15%, 10%, 0.9))`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "3rem",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        {isHealthy ? "🌿" : "🍂"}
      </div>

      <div className="diagnostic-card-body">
        <div className="diagnostic-card-disease">
          {formatDiseaseName(diagnostic.disease_detected)}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.8rem",
            color: "var(--text-muted)",
          }}
        >
          <span>Confidence:</span>
          <span
            style={{
              fontWeight: 600,
              color:
                confidence >= 90
                  ? "var(--accent-green)"
                  : confidence >= 70
                  ? "var(--accent-amber)"
                  : "var(--accent-red)",
            }}
          >
            {confidence.toFixed(1)}%
          </span>
        </div>

        <div className="confidence-bar">
          <div
            className={`confidence-bar-fill ${getConfidenceLevel(confidence)}`}
            style={{ width: `${confidence}%` }}
          />
        </div>

        <div className="diagnostic-card-meta">
          <span>{diagnostic.device_id}</span>
          <span>{formatTimestamp(diagnostic.timestamp)}</span>
        </div>
      </div>
    </div>
  );
}
