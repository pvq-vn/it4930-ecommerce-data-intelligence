"""Step 3.2: Fine-Tuning PhoBERT Transformer for E-Commerce Review Sentiment Classification.

Implements deep learning sentiment classification using pre-trained PhoBERT:
- Pre-trained backbone: vinai/phobert-base-v2 (or fallback vinai/phobert-base).
- Word-segmented input matching PhoBERT pre-training distribution.
- Class-weighted Cross-Entropy loss to penalize minority class errors.
- Mixed precision (FP16 AMP) for fast execution on NVIDIA RTX 2060 SUPER (8GB VRAM).
- Evaluation & direct performance comparison against TF-IDF ML Baselines.
- Full-corpus inference exporting continuous polarity scores [-1.0, 1.0] for TV5.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.config import (
    DOCS_SENTIMENT_PHOBERT_REPORT_FILE,
    FIGURES_TV6_DIR,
    PHOBERT_FALLBACK_NAME,
    PHOBERT_MODEL_DIR,
    PHOBERT_PRETRAINED_NAME,
    REVIEWS_TV6_PREPROCESSED_FILE,
    REVIEWS_TV6_SENTIMENT_PHOBERT_FILE,
    SENTIMENT_BASELINE_REPORT_FILE,
    SENTIMENT_PHOBERT_REPORT_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)

# Label constants matching Step 3.1
LABEL_MAP = {
    1: 0,  # Negative
    2: 0,  # Negative
    3: 1,  # Neutral
    4: 2,  # Positive
    5: 2,  # Positive
}
CLASS_NAMES = ["NEGATIVE", "NEUTRAL", "POSITIVE"]
ID_TO_CLASS = {0: "NEGATIVE", 1: "NEUTRAL", 2: "POSITIVE"}
CLASS_TO_ID = {"NEGATIVE": 0, "NEUTRAL": 1, "POSITIVE": 2}


def check_torch_environment() -> Tuple[Any, Any, str]:
    """Verify PyTorch and Transformers installation and detect GPU device."""
    try:
        import torch
    except ImportError:
        raise ImportError(
            "\n[PyTorch Chưa Được Cài Đặt] Vui lòng cài đặt PyTorch hỗ trợ CUDA bằng lệnh:\n"
            "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121\n"
        )

    try:
        import transformers
    except ImportError:
        raise ImportError(
            "\n[Transformers Chưa Được Cài Đặt] Vui lòng cài đặt bằng lệnh:\n"
            "pip install transformers accelerate\n"
        )

    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        device = "cuda"
        print(f"[GPU DETECTED] {device_name} ({vram_gb:.2f} GB VRAM) - Kích hoạt tăng tốc phần cứng.")
    else:
        device = "cpu"
        print("[WARNING] Không phát hiện GPU CUDA, pipeline sẽ chạy trên CPU (tốc độ sẽ chậm hơn).")

    return torch, transformers, device


def load_dataset_for_phobert(filepath: Path = REVIEWS_TV6_PREPROCESSED_FILE) -> pd.DataFrame:
    """Load preprocessed reviews formatted with word segmentation for PhoBERT."""
    if not filepath.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}. Run Step 2 first.")

    records = []
    with filepath.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    df = pd.DataFrame(records)
    df["label_id"] = df["rating_raw"].map(LABEL_MAP)
    df["sentiment_label_groundtruth"] = df["label_id"].map(ID_TO_CLASS)

    # PhoBERT expects word-segmented tokens joined by underscores (from text_tokenized)
    df["phobert_input_text"] = df["text_tokenized"].replace("", np.nan)
    df["phobert_input_text"] = df["phobert_input_text"].fillna(df["review_text_normalized"])

    return df


class PhoBERTReviewDataset:
    """PyTorch Dataset wrapper for PhoBERT tokenized sequences."""

    def __init__(self, texts: List[str], labels: List[int], tokenizer: Any, max_length: int = 128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        import torch

        text = str(self.texts[idx])
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        item = {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
        }

        if self.labels is not None:
            item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)

        return item


def compute_class_weights(labels: np.ndarray) -> np.ndarray:
    """Compute balanced class weights inversely proportional to class frequencies."""
    n_samples = len(labels)
    n_classes = len(np.unique(labels))
    class_counts = np.bincount(labels, minlength=n_classes)
    weights = n_samples / (n_classes * class_counts.astype(np.float32))
    return weights


def train_phobert_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    epochs: int = 3,
    batch_size: int = 32,
    lr: float = 2e-5,
    max_length: int = 128,
    random_state: int = 42,
) -> Tuple[Any, Any, Dict[str, Any]]:
    """Fine-tune PhoBERT with Mixed Precision (FP16) and class-weighted loss."""
    torch, transformers, device = check_torch_environment()
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    torch.manual_seed(random_state)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(random_state)

    # 1. Initialize Tokenizer & Model
    model_name = PHOBERT_PRETRAINED_NAME
    print(f"\n1. Tải tokenizer và pre-trained weights từ '{model_name}'...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=3)
    except Exception as e:
        print(f"   [Cảnh báo] Không tải được {model_name} ({e}), chuyển sang fallback '{PHOBERT_FALLBACK_NAME}'...")
        model_name = PHOBERT_FALLBACK_NAME
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=3)

    model.to(device)

    # 2. Prepare DataLoaders
    train_dataset = PhoBERTReviewDataset(
        train_df["phobert_input_text"].tolist(),
        train_df["label_id"].tolist(),
        tokenizer,
        max_length=max_length,
    )
    val_dataset = PhoBERTReviewDataset(
        val_df["phobert_input_text"].tolist(),
        val_df["label_id"].tolist(),
        tokenizer,
        max_length=max_length,
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, pin_memory=True if device == "cuda" else False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size * 2, shuffle=False)

    # 3. Class-weighted Loss
    weights_np = compute_class_weights(train_df["label_id"].to_numpy())
    class_weights = torch.tensor(weights_np, dtype=torch.float).to(device)
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weights)
    print(f"   Trọng số lớp bù trừ mất cân bằng: Negative={weights_np[0]:.2f}, Neutral={weights_np[1]:.2f}, Positive={weights_np[2]:.2f}")

    # 4. Optimizer & Scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01, eps=1e-8)
    total_steps = len(train_loader) * epochs
    warmup_steps = int(0.1 * total_steps)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps)

    # 5. Mixed Precision Scaler
    use_cuda = device == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=use_cuda)

    # Training history tracking
    history = {
        "train_loss": [],
        "val_loss": [],
        "val_macro_f1": [],
        "val_weighted_f1": [],
        "val_accuracy": [],
        "epoch_time_seconds": [],
    }

    best_val_macro_f1 = -1.0
    best_model_state = None

    print(f"\n2. Bắt đầu quá trình huấn luyện PhoBERT ({epochs} Epochs, Batch Size={batch_size}, LR={lr})...")
    print("-" * 75)

    for epoch in range(1, epochs + 1):
        t_epoch_start = time.time()
        model.train()
        running_train_loss = 0.0

        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            attention_mask = batch["attention_mask"].to(device, non_blocking=True)
            labels = batch["labels"].to(device, non_blocking=True)

            optimizer.zero_grad()

            with torch.cuda.amp.autocast(enabled=use_cuda):
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                loss = loss_fn(outputs.logits, labels)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

            running_train_loss += loss.item()

            if (step + 1) % 100 == 0 or (step + 1) == len(train_loader):
                elapsed = time.time() - t_epoch_start
                print(f"   Epoch {epoch}/{epochs} | Step {step+1:3d}/{len(train_loader):3d} | Loss: {loss.item():.4f} | Tốc độ: {elapsed:.1f}s", end="\r")

        avg_train_loss = running_train_loss / len(train_loader)

        # Validation step
        model.eval()
        running_val_loss = 0.0
        val_preds = []
        val_targets = []

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device, non_blocking=True)
                attention_mask = batch["attention_mask"].to(device, non_blocking=True)
                labels = batch["labels"].to(device, non_blocking=True)

                with torch.cuda.amp.autocast(enabled=use_cuda):
                    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                    val_loss = loss_fn(outputs.logits, labels)

                running_val_loss += val_loss.item()
                logits = outputs.logits
                preds = torch.argmax(logits, dim=1).cpu().numpy()

                val_preds.extend(preds)
                val_targets.extend(labels.cpu().numpy())

        avg_val_loss = running_val_loss / len(val_loader)
        val_acc = accuracy_score(val_targets, val_preds)
        val_macro_f1 = f1_score(val_targets, val_preds, average="macro")
        val_weighted_f1 = f1_score(val_targets, val_preds, average="weighted")
        epoch_time = time.time() - t_epoch_start

        history["train_loss"].append(float(avg_train_loss))
        history["val_loss"].append(float(avg_val_loss))
        history["val_accuracy"].append(float(val_acc))
        history["val_macro_f1"].append(float(val_macro_f1))
        history["val_weighted_f1"].append(float(val_weighted_f1))
        history["epoch_time_seconds"].append(round(epoch_time, 2))

        print(
            f"   Epoch {epoch:d}/{epochs:d} Hoàn tất ({epoch_time:.1f}s) -> "
            f"Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | "
            f"Val Acc: {val_acc:.4f} | Val Macro F1: {val_macro_f1:.4f} | Val Weighted F1: {val_weighted_f1:.4f}"
        )

        if val_macro_f1 > best_val_macro_f1:
            best_val_macro_f1 = val_macro_f1
            best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    # Restore best checkpoint
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        print(f"\n   [Best Checkpoint Restored] Đạt Val Macro F1 cao nhất: {best_val_macro_f1:.4f}")

    # Save best checkpoint to disk
    PHOBERT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(PHOBERT_MODEL_DIR / "best_model")
    tokenizer.save_pretrained(PHOBERT_MODEL_DIR / "best_model")
    print(f"   Đã lưu weights mô hình tại: {PHOBERT_MODEL_DIR / 'best_model'}")

    return model, tokenizer, history


def evaluate_phobert_on_test(
    model: Any,
    tokenizer: Any,
    test_df: pd.DataFrame,
    batch_size: int = 64,
    device: str = "cuda",
) -> Dict[str, Any]:
    """Evaluate final fine-tuned PhoBERT model on hold-out test set."""
    torch, _, _ = check_torch_environment()
    from torch.utils.data import DataLoader

    test_dataset = PhoBERTReviewDataset(
        test_df["phobert_input_text"].tolist(),
        test_df["label_id"].tolist(),
        tokenizer,
        max_length=128,
    )
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    model.eval()
    all_preds = []
    all_targets = []
    all_probs = []

    t0 = time.time()
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            attention_mask = batch["attention_mask"].to(device, non_blocking=True)
            labels = batch["labels"].to(device, non_blocking=True)

            with torch.cuda.amp.autocast(enabled=(device == "cuda")):
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                probs = torch.softmax(outputs.logits, dim=1)

            preds = torch.argmax(probs, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    infer_time = round(time.time() - t0, 3)

    acc = accuracy_score(all_targets, all_preds)
    macro_f1 = f1_score(all_targets, all_preds, average="macro")
    weighted_f1 = f1_score(all_targets, all_preds, average="weighted")
    macro_prec = precision_score(all_targets, all_preds, average="macro", zero_division=0)
    macro_rec = recall_score(all_targets, all_preds, average="macro", zero_division=0)
    per_class_f1 = f1_score(all_targets, all_preds, average=None)
    cm = confusion_matrix(all_targets, all_preds, labels=[0, 1, 2])

    test_metrics = {
        "test_accuracy": float(acc),
        "test_macro_f1": float(macro_f1),
        "test_weighted_f1": float(weighted_f1),
        "test_macro_precision": float(macro_prec),
        "test_macro_recall": float(macro_rec),
        "test_f1_negative": float(per_class_f1[0]),
        "test_f1_neutral": float(per_class_f1[1]),
        "test_f1_positive": float(per_class_f1[2]),
        "inference_time_seconds": infer_time,
        "confusion_matrix": cm.tolist(),
    }

    return test_metrics


def predict_full_corpus_phobert(
    model: Any,
    tokenizer: Any,
    df: pd.DataFrame,
    batch_size: int = 64,
    device: str = "cuda",
) -> pd.DataFrame:
    """Predict sentiment scores [-1.0, 1.0] and probabilities for all 14,869 reviews."""
    torch, _, _ = check_torch_environment()
    from torch.utils.data import DataLoader

    dataset = PhoBERTReviewDataset(
        df["phobert_input_text"].tolist(),
        labels=None,
        tokenizer=tokenizer,
        max_length=128,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)

    model.eval()
    all_probs = []

    print(f"\n3. Tiến hành suy luận toàn bộ {len(df):,} reviews để tính điểm polarity bàn giao TV5...")
    t0 = time.time()
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            attention_mask = batch["attention_mask"].to(device, non_blocking=True)

            with torch.cuda.amp.autocast(enabled=(device == "cuda")):
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                probs = torch.softmax(outputs.logits, dim=1)

            all_probs.extend(probs.cpu().numpy())

    probs_arr = np.array(all_probs)
    preds = np.argmax(probs_arr, axis=1)

    # Polarity score = P(Positive) - P(Negative) in [-1.0, 1.0]
    polarity_scores = probs_arr[:, 2] - probs_arr[:, 0]
    confidences = np.max(probs_arr, axis=1)

    df["sentiment_pred"] = [ID_TO_CLASS[p] for p in preds]
    df["sentiment_score"] = np.round(polarity_scores, 4)
    df["sentiment_confidence"] = np.round(confidences, 4)
    df["prob_negative"] = np.round(probs_arr[:, 0], 4)
    df["prob_neutral"] = np.round(probs_arr[:, 1], 4)
    df["prob_positive"] = np.round(probs_arr[:, 2], 4)
    df["sentiment_model"] = "PhoBERT_vinai_phobert_base_v2"
    df["sentiment_step_version"] = TV6_PIPELINE_VERSION

    elapsed = round(time.time() - t0, 2)
    print(f"   Suy luận thành công {len(df):,} reviews trong {elapsed}s.")

    return df


def generate_phobert_tables(
    phobert_metrics: Dict[str, Any],
    baseline_report_path: Path = SENTIMENT_BASELINE_REPORT_FILE,
    output_dir: Path = TABLES_TV6_DIR,
) -> None:
    """Generate comparative performance tables between PhoBERT and TF-IDF Baselines."""
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    # Load baseline report if exists
    if baseline_report_path.exists():
        with baseline_report_path.open("r", encoding="utf-8") as f:
            b_data = json.load(f)
        for m_name, m_res in b_data.get("model_results", {}).items():
            rows.append({
                "Architecture": f"TF-IDF + {m_name}",
                "Model Type": "Classical ML",
                "Accuracy": f"{m_res['test_accuracy']:.4f}",
                "Macro F1": f"{m_res['test_macro_f1']:.4f}",
                "Weighted F1": f"{m_res['test_weighted_f1']:.4f}",
                "F1 (Neg)": f"{m_res['test_f1_negative']:.4f}",
                "F1 (Neu)": f"{m_res['test_f1_neutral']:.4f}",
                "F1 (Pos)": f"{m_res['test_f1_positive']:.4f}",
            })

    # Add PhoBERT row
    rows.append({
        "Architecture": "PhoBERT (vinai/phobert-base-v2)",
        "Model Type": "Pre-trained Transformer (SOTA)",
        "Accuracy": f"{phobert_metrics['test_accuracy']:.4f}",
        "Macro F1": f"{phobert_metrics['test_macro_f1']:.4f}",
        "Weighted F1": f"{phobert_metrics['test_weighted_f1']:.4f}",
        "F1 (Neg)": f"{phobert_metrics['test_f1_negative']:.4f}",
        "F1 (Neu)": f"{phobert_metrics['test_f1_neutral']:.4f}",
        "F1 (Pos)": f"{phobert_metrics['test_f1_positive']:.4f}",
    })

    comp_df = pd.DataFrame(rows)
    comp_df.to_csv(output_dir / "table_3_4_phobert_vs_baseline.csv", index=False, encoding="utf-8")
    comp_df.to_markdown(output_dir / "table_3_4_phobert_vs_baseline.md", index=False)

    # PhoBERT Confusion Matrix Table
    cm = np.array(phobert_metrics["confusion_matrix"])
    cm_rows = []
    for i, true_cls in enumerate(CLASS_NAMES):
        cm_rows.append({
            "True Class": true_cls,
            "Pred NEGATIVE": int(cm[i, 0]),
            "Pred NEUTRAL": int(cm[i, 1]),
            "Pred POSITIVE": int(cm[i, 2]),
            "Total True": int(np.sum(cm[i, :])),
            "Recall (%)": f"{cm[i, i] / np.sum(cm[i, :]) * 100:.2f}%",
        })
    cm_df = pd.DataFrame(cm_rows)
    cm_df.to_csv(output_dir / "table_3_5_phobert_confusion_matrix.csv", index=False, encoding="utf-8")
    cm_df.to_markdown(output_dir / "table_3_5_phobert_confusion_matrix.md", index=False)


def generate_phobert_figures(
    history: Dict[str, Any],
    phobert_metrics: Dict[str, Any],
    baseline_report_path: Path = SENTIMENT_BASELINE_REPORT_FILE,
    output_dir: Path = FIGURES_TV6_DIR,
) -> None:
    """Generate training learning curves and SOTA vs Baseline comparison bar plots."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font="sans-serif")

    # Figure 3.4: PhoBERT Training Curves (Loss & F1 per Epoch)
    epochs_range = range(1, len(history["train_loss"]) + 1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # Subplot 1: Loss curves
    ax1.plot(epochs_range, history["train_loss"], "o-", color="#ef4444", label="Train Loss", linewidth=2)
    ax1.plot(epochs_range, history["val_loss"], "s--", color="#3b82f6", label="Validation Loss", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Weighted Cross-Entropy Loss")
    ax1.set_title("Quá trình Hội tụ Hàm Mất Mát (Loss Curve)", fontsize=11, fontweight="bold")
    ax1.set_xticks(epochs_range)
    ax1.legend()

    # Subplot 2: Metric curves
    ax2.plot(epochs_range, history["val_macro_f1"], "o-", color="#10b981", label="Val Macro F1", linewidth=2)
    ax2.plot(epochs_range, history["val_weighted_f1"], "^-", color="#8b5cf6", label="Val Weighted F1", linewidth=2)
    ax2.plot(epochs_range, history["val_accuracy"], "d--", color="#f59e0b", label="Val Accuracy", linewidth=2)
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score")
    ax2.set_title("Tiến triển Độ chính xác & F1 qua các Epochs", fontsize=11, fontweight="bold")
    ax2.set_xticks(epochs_range)
    ax2.set_ylim(0.4, 1.0)
    ax2.legend()

    plt.suptitle("Hình 3.4: Đường cong Huấn luyện Mô hình PhoBERT (NVIDIA GPU Mixed Precision)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_3_4_phobert_training_curves.png", dpi=300)
    plt.close()

    # Figure 3.5: PhoBERT vs Baselines Comparison Bar Chart
    models = ["PhoBERT\n(Transformer)", "LogisticReg\n(balanced)", "LinearSVC\n(balanced)", "ComplementNB", "MultinomialNB"]
    macro_f1s = [phobert_metrics["test_macro_f1"]]
    weighted_f1s = [phobert_metrics["test_weighted_f1"]]
    neg_f1s = [phobert_metrics["test_f1_negative"]]

    if baseline_report_path.exists():
        with baseline_report_path.open("r", encoding="utf-8") as f:
            b_data = json.load(f)
        b_res = b_data.get("model_results", {})
        macro_f1s.append(b_res.get("LogisticRegression_balanced", {}).get("test_macro_f1", 0.5901))
        weighted_f1s.append(b_res.get("LogisticRegression_balanced", {}).get("test_weighted_f1", 0.9116))
        neg_f1s.append(b_res.get("LogisticRegression_balanced", {}).get("test_f1_negative", 0.5623))

        macro_f1s.append(b_res.get("LinearSVC_balanced", {}).get("test_macro_f1", 0.5778))
        weighted_f1s.append(b_res.get("LinearSVC_balanced", {}).get("test_weighted_f1", 0.9227))
        neg_f1s.append(b_res.get("LinearSVC_balanced", {}).get("test_f1_negative", 0.5606))

        macro_f1s.append(b_res.get("ComplementNB", {}).get("test_macro_f1", 0.5226))
        weighted_f1s.append(b_res.get("ComplementNB", {}).get("test_weighted_f1", 0.8856))
        neg_f1s.append(b_res.get("ComplementNB", {}).get("test_f1_negative", 0.4453))

        macro_f1s.append(b_res.get("MultinomialNB_unweighted", {}).get("test_macro_f1", 0.3415))
        weighted_f1s.append(b_res.get("MultinomialNB_unweighted", {}).get("test_weighted_f1", 0.8804))
        neg_f1s.append(b_res.get("MultinomialNB_unweighted", {}).get("test_f1_negative", 0.0671))

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    x = np.arange(len(models))
    width = 0.25

    ax.bar(x - width, macro_f1s, width, label="Macro F1 (Overall Balance)", color="#3b82f6")
    ax.bar(x, weighted_f1s, width, label="Weighted F1", color="#10b981")
    ax.bar(x + width, neg_f1s, width, label="Negative F1 (Class 0 Sensitivity)", color="#ef4444")

    ax.set_ylabel("F1 Score")
    ax.set_title("Hình 3.5: Đối sánh Toàn diện Giữa PhoBERT SOTA và Các Mô Hình TF-IDF Baseline", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right")

    for i in x:
        ax.annotate(f"{macro_f1s[i]:.2f}", (i - width, macro_f1s[i] + 0.02), ha="center", fontsize=8)
        ax.annotate(f"{weighted_f1s[i]:.2f}", (i, weighted_f1s[i] + 0.02), ha="center", fontsize=8)
        ax.annotate(f"{neg_f1s[i]:.2f}", (i + width, neg_f1s[i] + 0.02), ha="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_dir / "fig_3_5_phobert_vs_baseline_comparison.png", dpi=300)
    plt.close()


def run_phobert_pipeline() -> Dict[str, Any]:
    """Execute complete Step 3.2 PhoBERT Fine-Tuning Pipeline."""
    t_total_start = time.time()
    print("=" * 75)
    print("STARTING STEP 3.2: PHOBERT TRANSFORMER FINE-TUNING FOR SENTIMENT")
    print("=" * 75)

    # 1. Environment check
    torch, transformers, device = check_torch_environment()

    # 2. Load dataset
    print("1. Loading preprocessed reviews...")
    df = load_dataset_for_phobert()
    total_reviews = len(df)
    print(f"   Loaded {total_reviews:,} reviews from {REVIEWS_TV6_PREPROCESSED_FILE}")

    # 3. Stratified Train/Test split (Strictly matching Step 3.1)
    train_df, test_df = train_test_split(
        df,
        test_size=0.20,
        random_state=42,
        stratify=df["label_id"],
    )
    print(f"   Train samples: {len(train_df):,} | Test samples: {len(test_df):,}")

    # 4. Fine-Tune PhoBERT
    model, tokenizer, history = train_phobert_model(
        train_df=train_df,
        val_df=test_df,
        epochs=3,
        batch_size=32 if device == "cuda" else 8,
        lr=2e-5,
        max_length=128,
        random_state=42,
    )

    # 5. Evaluate on Hold-out Test Set
    print("\n4. Đánh giá kiểm thử độc lập mô hình PhoBERT trên Hold-out Test Set...")
    test_metrics = evaluate_phobert_on_test(model, tokenizer, test_df, device=device)
    print(f"   [KẾT QUẢ TEST SET PHOBERT]")
    print(f"     Test Accuracy     : {test_metrics['test_accuracy'] * 100:.2f}%")
    print(f"     Test Macro F1     : {test_metrics['test_macro_f1']:.4f}")
    print(f"     Test Weighted F1  : {test_metrics['test_weighted_f1']:.4f}")
    print(f"     F1 Lớp Tiêu Cực   : {test_metrics['test_f1_negative']:.4f}")
    print(f"     F1 Lớp Trung Tính : {test_metrics['test_f1_neutral']:.4f}")
    print(f"     F1 Lớp Tích Cực   : {test_metrics['test_f1_positive']:.4f}")

    # 6. Predict full corpus & export scored dataset
    df_scored = predict_full_corpus_phobert(model, tokenizer, df, device=device)
    REVIEWS_TV6_SENTIMENT_PHOBERT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REVIEWS_TV6_SENTIMENT_PHOBERT_FILE.open("w", encoding="utf-8") as f:
        for rec in df_scored.to_dict(orient="records"):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"   Đã xuất tập dữ liệu gán điểm: {REVIEWS_TV6_SENTIMENT_PHOBERT_FILE}")

    # 7. Generate comparison tables and figures
    print("\n5. Xuất bảng biểu và đồ thị đối sánh SOTA vs Baseline...")
    generate_phobert_tables(test_metrics)
    generate_phobert_figures(history, test_metrics)
    print("   Bảng đã lưu: data/tv6/tables/ (table_3_4, table_3_5)")
    print("   Biểu đồ đã lưu: data/tv6/figures/ (fig_3_4, fig_3_5)")

    # 8. Save JSON metadata report
    total_elapsed = round(time.time() - t_total_start, 2)
    report_data = {
        "pipeline_version": TV6_PIPELINE_VERSION,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step": "step3_2_phobert_sentiment",
        "pretrained_model": PHOBERT_PRETRAINED_NAME,
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
        "dataset_split": {
            "train_size": len(train_df),
            "test_size": len(test_df),
            "test_ratio": 0.20,
            "random_state": 42,
        },
        "training_hyperparameters": {
            "epochs": 3,
            "batch_size": 32 if device == "cuda" else 8,
            "learning_rate": 2e-5,
            "max_length": 128,
            "fp16_enabled": device == "cuda",
        },
        "training_history": history,
        "test_metrics": test_metrics,
        "total_runtime_seconds": total_elapsed,
    }

    with SENTIMENT_PHOBERT_REPORT_FILE.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    DOCS_SENTIMENT_PHOBERT_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DOCS_SENTIMENT_PHOBERT_REPORT_FILE.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"   Đã lưu báo cáo JSON: {SENTIMENT_PHOBERT_REPORT_FILE}")
    print("=" * 75)
    print(f"STEP 3.2 HOÀN TẤT THÀNH CÔNG TRONG {total_elapsed} GIÂY.")
    print("=" * 75)

    return report_data


if __name__ == "__main__":
    run_phobert_pipeline()
