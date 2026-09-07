import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

// Client is created only when env vars are present.
// During build/SSG, functions return empty arrays gracefully.
export const supabase = supabaseUrl
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

/* ── Query Helpers ────────────────────────────────────────────────────── */

export async function getLatestReadings(limit = 50) {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("sensor_readings")
    .select("*")
    .order("timestamp", { ascending: false })
    .limit(limit);

  if (error) throw error;
  return data?.reverse() ?? [];
}

export async function getReadingsInRange(start: Date, end: Date) {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("sensor_readings")
    .select("*")
    .gte("timestamp", start.toISOString())
    .lte("timestamp", end.toISOString())
    .order("timestamp", { ascending: true });

  if (error) throw error;
  return data ?? [];
}

export async function getDiagnostics(limit = 20) {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("crop_diagnostics")
    .select("*")
    .order("timestamp", { ascending: false })
    .limit(limit);

  if (error) throw error;
  return data ?? [];
}

export async function getAlerts(severity?: string, limit = 50) {
  if (!supabase) return [];
  let query = supabase
    .from("advisory_alerts")
    .select("*")
    .order("timestamp", { ascending: false })
    .limit(limit);

  if (severity) {
    query = query.eq("severity", severity);
  }

  const { data, error } = await query;
  if (error) throw error;
  return data ?? [];
}

/* ── Realtime Subscriptions ───────────────────────────────────────────── */

let channelCounter = 0;

export function subscribeToReadings(
  callback: (reading: Record<string, unknown>) => void
) {
  if (!supabase) return () => {};
  const channelName = `sensor_readings_${++channelCounter}_${Date.now()}`;
  const channel = supabase
    .channel(channelName)
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "sensor_readings" },
      (payload) => callback(payload.new)
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}

export function subscribeToAlerts(
  callback: (alert: Record<string, unknown>) => void
) {
  if (!supabase) return () => {};
  const channelName = `advisory_alerts_${++channelCounter}_${Date.now()}`;
  const channel = supabase
    .channel(channelName)
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "advisory_alerts" },
      (payload) => callback(payload.new)
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}

export function subscribeToDiagnostics(
  callback: (diagnostic: Record<string, unknown>) => void
) {
  if (!supabase) return () => {};
  const channelName = `crop_diagnostics_${++channelCounter}_${Date.now()}`;
  const channel = supabase
    .channel(channelName)
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "crop_diagnostics" },
      (payload) => callback(payload.new)
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}
