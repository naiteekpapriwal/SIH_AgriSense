"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { SensorReading } from "@/lib/types";
import { getLatestReadings, subscribeToReadings } from "@/lib/supabase";

interface SensorChartProps {
  title: string;
  dataKey: keyof Pick<SensorReading, "temperature" | "humidity" | "soil_moisture">;
  color: string;
  unit: string;
  badge?: string;
}

export default function SensorChart({
  title,
  dataKey,
  color,
  unit,
  badge = "LIVE",
}: SensorChartProps) {
  const [data, setData] = useState<SensorReading[]>([]);

  useEffect(() => {
    // Initial fetch
    getLatestReadings(50)
      .then((readings) => setData(readings as SensorReading[]))
      .catch(console.error);

    // Real-time subscription
    const unsubscribe = subscribeToReadings((newReading) => {
      setData((prev) => {
        const updated = [...prev, newReading as unknown as SensorReading];
        return updated.slice(-50); // Keep last 50 points
      });
    });

    return () => unsubscribe();
  }, []);

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  };

  const CustomTooltip = ({ active, payload, label }: {
    active?: boolean;
    payload?: Array<{ value: number }>;
    label?: string;
  }) => {
    if (!active || !payload?.length) return null;
    return (
      <div
        style={{
          background: "hsla(160, 15%, 10%, 0.95)",
          backdropFilter: "blur(10px)",
          border: "1px solid hsla(160, 15%, 30%, 0.3)",
          borderRadius: "8px",
          padding: "8px 12px",
          fontSize: "0.8rem",
          color: "var(--text-primary)",
        }}
      >
        <div style={{ color: "var(--text-muted)", marginBottom: "2px" }}>
          {label ? formatTime(label) : ""}
        </div>
        <div style={{ color, fontWeight: 600 }}>
          {payload[0].value?.toFixed(1)} {unit}
        </div>
      </div>
    );
  };

  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <span className="chart-card-title">{title}</span>
        <span className="chart-card-badge">{badge}</span>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsla(160, 10%, 30%, 0.2)"
            vertical={false}
          />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTime}
            stroke="var(--text-muted)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="var(--text-muted)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: color, strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
