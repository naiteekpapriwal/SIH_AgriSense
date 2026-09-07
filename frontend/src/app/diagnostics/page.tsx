import type { Metadata } from "next";
import DiagnosticsPage from "./DiagnosticsPage";

export const metadata: Metadata = {
  title: "Crop Diagnostics — Smart Farming Assistant",
  description: "AI-powered crop disease detection results and confidence analysis.",
};

export default function Page() {
  return <DiagnosticsPage />;
}
