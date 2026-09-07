'use client';

import { useEffect, useState } from 'react';
import StatCard from '@/components/StatCard';
import { SensorReading, AdvisoryAlert } from '@/lib/types';
import { getLatestReadings, getAlerts, subscribeToReadings } from '@/lib/supabase';
import { CheckCircle2, AlertTriangle, Droplets, ThermometerSun } from 'lucide-react';

export default function OverviewPage() {
  const [latestReading, setLatestReading] = useState<SensorReading | null>(null);
  const [alertCount, setAlertCount] = useState(0);
  const [recentAlerts, setRecentAlerts] = useState<AdvisoryAlert[]>([]);

  useEffect(() => {
    getLatestReadings(1)
      .then((data) => {
        if (data.length > 0) setLatestReading(data[data.length - 1] as SensorReading);
      })
      .catch(console.error);

    getAlerts(undefined, 100)
      .then((data) => {
        const alerts = data as AdvisoryAlert[];
        setAlertCount(alerts.length);
        setRecentAlerts(alerts.slice(0, 3));
      })
      .catch(console.error);

    const unsubscribe = subscribeToReadings((reading) => {
      setLatestReading(reading as unknown as SensorReading);
    });
    return () => unsubscribe();
  }, []);

  const getStatusMessage = () => {
    if (!latestReading) return "Waiting for sensor data...";
    if (latestReading.soil_moisture < 25) return "Critical — Irrigation needed";
    if (latestReading.temperature > 38) return "Heat stress detected";
    if (alertCount > 0) return `${alertCount} alert${alertCount > 1 ? "s" : ""} require attention`;
    return "All systems nominal";
  };

  return (
    <div className="flex flex-col gap-8 max-w-7xl mx-auto">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold text-white tracking-tight">Overview</h1>
        <p className="text-gray-400 font-medium">{getStatusMessage()}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon="thermometer"
          label="Temperature"
          value={latestReading?.temperature ?? 0}
          unit="°C"
          trend={latestReading && latestReading.temperature > 35 ? "up" : "stable"}
          trendValue={latestReading && latestReading.temperature > 35 ? "High" : "Normal"}
        />
        <StatCard
          icon="droplets"
          label="Humidity"
          value={latestReading?.humidity ?? 0}
          unit="%"
          trend="stable"
          trendValue="Stable"
        />
        <StatCard
          icon="sprout"
          label="Soil Moisture"
          value={latestReading?.soil_moisture ?? 0}
          unit="%"
          trend={latestReading && latestReading.soil_moisture < 30 ? "down" : "stable"}
          trendValue={latestReading && latestReading.soil_moisture < 30 ? "Low" : "OK"}
        />
        <StatCard
          icon="bell"
          label="Active Alerts"
          value={alertCount}
          trend={alertCount > 0 ? "up" : "stable"}
          trendValue={alertCount > 0 ? `${alertCount} new` : "None"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-[#1A1A1A] border border-white/10 rounded-xl p-6 shadow-xl flex flex-col min-h-[300px]">
          <h2 className="text-lg font-bold text-white mb-4">Historical Sensor Trends</h2>
          <div className="flex-1 border-2 border-dashed border-white/10 rounded-lg flex items-center justify-center bg-white/5">
            <span className="text-gray-500 font-medium">Line chart placeholder</span>
          </div>
        </div>

        <div className="bg-[#1A1A1A] border border-white/10 rounded-xl p-6 shadow-xl flex flex-col">
          <h2 className="text-lg font-bold text-white mb-4">Recent Alerts</h2>
          
          {recentAlerts.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 py-8">
              <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center border border-green-500/20">
                <CheckCircle2 className="text-green-500" size={24} />
              </div>
              <div>
                <div className="text-sm font-bold text-white">All systems optimal</div>
                <div className="text-xs text-gray-400 mt-1">Farm conditions are normal</div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {recentAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`flex items-start gap-3 p-4 rounded-lg bg-white/5 border-l-2 ${
                    alert.severity === 'critical'
                      ? 'border-red-500'
                      : alert.severity === 'high'
                      ? 'border-orange-500'
                      : 'border-yellow-500'
                  }`}
                >
                  <div className="mt-0.5">
                    {alert.alert_type === 'irrigation' ? (
                      <Droplets className="text-blue-400" size={16} />
                    ) : alert.alert_type === 'heat_stress' ? (
                      <ThermometerSun className="text-orange-400" size={16} />
                    ) : (
                      <AlertTriangle className="text-yellow-400" size={16} />
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white capitalize">
                      {alert.alert_type.replace(/_/g, ' ')}
                    </div>
                    <div className="text-xs text-gray-400 mt-1 leading-snug">
                      {alert.message}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
