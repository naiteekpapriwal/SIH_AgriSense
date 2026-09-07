"""
Export trained MobileNetV3 crop disease model to ONNX format.

- Loads the best PyTorch checkpoint
- Exports to ONNX with dynamic batch size
- Validates the ONNX model against PyTorch outputs
- Reports model size and basic inference benchmark
"""

import sys
import time
import json
import argparse
from pathlib import Path

import torch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_mobilenetv3 import build_model
from dataset import MODELS_DIR, CLASS_LABELS_PATH, IMAGENET_MEAN, IMAGENET_STD

CHECKPOINT_PATH = MODELS_DIR / "mobilenetv3_crop_disease.pth"
ONNX_PATH = MODELS_DIR / "mobilenetv3_crop_disease.onnx"


def export_to_onnx(num_classes: int):
    """Export the best MobileNetV3 checkpoint to ONNX."""
    print("[1/3] Loading PyTorch checkpoint...")
    model = build_model(num_classes=num_classes, pretrained=False)

    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    print(f"  Loaded checkpoint — Val Acc: {checkpoint['val_acc']:.2f}%")

    # Dummy input for tracing
    dummy_input = torch.randn(1, 3, 224, 224)

    print(f"\n[2/3] Exporting to ONNX: {ONNX_PATH}")
    torch.onnx.export(
        model,
        dummy_input,
        str(ONNX_PATH),
        opset_version=13,
        input_names=["image"],
        output_names=["prediction"],
        dynamic_axes={
            "image": {0: "batch_size"},
            "prediction": {0: "batch_size"},
        },
    )

    # File size
    size_mb = ONNX_PATH.stat().st_size / (1024 * 1024)
    print(f"  ONNX model size: {size_mb:.2f} MB")

    return model, dummy_input


def validate_onnx(pytorch_model, dummy_input):
    """Validate ONNX model outputs match PyTorch outputs."""
    import onnxruntime as ort

    print(f"\n[3/3] Validating ONNX model...")

    # PyTorch inference
    with torch.no_grad():
        pytorch_output = pytorch_model(dummy_input).numpy()

    # ONNX Runtime inference
    session = ort.InferenceSession(str(ONNX_PATH))
    onnx_output = session.run(None, {"image": dummy_input.numpy()})[0]

    # Compare outputs
    max_diff = np.max(np.abs(pytorch_output - onnx_output))
    print(f"  Max output difference (PyTorch vs ONNX): {max_diff:.8f}")

    if max_diff < 1e-4:
        print("  ✓ Validation PASSED — outputs match within tolerance")
    else:
        print("  ⚠ Validation WARNING — outputs differ more than expected")

    # Benchmark ONNX inference speed
    print("\n  Benchmarking ONNX inference (100 runs on CPU)...")
    times = []
    for _ in range(100):
        start = time.perf_counter()
        session.run(None, {"image": dummy_input.numpy()})
        times.append((time.perf_counter() - start) * 1000)

    avg_ms = np.mean(times)
    p95_ms = np.percentile(times, 95)
    print(f"  Avg: {avg_ms:.1f}ms | P95: {p95_ms:.1f}ms per inference")

    if avg_ms < 50:
        print("  ✓ Inference speed target met (<50ms)")
    else:
        print(f"  ⚠ Inference is {avg_ms:.0f}ms — consider quantization for edge deployment")


def main():
    parser = argparse.ArgumentParser(description="Export MobileNetV3 to ONNX")
    parser.add_argument("--skip-validation", action="store_true", help="Skip ONNX validation step")
    args = parser.parse_args()

    print("=" * 60)
    print("  MobileNetV3 → ONNX Export")
    print("=" * 60)

    if not CHECKPOINT_PATH.exists():
        print(f"Error: No checkpoint found at {CHECKPOINT_PATH}")
        print("Please run train_mobilenetv3.py first.")
        sys.exit(1)

    # Determine number of classes from saved labels
    if CLASS_LABELS_PATH.exists():
        with open(CLASS_LABELS_PATH) as f:
            labels = json.load(f)
        num_classes = len(labels)
    else:
        print("Warning: class_labels.json not found. Defaulting to 38 classes (PlantVillage).")
        num_classes = 38

    model, dummy_input = export_to_onnx(num_classes)

    if not args.skip_validation:
        validate_onnx(model, dummy_input)

    print(f"\n  Export complete: {ONNX_PATH}")
    print("  Ready for edge deployment!")


if __name__ == "__main__":
    main()
