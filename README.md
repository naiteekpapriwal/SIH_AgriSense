# AgriSense: Smart Farming Assistant

AgriSense is an Edge AI and IoT platform built for real-time crop disease detection and irrigation monitoring. By running machine learning models on edge devices, the system operates effectively in areas with limited internet connectivity and pushes alerts to a centralized cloud dashboard.

## Key Features

### 1. Edge AI Crop Disease Detection
- Uses computer vision on edge cameras to automatically detect crop diseases in the field.
- Operates offline to save bandwidth and provide instant alerts.
- Optimized to run on low-power microcomputers like the Raspberry Pi.

### 2. Smart Irrigation & Sensor Engine
- Ingests real-time IoT telemetry data including soil moisture, temperature, and humidity.
- The decision engine evaluates environmental conditions (e.g., low moisture and high heat) to trigger critical, high, or low severity irrigation and heat stress alerts.

### 3. Real-time Dashboard
- A web application built with Next.js and Tailwind CSS.
- Uses Supabase WebSockets for real-time UI updates without page refreshes.
- Features live sensor charts, a crop diagnostics feed, and active farm condition alerts.

---

## Machine Learning Models

We trained custom AI models to ensure accuracy and edge compatibility:

- **Model Architecture**: MobileNetV3-Large (Transfer Learning)
- **Dataset**: PlantVillage (15 distinct crop conditions/diseases)
- **Final Test Accuracy**: 99.13%
- **Edge Optimization**: The PyTorch model was exported to ONNX format.
  - **Size**: 0.33 MB
  - **Inference Speed**: ~3.7ms per image (CPU)

*(A secondary DINOv2 feature extraction pipeline is also available in the codebase).*

---

## Project Structure

```text
SIH_Agriculture_project/
├── .env.example                          # Supabase credentials template
├── .gitignore                            # Python, Node, data, models ignored
├── database_schema.sql                   # 3 relational tables for Supabase
│
├── edge-ai/
│   ├── requirements.txt                  # Full Python deps (PyTorch, ONNX, etc.)
│   ├── mock_sensor_stream.py             # Scenario-based sensor simulator + alerts
│   ├── run_pipeline.py                   # End-to-end orchestrator (sensors + camera)
│   │
│   ├── training/
│   │   ├── dataset.py                    # PlantVillage dataset prep + augmentation
│   │   ├── train_mobilenetv3.py          # 2-stage transfer learning (MobileNetV3)
│   │   ├── train_dinov2_feature.py       # Frozen DINOv2 backbone + trainable head
│   │   └── export_onnx.py               # PyTorch → ONNX with validation
│   │
│   ├── inference/
│   │   ├── onnx_inference.py             # ONNX Runtime inference engine
│   │   └── camera_capture.py             # Simulated camera → inference → Supabase
│   │
│   └── logic/
│       ├── irrigation_advisor.py         # Multi-factor irrigation decision engine
│       ├── risk_monitor.py               # Rolling-window environmental risk detection
│       └── alert_engine.py               # Unified orchestrator + SQLite offline buffer
│
└── frontend/                             # Next.js 14 (TypeScript, App Router)
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx                # Root layout with sidebar
    │   │   ├── page.tsx                  # Overview (4 KPI cards + recent alerts)
    │   │   ├── globals.css               # Dark-mode agricultural design system
    │   │   ├── dashboard/                # Real-time sensor charts (Recharts)
    │   │   ├── diagnostics/              # Crop disease detection results grid
    │   │   └── alerts/                   # Live advisory alert feed
    │   ├── components/
    │   │   ├── Navbar.tsx                # Sidebar navigation
    │   │   ├── StatCard.tsx              # Animated KPI card
    │   │   ├── SensorChart.tsx           # Real-time Recharts line chart
    │   │   ├── DiagnosticCard.tsx        # Disease detection result card
    │   │   └── AlertFeed.tsx             # Live alert timeline with filters
    │   └── lib/
    │       ├── supabase.ts               # Null-safe Supabase client + helpers
    │       └── types.ts                  # TypeScript interfaces for all entities
    └── .env.local.example                # Frontend Supabase env template
```
