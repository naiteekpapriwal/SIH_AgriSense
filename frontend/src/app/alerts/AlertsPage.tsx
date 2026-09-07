"use client";

import AlertFeed from "@/components/AlertFeed";

export default function AlertsPage() {
  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Advisory Alerts</h1>
        <p className="page-subtitle">
          Real-time irrigation, risk, and disease advisories from edge AI
        </p>
      </div>

      <AlertFeed />
    </>
  );
}
