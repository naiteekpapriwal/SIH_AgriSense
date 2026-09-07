"use client";

import SensorChart from "@/components/SensorChart";

export default function SensorDashboard() {
  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Sensor Dashboard</h1>
        <p className="page-subtitle">
          Real-time environmental data from edge devices
        </p>
      </div>

      <div className="charts-grid">
        <SensorChart
          title="Temperature"
          dataKey="temperature"
          color="hsl(38, 92%, 55%)"
          unit="°C"
        />
        <SensorChart
          title="Humidity"
          dataKey="humidity"
          color="hsl(210, 80%, 55%)"
          unit="%"
        />
        <SensorChart
          title="Soil Moisture"
          dataKey="soil_moisture"
          color="hsl(142, 70%, 45%)"
          unit="%"
        />
      </div>
    </>
  );
}
