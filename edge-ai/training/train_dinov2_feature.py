"""
DINOv2 feature extraction + lightweight classification head for crop disease.

Uses DINOv2 ViT-Small (dinov2_vits14) as a frozen backbone.
Only trains a 2-layer classification head on the extracted [CLS] token features.
This approach is fast, data-efficient, and produces strong results on fine-grained
visual tasks like plant disease recognition.
"""

import sys
import time
import argparse
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset import get_dataloaders, MODELS_DIR


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CHECKPOINT_PATH = MODELS_DIR / "dinov2_crop_disease.pth"


# ─── Model ───────────────────────────────────────────────────────────────────
class DINOv2Classifier(nn.Module):
    """
    DINOv2 ViT-Small backbone (frozen) + lightweight classification head.

    Architecture:
        DINOv2 ViT-Small (384-dim [CLS] token)
        └── Linear(384→128) → GELU → Dropout(0.2) → Linear(128→num_classes)
    """

    def __init__(self, num_classes: int, backbone_name: str = "dinov2_vits14"):
        super().__init__()

        # Load DINOv2 backbone from torch.hub (Facebook Research)
        self.backbone = torch.hub.load("facebookresearch/dinov2", backbone_name)
        self.backbone.eval()  # Always in eval mode

        # Freeze all backbone parameters
        for param in self.backbone.parameters():
            param.requires_grad = False

        # Get embedding dimension from the backbone
        embed_dim = self.backbone.embed_dim  # 384 for vits14

        # Lightweight classification head
        self.head = nn.Sequential(
            nn.Linear(embed_dim, 128),
            nn.GELU(),
            nn.Dropout(p=0.2),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        # Extract [CLS] token features (frozen, no gradients)
        with torch.no_grad():
            features = self.backbone(x)  # (batch, embed_dim)
        # Pass through trainable head
        return self.head(features)


# ─── Training Utilities ──────────────────────────────────────────────────────
def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()  # Only head enters train mode; backbone stays eval via forward()
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

    return running_loss / total, 100.0 * correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
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

    return running_loss / total, 100.0 * correct / total


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train DINOv2 classifier for crop disease")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true", help="Run 1 epoch for smoke testing")
    args = parser.parse_args()

    if args.dry_run:
        args.epochs = 1

    print("=" * 70)
    print("  DINOv2 Feature Extractor — Crop Disease Classification")
    print("=" * 70)
    print(f"  Device: {DEVICE}")
    print(f"  Backbone: dinov2_vits14 (frozen)")
    print(f"  Epochs: {args.epochs} | LR: {args.lr}")
    print()

    # Load data
    print("[1/3] Loading dataset...")
    train_loader, val_loader, test_loader, classes = get_dataloaders(
        batch_size=args.batch_size, num_workers=args.num_workers
    )
    num_classes = len(classes)

    # Build model
    print("\n[2/3] Loading DINOv2 backbone (first run will download weights)...")
    model = DINOv2Classifier(num_classes=num_classes)
    model = model.to(DEVICE)

    head_params = sum(p.numel() for p in model.head.parameters())
    backbone_params = sum(p.numel() for p in model.backbone.parameters())
    print(f"  Backbone params (frozen): {backbone_params:,}")
    print(f"  Head params (trainable): {head_params:,}")

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.head.parameters(), lr=args.lr)

    # Training
    print(f"\n[3/3] Training classification head for {args.epochs} epochs...")
    best_val_loss = float("inf")

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, DEVICE)
        val_loss, val_acc = evaluate(model, val_loader, criterion, DEVICE)

        elapsed = time.time() - epoch_start
        print(f"  Epoch {epoch}/{args.epochs} ({elapsed:.1f}s) | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.2f}% | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.2f}%")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "head_state_dict": model.head.state_dict(),
                "num_classes": num_classes,
                "val_loss": val_loss,
                "val_acc": val_acc,
                "epoch": epoch,
            }, CHECKPOINT_PATH)
            print(f"    ✓ Saved best checkpoint (val_loss: {val_loss:.4f})")

    # Final evaluation
    print("\n" + "=" * 70)
    print("  Final Evaluation on Test Set")
    print("=" * 70)

    checkpoint = torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=True)
    model.head.load_state_dict(checkpoint["head_state_dict"])

    test_loss, test_acc = evaluate(model, test_loader, criterion, DEVICE)
    print(f"  Test Loss: {test_loss:.4f} | Test Accuracy: {test_acc:.2f}%")
    print(f"  Checkpoint: {CHECKPOINT_PATH}")
    print("  Done!")


if __name__ == "__main__":
    main()
