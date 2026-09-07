"use client";

import { useEffect, useState } from "react";
import {
  AdvisoryAlert,
  SEVERITY_CONFIG,
  ALERT_TYPE_ICONS,
  AlertType,
  Severity,
} from "@/lib/types";
import { getAlerts, subscribeToAlerts } from "@/lib/supabase";

export default function AlertFeed() {
  const [alerts, setAlerts] = useState<AdvisoryAlert[]>([]);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    getAlerts(undefined, 50)
      .then((data) => setAlerts(data as AdvisoryAlert[]))
      .catch(console.error);

    const unsubscribe = subscribeToAlerts((newAlert) => {
      setAlerts((prev) => [newAlert as unknown as AdvisoryAlert, ...prev].slice(0, 100));
    });

    return () => unsubscribe();
  }, []);

  const formatTimestamp = (ts: string) => {
    try {
      const date = new Date(ts);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMin = Math.floor(diffMs / 60000);

      if (diffMin < 1) return "Just now";
      if (diffMin < 60) return `${diffMin} min ago`;
      const diffHrs = Math.floor(diffMin / 60);
      if (diffHrs < 24) return `${diffHrs}h ago`;
      const diffDays = Math.floor(diffHrs / 24);
      return `${diffDays}d ago`;
    } catch {
      return "";
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    if (filter === "all") return true;
    if (["critical", "high", "medium", "low"].includes(filter))
      return a.severity === filter;
    return a.alert_type === filter;
  });

  const severityFilters = ["all", "critical", "high", "medium", "low"];

  return (
    <>
      <div className="filter-bar">
        {severityFilters.map((f) => (
          <button
            key={f}
            className={`filter-btn ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      <div className="alert-feed">
        {filteredAlerts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔔</div>
            <div className="empty-state-title">No alerts</div>
            <div className="empty-state-text">
              {filter === "all"
                ? "No advisory alerts have been generated yet. Start the edge pipeline to see real-time alerts."
                : `No ${filter} alerts found.`}
            </div>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const severityStyle =
              SEVERITY_CONFIG[alert.severity as Severity] || SEVERITY_CONFIG.low;
            const icon =
              ALERT_TYPE_ICONS[alert.alert_type as AlertType] || "⚠️";

            return (
              <div
                key={alert.id}
                className={`alert-item severity-${alert.severity}`}
              >
                <span className="alert-icon">{icon}</span>
                <div className="alert-content">
                  <div className="alert-header">
                    <span className="alert-type">
                      {alert.alert_type.replace(/_/g, " ")}
                    </span>
                    <span
                      className="severity-badge"
                      style={{
                        color: severityStyle.color,
                        background: severityStyle.bg,
                      }}
                    >
                      {severityStyle.label}
                    </span>
                  </div>
                  <p className="alert-message">{alert.message}</p>
                  <div className="alert-timestamp">
                    {formatTimestamp(alert.timestamp)}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
