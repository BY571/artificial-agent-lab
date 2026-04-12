"""CIFAR-10 baseline training script.

Trains a small CNN on CIFAR-10 and outputs metrics in the format
the research lab expects.

Usage:
    python train.py
    python train.py --epochs 20 --lr 0.01 --seed 42
"""
import argparse
import json
import time

import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

from model import SimpleCNN


def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss, correct, total = 0, 0, 0
    for inputs, targets in loader:
        inputs, targets = inputs.to(device), targets.to(device)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * inputs.size(0)
        correct += outputs.argmax(1).eq(targets).sum().item()
        total += inputs.size(0)
    return total_loss / total, correct / total


def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0, 0, 0
    with torch.no_grad():
        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            total_loss += loss.item() * inputs.size(0)
            correct += outputs.argmax(1).eq(targets).sum().item()
            total += inputs.size(0)
    return total_loss / total, correct / total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-dir", default="./data")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Data — basic normalization only
    transform_train = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
    ])
    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
    ])

    train_set = datasets.CIFAR10(args.data_dir, train=True, download=True, transform=transform_train)
    test_set = datasets.CIFAR10(args.data_dir, train=False, download=True, transform=transform_test)
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, num_workers=2)
    test_loader = DataLoader(test_set, batch_size=args.batch_size, shuffle=False, num_workers=2)

    model = SimpleCNN().to(device)
    optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=0.9)
    criterion = nn.CrossEntropyLoss()

    start = time.time()
    best_acc = 0

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, criterion, device)
        test_loss, test_acc = evaluate(model, test_loader, criterion, device)
        best_acc = max(best_acc, test_acc)
        print(f"Epoch {epoch}/{args.epochs} | "
              f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
              f"test_loss={test_loss:.4f} test_acc={test_acc:.4f}")

    duration = time.time() - start

    # Output metrics in the format the lab expects
    metrics = {
        "test_accuracy": round(test_acc * 100, 2),
        "best_accuracy": round(best_acc * 100, 2),
        "test_loss": round(test_loss, 4),
        "train_accuracy": round(train_acc * 100, 2),
        "train_loss": round(train_loss, 4),
        "epochs": args.epochs,
        "lr": args.lr,
        "params": sum(p.numel() for p in model.parameters()),
        "duration_s": round(duration, 1),
    }

    print("\n===METRICS_JSON===")
    print(json.dumps(metrics))
    print("===END_METRICS_JSON===")


if __name__ == "__main__":
    main()
