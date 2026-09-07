"""
ONNX Runtime inference engine for crop disease classification.

Loads the exported ONNX model and provides a simple API for running
inference on individual images. Designed for edge deployment.
"""

import json
import time
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    raise ImportError("onnxruntime is required. Install with: pip install onnxruntime")


# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
ONNX_PATH = MODELS_DIR / "mobilenetv3_crop_disease.onnx"
CLASS_LABELS_PATH = MODELS_DIR / "class_labels.json"

# ImageNet normalization
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# ─── Inference Engine ────────────────────────────────────────────────────────
class CropDiseaseClassifier:
    """
    ONNX-based crop disease classifier.

    Usage:
        classifier = CropDiseaseClassifier()
        results = classifier.predict("path/to/leaf_image.jpg", top_k=3)
        # [{"class": "Tomato___Late_blight", "confidence": 0.95}, ...]
    """

    def __init__(self, model_path: str = None, labels_path: str = None):
        self.model_path = Path(model_path) if model_path else ONNX_PATH
        self.labels_path = Path(labels_path) if labels_path else CLASS_LABELS_PATH

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"ONNX model not found at {self.model_path}\n"
                "Run training/export_onnx.py first."
            )

        # Load ONNX model
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )

        # Load class labels
        if self.labels_path.exists():
            with open(self.labels_path) as f:
                self.labels = json.load(f)
            # Ensure keys are integers
            self.labels = {int(k): v for k, v in self.labels.items()}
        else:
            self.labels = None
            print("Warning: class_labels.json not found. Predictions will use indices.")

        self.input_name = self.session.get_inputs()[0].name

    def preprocess(self, image_path: str) -> np.ndarray:
        """Load and preprocess an image for inference."""
        img = Image.open(image_path).convert("RGB")

        # Resize to 256, then center crop to 224
        img = img.resize((256, 256), Image.BILINEAR)
        left = (256 - 224) // 2
        top = (256 - 224) // 2
        img = img.crop((left, top, left + 224, top + 224))

        # Convert to numpy and normalize
        img_array = np.array(img, dtype=np.float32) / 255.0
        img_array = (img_array - IMAGENET_MEAN) / IMAGENET_STD

        # HWC → CHW and add batch dimension
        img_array = np.transpose(img_array, (2, 0, 1))
        img_array = np.expand_dims(img_array, axis=0)

        return img_array

    def predict(self, image_path: str, top_k: int = 5) -> list[dict]:
        """
        Run inference on a single image.

        Returns list of top-k predictions:
            [{"class": "Apple___Apple_scab", "confidence": 0.95, "index": 0}, ...]
        """
        start_time = time.perf_counter()

        # Preprocess
        input_tensor = self.preprocess(image_path)

        # Inference
        outputs = self.session.run(None, {self.input_name: input_tensor})
        logits = outputs[0][0]  # Remove batch dimension

        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probabilities = exp_logits / exp_logits.sum()

        # Top-k
        top_indices = np.argsort(probabilities)[::-1][:top_k]

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        results = []
        for idx in top_indices:
            class_name = self.labels.get(int(idx), f"class_{idx}") if self.labels else f"class_{idx}"
            results.append({
                "class": class_name,
                "confidence": float(probabilities[idx]),
                "index": int(idx),
            })

        return results, elapsed_ms

    def predict_batch(self, image_paths: list[str], top_k: int = 5) -> list:
        """Run inference on multiple images."""
        all_results = []
        for path in image_paths:
            results, elapsed = self.predict(path, top_k=top_k)
            all_results.append({
                "image": str(path),
                "predictions": results,
                "inference_ms": elapsed,
            })
        return all_results


# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Run crop disease inference on an image")
    parser.add_argument("--image", type=str, required=True, help="Path to input image")
    parser.add_argument("--model", type=str, default=None, help="Path to ONNX model")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top predictions")
    args = parser.parse_args()

    print("=" * 60)
    print("  Crop Disease Classifier — ONNX Inference")
    print("=" * 60)

    classifier = CropDiseaseClassifier(model_path=args.model)

    results, elapsed = classifier.predict(args.image, top_k=args.top_k)

    print(f"\n  Image: {args.image}")
    print(f"  Inference time: {elapsed:.1f}ms")
    print(f"\n  Top-{args.top_k} Predictions:")
    print(f"  {'Rank':<6} {'Class':<40} {'Confidence':>10}")
    print(f"  {'─'*6} {'─'*40} {'─'*10}")

    for i, pred in enumerate(results, 1):
        conf_pct = pred["confidence"] * 100
        bar = "█" * int(conf_pct / 5) + "░" * (20 - int(conf_pct / 5))
        print(f"  {i:<6} {pred['class']:<40} {conf_pct:>8.2f}%  {bar}")


if __name__ == "__main__":
    main()
