"use client";

import { useEffect, useState } from "react";
import DiagnosticCard from "@/components/DiagnosticCard";
import { CropDiagnostic } from "@/lib/types";
import { getDiagnostics, subscribeToDiagnostics } from "@/lib/supabase";

export default function DiagnosticsPage() {
  const [diagnostics, setDiagnostics] = useState<CropDiagnostic[]>([]);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    getDiagnostics(30)
      .then((data) => setDiagnostics(data as CropDiagnostic[]))
      .catch(console.error);

    const unsubscribe = subscribeToDiagnostics((newDiag) => {
      setDiagnostics((prev) =>
        [newDiag as unknown as CropDiagnostic, ...prev].slice(0, 50)
      );
    });

    return () => unsubscribe();
  }, []);

  const filteredDiagnostics = diagnostics.filter((d) => {
    if (filter === "all") return true;
    if (filter === "healthy")
      return d.disease_detected?.toLowerCase().includes("healthy");
    if (filter === "diseased")
      return !d.disease_detected?.toLowerCase().includes("healthy");
    return true;
  });

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Crop Diagnostics</h1>
        <p className="page-subtitle">
          AI-powered disease detection from edge camera analysis
        </p>
      </div>

      <div className="filter-bar">
        {["all", "healthy", "diseased"].map((f) => (
          <button
            key={f}
            className={`filter-btn ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all"
              ? `All (${diagnostics.length})`
              : f === "healthy"
              ? `Healthy (${diagnostics.filter((d) => d.disease_detected?.toLowerCase().includes("healthy")).length})`
              : `Diseased (${diagnostics.filter((d) => !d.disease_detected?.toLowerCase().includes("healthy")).length})`}
          </button>
        ))}
      </div>

      {filteredDiagnostics.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔬</div>
          <div className="empty-state-title">No diagnostics yet</div>
          <div className="empty-state-text">
            Run the camera capture simulation to see crop disease detection
            results appear here in real-time.
          </div>
        </div>
      ) : (
        <div className="diagnostics-grid">
          {filteredDiagnostics.map((d) => (
            <DiagnosticCard key={d.id} diagnostic={d} />
          ))}
        </div>
      )}
    </>
  );
}
