"""
MobileNetV3-Large fine-tuning for crop disease classification.

Two-stage transfer learning:
  Stage 1: Train only the classifier head (frozen backbone)
  Stage 2: Fine-tune top layers with lower learning rate

Uses PlantVillage dataset via the dataset.py module.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
import torchvision.models as models

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset import get_dataloaders, MODELS_DIR, CLASS_LABELS_PATH


# ─── Configuration ───────────────────────────────────────────────────────────
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
CHECKPOINT_PATH = MODELS_DIR / "mobilenetv3_crop_disease.pth"


# ─── Model Builder ───────────────────────────────────────────────────────────
def build_model(num_classes: int, pretrained: bool = True) -> nn.Module:
    """
    Builds MobileNetV3-Large with a custom classification head.

    Architecture:
        MobileNetV3-Large backbone (ImageNet pretrained)
        └── Custom head: Linear(960→256) → ReLU → Dropout(0.3) → Linear(256→num_classes)
    """
    weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_large(weights=weights)

    # Replace the classifier head
    in_features = model.classifier[0].in_features  # 960
    model.classifier = nn.Sequential(
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.3),
        nn.Linear(256, num_classes),
    )

    return model


def freeze_backbone(model: nn.Module):
    """Freeze all parameters except the classifier head."""
    for param in model.features.parameters():
        param.requires_grad = False


def unfreeze_top_layers(model: nn.Module, unfreeze_from: int = 8):
    """
    Unfreeze the top portion of the backbone for fine-tuning.
    MobileNetV3-Large has 16 inverted residual blocks (indices 0-15).
    Default unfreezes from block 8 onwards (~50% of the network).
    """
    for i, block in enumerate(model.features):
        if i >= unfreeze_from:
            for param in block.parameters():
                param.requires_grad = True


# ─── Training Loop ───────────────────────────────────────────────────────────
def train_one_epoch(model, loader, criterion, optimizer, device):
    """Train for one epoch. Returns (avg_loss, accuracy)."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (images, labels) in enumerate(loader):
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

        if (batch_idx + 1) % 50 == 0:
            print(f"    Batch {batch_idx+1}/{len(loader)} — "
                  f"Loss: {loss.item():.4f} | Acc: {100.*correct/total:.2f}%")

    avg_loss = running_loss / total
    accuracy = 100.0 * correct / total
    return avg_loss, accuracy


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    """Evaluate model. Returns (avg_loss, accuracy)."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)

        running_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    avg_loss = running_loss / total
    accuracy = 100.0 * correct / total
    return avg_loss, accuracy


def train(
    model: nn.Module,
    train_loader,
    val_loader,
    criterion,
    optimizer,
    scheduler,
    device,
    num_epochs: int,
    stage_name: str,
    patience: int = 5,
):
    """
    Full training loop with early stopping.
    Saves the best model checkpoint based on validation loss.
    """
    best_val_loss = float("inf")
    epochs_without_improvement = 0

    for epoch in range(1, num_epochs + 1):
        epoch_start = time.time()

        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)

        if scheduler is not None:
            scheduler.step()

        elapsed = time.time() - epoch_start
        lr = optimizer.param_groups[0]["lr"]

        print(f"  [{stage_name}] Epoch {epoch}/{num_epochs} ({elapsed:.1f}s) | "
              f"LR: {lr:.2e} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.2f}% | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.2f}%")

        # Save best checkpoint
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_without_improvement = 0
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state_dict": model.state_dict(),
                "val_loss": val_loss,
                "val_acc": val_acc,
                "epoch": epoch,
                "stage": stage_name,
            }, CHECKPOINT_PATH)
            print(f"    ✓ Saved best checkpoint (val_loss: {val_loss:.4f})")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(f"    ✗ Early stopping after {patience} epochs without improvement")
                break

    return best_val_loss


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train MobileNetV3 for crop disease classification")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--stage1-epochs", type=int, default=5, help="Epochs for head-only training")
    parser.add_argument("--stage2-epochs", type=int, default=15, help="Epochs for fine-tuning")
    parser.add_argument("--stage1-lr", type=float, default=1e-3, help="Learning rate for stage 1")
    parser.add_argument("--stage2-lr", type=float, default=3e-5, help="Learning rate for stage 2")
    parser.add_argument("--patience", type=int, default=5, help="Early stopping patience")
    parser.add_argument("--num-workers", type=int, default=4, help="DataLoader workers")
    parser.add_argument("--dry-run", action="store_true", help="Run 2 epochs of each stage for smoke testing")
    args = parser.parse_args()

    if args.dry_run:
        args.stage1_epochs = 1
        args.stage2_epochs = 1
        args.patience = 99

    print("=" * 70)
    print("  MobileNetV3 Crop Disease Classifier — Training")
    print("=" * 70)
    print(f"  Device: {DEVICE}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Stage 1: {args.stage1_epochs} epochs, LR={args.stage1_lr}")
    print(f"  Stage 2: {args.stage2_epochs} epochs, LR={args.stage2_lr}")
    print()

    # Load data
    print("[1/4] Loading dataset...")
    train_loader, val_loader, test_loader, classes = get_dataloaders(
        batch_size=args.batch_size, num_workers=args.num_workers
    )
    num_classes = len(classes)
    print(f"  Classes: {num_classes}")

    # Build model
    print("\n[2/4] Building MobileNetV3-Large model...")
    model = build_model(num_classes=num_classes, pretrained=True)
    model = model.to(DEVICE)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Total params: {total:,} | Trainable: {trainable:,}")

    criterion = nn.CrossEntropyLoss()

    # ── Stage 1: Train head only ──────────────────────────────────────────
    print("\n[3/4] Stage 1 — Training classifier head (backbone frozen)...")
    freeze_backbone(model)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Trainable params (head only): {trainable:,}")

    optimizer_s1 = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.stage1_lr
    )

    train(
        model, train_loader, val_loader, criterion,
        optimizer_s1, scheduler=None, device=DEVICE,
        num_epochs=args.stage1_epochs, stage_name="Stage 1 — Head",
        patience=args.patience
    )

    # ── Stage 2: Fine-tune top layers ─────────────────────────────────────
    print(f"\n[4/4] Stage 2 — Fine-tuning (unfreezing top 50% of backbone)...")
    unfreeze_top_layers(model, unfreeze_from=8)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Trainable params (partial unfreeze): {trainable:,}")

    optimizer_s2 = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.stage2_lr, weight_decay=0.01
    )
    scheduler_s2 = CosineAnnealingLR(optimizer_s2, T_max=args.stage2_epochs, eta_min=1e-6)

    train(
        model, train_loader, val_loader, criterion,
        optimizer_s2, scheduler=scheduler_s2, device=DEVICE,
        num_epochs=args.stage2_epochs, stage_name="Stage 2 — Fine-tune",
        patience=args.patience
    )

    # ── Final Evaluation ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  Final Evaluation on Test Set")
    print("=" * 70)

    # Load best checkpoint
    checkpoint = torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    print(f"  Loaded best checkpoint from {checkpoint['stage']} epoch {checkpoint['epoch']}")

    test_loss, test_acc = evaluate(model, test_loader, criterion, DEVICE)
    print(f"  Test Loss: {test_loss:.4f} | Test Accuracy: {test_acc:.2f}%")
    print(f"\n  Checkpoint saved to: {CHECKPOINT_PATH}")
    print(f"  Class labels saved to: {CLASS_LABELS_PATH}")
    print("  Training complete!")


if __name__ == "__main__":
    main()
