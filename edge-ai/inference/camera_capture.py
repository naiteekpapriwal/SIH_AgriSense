"""
Simulated camera capture pipeline.

Reads images from a local test_images/ directory (simulating an edge camera feed),
runs ONNX inference, and pushes crop diagnostic results to Supabase.
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Add parent dirs to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "inference"))

from onnx_inference import CropDiseaseClassifier

# Load environment
load_dotenv(dotenv_path=BASE_DIR.parent / ".env")


DEVICE_ID = "edge-device-sih-01"
TEST_IMAGES_DIR = BASE_DIR / "test_images"


def get_supabase_client():
    """Initialize Supabase client."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("Warning: Supabase credentials not set. Results will only be printed locally.")
        return None

    return create_client(url, key)


def push_diagnostic(supabase, result: dict):
    """Push a crop diagnostic result to Supabase."""
    if supabase is None:
        return

    top_pred = result["predictions"][0] if result["predictions"] else None

    data = {
        "device_id": DEVICE_ID,
        "image_url": result["image"],
        "disease_detected": top_pred["class"] if top_pred else None,
        "confidence_score": round(top_pred["confidence"] * 100, 2) if top_pred else None,
    }

    try:
        supabase.table("crop_diagnostics").insert(data).execute()
        print(f"  → Pushed to Supabase: {data['disease_detected']} ({data['confidence_score']}%)")
    except Exception as e:
        print(f"  ✗ Supabase push failed: {e}")


def run_capture_loop(classifier, supabase, interval: int = 30, max_captures: int = None):
    """
    Continuously process images from the test_images directory.

    Args:
        interval: Seconds between capture cycles
        max_captures: Maximum number of images to process (None = unlimited)
    """
    if not TEST_IMAGES_DIR.exists():
        TEST_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Created {TEST_IMAGES_DIR}/ — add test images (.jpg, .png) to this folder.")
        return

    image_extensions = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}
    images = [f for f in TEST_IMAGES_DIR.iterdir() if f.suffix in image_extensions]

    if not images:
        print(f"No images found in {TEST_IMAGES_DIR}/")
        print("Add test leaf/plant images to simulate the camera feed.")
        return

    print(f"Found {len(images)} images in {TEST_IMAGES_DIR}/")
    print(f"Capture interval: {interval}s")
    print("Press Ctrl+C to stop.\n")

    capture_count = 0
    image_index = 0

    try:
        while True:
            image_path = images[image_index % len(images)]
            image_index += 1
            capture_count += 1

            print(f"[Capture {capture_count}] Processing: {image_path.name}")

            # Run inference
            predictions, elapsed_ms = classifier.predict(str(image_path), top_k=3)

            # Display results
            top = predictions[0]
            print(f"  Detected: {top['class']} (confidence: {top['confidence']*100:.1f}%)")
            print(f"  Inference time: {elapsed_ms:.1f}ms")

            # Push to Supabase
            result = {"image": str(image_path), "predictions": predictions}
            push_diagnostic(supabase, result)

            if max_captures and capture_count >= max_captures:
                print(f"\nReached max captures ({max_captures}). Stopping.")
                break

            print(f"  Next capture in {interval}s...\n")
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\nStopped after {capture_count} captures.")


def main():
    parser = argparse.ArgumentParser(description="Simulated camera capture pipeline")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between captures")
    parser.add_argument("--max-captures", type=int, default=None, help="Max number of captures")
    parser.add_argument("--model", type=str, default=None, help="Path to ONNX model")
    parser.add_argument("--no-supabase", action="store_true", help="Disable Supabase push")
    args = parser.parse_args()

    print("=" * 60)
    print("  Camera Capture Simulation Pipeline")
    print("=" * 60)

    classifier = CropDiseaseClassifier(model_path=args.model)
    supabase = None if args.no_supabase else get_supabase_client()

    run_capture_loop(classifier, supabase, interval=args.interval, max_captures=args.max_captures)


if __name__ == "__main__":
    main()
