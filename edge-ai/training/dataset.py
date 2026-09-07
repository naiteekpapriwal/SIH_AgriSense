"""
Dataset preparation for PlantVillage crop disease classification.

Downloads (if needed), organizes, and provides PyTorch Dataset/DataLoader
utilities with proper augmentation pipelines for training, validation, and test splits.
"""

import os
import json
import shutil
import random
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "PlantVillage"
MODELS_DIR = BASE_DIR / "models"

TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"
TEST_DIR = DATA_DIR / "test"

CLASS_LABELS_PATH = MODELS_DIR / "class_labels.json"


# ─── Transform Pipelines ────────────────────────────────────────────────────
# ImageNet normalization constants (used because we transfer-learn from ImageNet)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

train_transforms = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(p=0.2),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1, hue=0.05),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])

val_transforms = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])

# Test uses the same pipeline as validation
test_transforms = val_transforms


# ─── Dataset Splitting ───────────────────────────────────────────────────────
def split_dataset(source_dir: str, train_ratio=0.8, val_ratio=0.1, seed=42):
    """
    Splits a flat ImageFolder-style directory into train/val/test subdirectories.

    Expects:
        source_dir/
            class_a/
                img1.jpg
                img2.jpg
            class_b/
                ...

    Produces:
        data/PlantVillage/train/class_a/...
        data/PlantVillage/val/class_a/...
        data/PlantVillage/test/class_a/...
    """
    source = Path(source_dir)
    if not source.exists():
        raise FileNotFoundError(
            f"Source directory not found: {source}\n"
            "Please download the PlantVillage dataset and place it at:\n"
            f"  {DATA_DIR}\n"
            "You can download it from Kaggle:\n"
            "  https://www.kaggle.com/datasets/emmarex/plantdisease"
        )

    random.seed(seed)

    # Create output directories
    for split_dir in [TRAIN_DIR, VAL_DIR, TEST_DIR]:
        split_dir.mkdir(parents=True, exist_ok=True)

    classes = sorted([d.name for d in source.iterdir() if d.is_dir()])
    print(f"Found {len(classes)} classes")

    stats = {"train": 0, "val": 0, "test": 0}

    for cls_name in classes:
        cls_path = source / cls_name
        images = list(cls_path.glob("*.[jJpP][pPnN][gG]"))  # jpg, JPG, png, PNG
        images += list(cls_path.glob("*.jpeg"))
        images += list(cls_path.glob("*.JPEG"))
        random.shuffle(images)

        n = len(images)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        splits = {
            "train": images[:train_end],
            "val": images[train_end:val_end],
            "test": images[val_end:],
        }

        for split_name, split_images in splits.items():
            dest = Path({"train": TRAIN_DIR, "val": VAL_DIR, "test": TEST_DIR}[split_name]) / cls_name
            dest.mkdir(parents=True, exist_ok=True)
            for img_path in split_images:
                shutil.copy2(str(img_path), str(dest / img_path.name))
            stats[split_name] += len(split_images)

    print(f"Split complete: train={stats['train']}, val={stats['val']}, test={stats['test']}")
    return stats


# ─── Class Label Export ──────────────────────────────────────────────────────
def save_class_labels(dataset: datasets.ImageFolder):
    """Saves class index → class name mapping as JSON."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    labels = {v: k for k, v in dataset.class_to_idx.items()}
    with open(CLASS_LABELS_PATH, "w") as f:
        json.dump(labels, f, indent=2)
    print(f"Saved {len(labels)} class labels to {CLASS_LABELS_PATH}")
    return labels


# ─── DataLoader Factory ─────────────────────────────────────────────────────
def get_dataloaders(batch_size=32, num_workers=4):
    """
    Returns train, val, and test DataLoaders.
    Assumes the data has already been split into train/val/test directories.
    """
    if not TRAIN_DIR.exists():
        raise FileNotFoundError(
            f"Training data not found at {TRAIN_DIR}.\n"
            "Run `python dataset.py` first to split the dataset."
        )

    train_dataset = datasets.ImageFolder(str(TRAIN_DIR), transform=train_transforms)
    val_dataset = datasets.ImageFolder(str(VAL_DIR), transform=val_transforms)
    test_dataset = datasets.ImageFolder(str(TEST_DIR), transform=test_transforms)

    # Save class labels
    save_class_labels(train_dataset)

    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True, drop_last=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )
    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )

    print(f"Classes: {len(train_dataset.classes)}")
    print(f"Train: {len(train_dataset)} | Val: {len(val_dataset)} | Test: {len(test_dataset)}")

    return train_loader, val_loader, test_loader, train_dataset.classes


# ─── CLI Entry Point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare PlantVillage dataset")
    parser.add_argument(
        "--source", type=str, default=str(DATA_DIR / "raw"),
        help="Path to the raw PlantVillage directory with class subfolders"
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--split-only", action="store_true", help="Only split, don't create loaders")
    args = parser.parse_args()

    print("=" * 60)
    print("  PlantVillage Dataset Preparation")
    print("=" * 60)

    # Step 1: Split if train dir doesn't exist yet
    if not TRAIN_DIR.exists() or len(list(TRAIN_DIR.iterdir())) == 0:
        print("\n[1/2] Splitting dataset...")
        split_dataset(args.source)
    else:
        print(f"\n[1/2] Train directory already exists at {TRAIN_DIR}, skipping split.")

    if not args.split_only:
        # Step 2: Validate by creating loaders
        print("\n[2/2] Creating DataLoaders (validation)...")
        train_loader, val_loader, test_loader, classes = get_dataloaders(batch_size=args.batch_size)

        # Quick sanity check
        batch = next(iter(train_loader))
        print(f"\nSanity check — batch shape: {batch[0].shape}, labels shape: {batch[1].shape}")
        print("Dataset preparation complete!")
