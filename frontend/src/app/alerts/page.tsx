import type { Metadata } from "next";
import AlertsPage from "./AlertsPage";

export const metadata: Metadata = {
  title: "Advisory Alerts — Smart Farming Assistant",
  description: "Real-time irrigation, pest, and environmental risk alerts for your farm.",
};

export default function Page() {
  return <AlertsPage />;
}
