import type { Metadata } from "next";
import SensorDashboard from "./SensorDashboard";

export const metadata: Metadata = {
  title: "Sensor Dashboard — Smart Farming Assistant",
  description: "Real-time environmental sensor data visualization with live charts.",
};

export default function DashboardPage() {
  return <SensorDashboard />;
}
