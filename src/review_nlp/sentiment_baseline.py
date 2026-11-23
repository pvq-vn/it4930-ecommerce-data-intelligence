"""Step 3.1: Classical Machine Learning Sentiment Classification Baseline Engine.

Implements competitive, fast, and explainable sentiment classification using
TF-IDF n-grams (1-2) with multiple supervised machine learning architectures:
1. Logistic Regression (L2, class_weight='balanced')
2. Linear Support Vector Machine (LinearSVC, class_weight='balanced')
3. Complement Naive Bayes (ComplementNB - engineered for severe class imbalance)
4. Multinomial Naive Bayes (MultinomialNB - unweighted baseline)

Includes:
- Anti-leakage Stratified 80/20 train/test split.
- Stratified 5-Fold Cross Validation.
- Macro F1, Weighted F1, Per-Class F1, Confusion Matrix.
- Top Polar Feature Extraction (Positive vs Negative feature importance).
- Continuous polarity score [-1.0, +1.0] for downstream TV5 aggregation.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import ComplementNB, MultinomialNB
from sklearn.svm import LinearSVC

import sys
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.config import (
    DATA_TV6_DIR,
    DOCS_SENTIMENT_BASELINE_REPORT_FILE,
    FIGURES_TV6_DIR,
    REVIEWS_TV6_PREPROCESSED_FILE,
    REVIEWS_TV6_SENTIMENT_BASELINE_FILE,
    SENTIMENT_BASELINE_REPORT_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)

# Label constants
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


def load_preprocessed_reviews(filepath: Path = REVIEWS_TV6_PREPROCESSED_FILE) -> pd.DataFrame:
    """Load preprocessed usable reviews and construct pseudo-labels."""
    if not filepath.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}. Run Step 2 first.")

    records = []
    with filepath.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    df = pd.DataFrame(records)

    # Construct groundtruth pseudo-label from rating_raw
    df["label_id"] = df["rating_raw"].map(LABEL_MAP)
    df["sentiment_label_groundtruth"] = df["label_id"].map(ID_TO_CLASS)

    # Text column: prefer text_stopwords_removed, fallback to text_tokenized
    df["model_input_text"] = df["text_stopwords_removed"].replace("", np.nan)
    df["model_input_text"] = df["model_input_text"].fillna(df["text_tokenized"]).fillna(df["review_text_normalized"])

    return df


def split_data(
    df: pd.DataFrame, test_size: float = 0.20, random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified split ensuring zero data leakage between train and test."""
    train_df, test_df = train_test_split(
        df,
        test_size=test_size,
        random_state=random_state,
        stratify=df["label_id"],
    )
    return train_df.copy(), test_df.copy()


def train_tfidf_vectorizer(
    train_texts: pd.Series,
    max_features: int = 10000,
    ngram_range: Tuple[int, int] = (1, 2),
    min_df: int = 3,
    max_df: float = 0.85,
) -> TfidfVectorizer:
    """Fit TF-IDF Vectorizer strictly on train set to prevent feature leakage."""
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        min_df=min_df,
        max_df=max_df,
        sublinear_tf=True,
    )
    vectorizer.fit(train_texts)
    return vectorizer


def initialize_candidate_models(random_state: int = 42) -> Dict[str, Any]:
    """Instantiate diverse candidate machine learning classifiers."""
    return {
        "LogisticRegression_balanced": LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
            random_state=random_state,
        ),
        "LinearSVC_balanced": LinearSVC(
            C=0.5,
            max_iter=2500,
            class_weight="balanced",
            random_state=random_state,
        ),
        "ComplementNB": ComplementNB(
            alpha=0.5,
            norm=False,
        ),
        "MultinomialNB_unweighted": MultinomialNB(
            alpha=1.0,
        ),
    }


def evaluate_models(
    models: Dict[str, Any],
    X_train: Any,
    y_train: np.ndarray,
    X_test: Any,
    y_test: np.ndarray,
    cv_folds: int = 5,
    random_state: int = 42,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, np.ndarray]]:
    """Execute 5-fold cross-validation and hold-out test set evaluation."""
    skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    results: Dict[str, Dict[str, Any]] = {}
    test_preds: Dict[str, np.ndarray] = {}

    for name, model in models.items():
        t0 = time.time()

        # 5-Fold Stratified CV on Train Set
        cv_macro_f1 = cross_val_score(model, X_train, y_train, cv=skf, scoring="f1_macro", n_jobs=-1)
        cv_weighted_f1 = cross_val_score(model, X_train, y_train, cv=skf, scoring="f1_weighted", n_jobs=-1)

        # Fit on full train set
        model.fit(X_train, y_train)
        train_time = round(time.time() - t0, 3)

        # Predict on holdout test set
        y_pred = model.predict(X_test)
        test_preds[name] = y_pred

        # Compute test set metrics
        acc = accuracy_score(y_test, y_pred)
        macro_f1 = f1_score(y_test, y_pred, average="macro")
        weighted_f1 = f1_score(y_test, y_pred, average="weighted")
        macro_prec = precision_score(y_test, y_pred, average="macro", zero_division=0)
        macro_rec = recall_score(y_test, y_pred, average="macro", zero_division=0)

        # Per-class F1
        per_class_f1 = f1_score(y_test, y_pred, average=None)
        cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2])

        results[name] = {
            "cv_macro_f1_mean": float(np.mean(cv_macro_f1)),
            "cv_macro_f1_std": float(np.std(cv_macro_f1)),
            "cv_weighted_f1_mean": float(np.mean(cv_weighted_f1)),
            "test_accuracy": float(acc),
            "test_macro_f1": float(macro_f1),
            "test_weighted_f1": float(weighted_f1),
            "test_macro_precision": float(macro_prec),
            "test_macro_recall": float(macro_rec),
            "test_f1_negative": float(per_class_f1[0]),
            "test_f1_neutral": float(per_class_f1[1]),
            "test_f1_positive": float(per_class_f1[2]),
            "train_time_seconds": train_time,
            "confusion_matrix": cm.tolist(),
        }

    return results, test_preds


def extract_top_polar_features(
    model: Any, vectorizer: TfidfVectorizer, top_k: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    """Extract top positive and negative vocabulary features based on model weights."""
    feature_names = np.array(vectorizer.get_feature_names_out())

    if isinstance(model, LogisticRegression):
        # Multi-class LR coef shape: (3, n_features)
        # Class 0: Negative, Class 1: Neutral, Class 2: Positive
        neg_coefs = model.coef_[0]
        pos_coefs = model.coef_[2]

        top_neg_idx = np.argsort(neg_coefs)[::-1][:top_k]
        top_pos_idx = np.argsort(pos_coefs)[::-1][:top_k]

        top_neg = [{"feature": feature_names[i], "weight": round(float(neg_coefs[i]), 4)} for i in top_neg_idx]
        top_pos = [{"feature": feature_names[i], "weight": round(float(pos_coefs[i]), 4)} for i in top_pos_idx]

        return {"top_negative": top_neg, "top_positive": top_pos}

    elif isinstance(model, LinearSVC):
        neg_coefs = model.coef_[0]
        pos_coefs = model.coef_[2]

        top_neg_idx = np.argsort(neg_coefs)[::-1][:top_k]
        top_pos_idx = np.argsort(pos_coefs)[::-1][:top_k]

        top_neg = [{"feature": feature_names[i], "weight": round(float(neg_coefs[i]), 4)} for i in top_neg_idx]
        top_pos = [{"feature": feature_names[i], "weight": round(float(pos_coefs[i]), 4)} for i in top_pos_idx]

        return {"top_negative": top_neg, "top_positive": top_pos}

    return {"top_negative": [], "top_positive": []}


def predict_full_corpus_sentiment(
    best_model: Any,
    vectorizer: TfidfVectorizer,
    df: pd.DataFrame,
    model_name: str,
) -> pd.DataFrame:
    """Predict sentiment labels, continuous polarity score [-1.0, 1.0], and confidence."""
    X_full = vectorizer.transform(df["model_input_text"])

    preds = best_model.predict(X_full)
    df["sentiment_pred"] = [ID_TO_CLASS[p] for p in preds]

    # Probabilities or decision function
    if hasattr(best_model, "predict_proba"):
        probs = best_model.predict_proba(X_full)
        # Class 0 = Negative, Class 1 = Neutral, Class 2 = Positive
        # Continuous polarity score: P(Positive) - P(Negative) in [-1.0, 1.0]
        polarity_scores = probs[:, 2] - probs[:, 0]
        confidences = np.max(probs, axis=1)
        prob_neg = probs[:, 0]
        prob_neu = probs[:, 1]
        prob_pos = probs[:, 2]
    else:
        # Decision function for LinearSVC
        d_scores = best_model.decision_function(X_full)
        # Softmax over decision function for confidence approximation
        exp_d = np.exp(d_scores - np.max(d_scores, axis=1, keepdims=True))
        probs = exp_d / np.sum(exp_d, axis=1, keepdims=True)
        polarity_scores = probs[:, 2] - probs[:, 0]
        confidences = np.max(probs, axis=1)
        prob_neg = probs[:, 0]
        prob_neu = probs[:, 1]
        prob_pos = probs[:, 2]

    df["sentiment_score"] = np.round(polarity_scores, 4)
    df["sentiment_confidence"] = np.round(confidences, 4)
    df["prob_negative"] = np.round(prob_neg, 4)
    df["prob_neutral"] = np.round(prob_neu, 4)
    df["prob_positive"] = np.round(prob_pos, 4)
    df["sentiment_model"] = model_name
    df["sentiment_step_version"] = TV6_PIPELINE_VERSION

    return df


def generate_baseline_tables(
    results: Dict[str, Dict[str, Any]],
    top_polar: Dict[str, List[Dict[str, Any]]],
    output_dir: Path = TABLES_TV6_DIR,
) -> None:
    """Export formatted Markdown and CSV performance comparison tables."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Model comparison table
    comp_rows = []
    for name, m in results.items():
        comp_rows.append({
            "Model Name": name,
            "CV Macro F1": f"{m['cv_macro_f1_mean']:.4f} ± {m['cv_macro_f1_std']:.4f}",
            "Test Accuracy": f"{m['test_accuracy']:.4f}",
            "Test Macro F1": f"{m['test_macro_f1']:.4f}",
            "Test Weighted F1": f"{m['test_weighted_f1']:.4f}",
            "F1 (Negative)": f"{m['test_f1_negative']:.4f}",
            "F1 (Neutral)": f"{m['test_f1_neutral']:.4f}",
            "F1 (Positive)": f"{m['test_f1_positive']:.4f}",
            "Train Time (s)": f"{m['train_time_seconds']:.2f}",
        })

    comp_df = pd.DataFrame(comp_rows)
    comp_df.to_csv(output_dir / "table_3_1_model_comparison.csv", index=False, encoding="utf-8")
    comp_df.to_markdown(output_dir / "table_3_1_model_comparison.md", index=False)

    # 2. Confusion Matrix Table for Best Model
    best_name = max(results.keys(), key=lambda k: results[k]["test_macro_f1"])
    cm = np.array(results[best_name]["confusion_matrix"])

    cm_rows = []
    for i, true_cls in enumerate(CLASS_NAMES):
        cm_rows.append({
            "True Class": true_cls,
            "Pred NEGATIVE": int(cm[i, 0]),
            "Pred NEUTRAL": int(cm[i, 1]),
            "Pred POSITIVE": int(cm[i, 2]),
            "Total True": int(np.sum(cm[i, :])),
        })
    cm_df = pd.DataFrame(cm_rows)
    cm_df.to_csv(output_dir / "table_3_2_confusion_matrices.csv", index=False, encoding="utf-8")
    cm_df.to_markdown(output_dir / "table_3_2_confusion_matrices.md", index=False)

    # 3. Top polar features table
    top_pos = top_polar.get("top_positive", [])
    top_neg = top_polar.get("top_negative", [])
    n_items = max(len(top_pos), len(top_neg))

    polar_rows = []
    for i in range(n_items):
        pos_item = top_pos[i] if i < len(top_pos) else {"feature": "", "weight": ""}
        neg_item = top_neg[i] if i < len(top_neg) else {"feature": "", "weight": ""}
        polar_rows.append({
            "Rank": i + 1,
            "Positive Feature": pos_item["feature"],
            "Pos Weight": pos_item["weight"],
            "Negative Feature": neg_item["feature"],
            "Neg Weight": neg_item["weight"],
        })
    polar_df = pd.DataFrame(polar_rows)
    polar_df.to_csv(output_dir / "table_3_3_top_polar_features.csv", index=False, encoding="utf-8")
    polar_df.to_markdown(output_dir / "table_3_3_top_polar_features.md", index=False)


def generate_baseline_figures(
    results: Dict[str, Dict[str, Any]],
    top_polar: Dict[str, List[Dict[str, Any]]],
    output_dir: Path = FIGURES_TV6_DIR,
) -> None:
    """Generate high-resolution (300 DPI) publication-ready comparison figures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font="sans-serif")

    # Figure 3.1: Model Comparison Metrics (Macro F1, Weighted F1, Negative F1)
    models = list(results.keys())
    macro_f1s = [results[m]["test_macro_f1"] for m in models]
    weighted_f1s = [results[m]["test_weighted_f1"] for m in models]
    neg_f1s = [results[m]["test_f1_negative"] for m in models]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    x = np.arange(len(models))
    width = 0.25

    ax.bar(x - width, macro_f1s, width, label="Macro F1", color="#3b82f6")
    ax.bar(x, weighted_f1s, width, label="Weighted F1", color="#10b981")
    ax.bar(x + width, neg_f1s, width, label="Negative F1 (Class 0)", color="#ef4444")

    ax.set_ylabel("F1 Score")
    ax.set_title("Hình 3.1: So sánh hiệu năng các mô hình Sentiment Baseline (TF-IDF)", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace("_", "\n") for m in models], fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right")

    for i in x:
        ax.annotate(f"{macro_f1s[i]:.2f}", (i - width, macro_f1s[i] + 0.02), ha="center", fontsize=8)
        ax.annotate(f"{weighted_f1s[i]:.2f}", (i, weighted_f1s[i] + 0.02), ha="center", fontsize=8)
        ax.annotate(f"{neg_f1s[i]:.2f}", (i + width, neg_f1s[i] + 0.02), ha="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_dir / "fig_3_1_model_comparison_metrics.png", dpi=300)
    plt.close()

    # Figure 3.2: Confusion Matrices for All 4 Models
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), dpi=300)
    axes = axes.flatten()

    for idx, (m_name, m_data) in enumerate(results.items()):
        cm = np.array(m_data["confusion_matrix"])
        # Normalize by true class
        cm_norm = cm.astype("float") / cm.sum(axis=1)[:, np.newaxis]
        ax = axes[idx]
        sns.heatmap(
            cm_norm,
            annot=True,
            fmt=".2%",
            cmap="Blues",
            ax=ax,
            xticklabels=CLASS_NAMES,
            yticklabels=CLASS_NAMES,
            cbar=False,
        )
        ax.set_title(f"{m_name}\n(Macro F1: {m_data['test_macro_f1']:.4f})", fontsize=10, fontweight="bold")
        ax.set_xlabel("Predicted Label")
        ax.set_ylabel("True Label")

    plt.suptitle("Hình 3.2: Ma trận nhầm lẫn chuẩn hóa (Confusion Matrices) các mô hình Baseline", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_3_2_confusion_matrices.png", dpi=300)
    plt.close()

    # Figure 3.3: Top Polar Features Diverging Bar Chart
    top_pos = top_polar.get("top_positive", [])[:15]
    top_neg = top_polar.get("top_negative", [])[:15]

    if top_pos and top_neg:
        fig, (ax_pos, ax_neg) = plt.subplots(1, 2, figsize=(12, 6), dpi=300)

        pos_words = [p["feature"] for p in top_pos][::-1]
        pos_weights = [p["weight"] for p in top_pos][::-1]

        neg_words = [n["feature"] for n in top_neg][::-1]
        neg_weights = [n["weight"] for n in top_neg][::-1]

        ax_pos.barh(pos_words, pos_weights, color="#10b981")
        ax_pos.set_title("Top 15 Từ tố mang Cực tính TÍCH CỰC", fontsize=11, fontweight="bold")
        ax_pos.set_xlabel("Trọng số phân loại (Coefficients)")

        ax_neg.barh(neg_words, neg_weights, color="#ef4444")
        ax_neg.set_title("Top 15 Từ tố mang Cực tính TIÊU CỰC", fontsize=11, fontweight="bold")
        ax_neg.set_xlabel("Trọng số phân loại (Coefficients)")

        plt.suptitle("Hình 3.3: Các đặc trưng từ vựng phân cực mạnh nhất (Logistic Regression Weights)", fontsize=12, fontweight="bold")
        plt.tight_layout()
        plt.savefig(output_dir / "fig_3_3_top_polar_words.png", dpi=300)
        plt.close()


def run_sentiment_baseline_pipeline() -> Dict[str, Any]:
    """Execute complete Step 3.1 Sentiment Baseline Pipeline."""
    t0 = time.time()
    print("=" * 65)
    print("STARTING STEP 3.1: CLASSICAL ML SENTIMENT BASELINE")
    print("=" * 65)

    # 1. Load data
    print("1. Loading preprocessed reviews...")
    df = load_preprocessed_reviews()
    total_reviews = len(df)
    print(f"   Loaded {total_reviews:,} reviews from {REVIEWS_TV6_PREPROCESSED_FILE}")

    # Class distribution in total corpus
    dist = df["sentiment_label_groundtruth"].value_counts().to_dict()
    print("   Corpus class distribution:")
    for c, cnt in dist.items():
        print(f"     - {c:10s}: {cnt:5d} ({cnt / total_reviews * 100:.2f}%)")

    # 2. Stratified train/test split
    print("\n2. Executing Stratified 80/20 train/test split (random_state=42)...")
    train_df, test_df = split_data(df, test_size=0.20, random_state=42)
    print(f"   Train samples: {len(train_df):,} | Test samples: {len(test_df):,}")

    # 3. Fit TF-IDF Vectorizer strictly on train
    print("\n3. Fitting TF-IDF Vectorizer (ngram=(1, 2), max_features=10,000)...")
    vectorizer = train_tfidf_vectorizer(train_df["model_input_text"])
    X_train = vectorizer.transform(train_df["model_input_text"])
    X_test = vectorizer.transform(test_df["model_input_text"])
    y_train = train_df["label_id"].to_numpy()
    y_test = test_df["label_id"].to_numpy()
    print(f"   Vocabulary size: {len(vectorizer.get_feature_names_out()):,} n-grams")

    # 4. Initialize & Benchmark candidate models
    print("\n4. Benchmarking candidate models with 5-Fold Stratified CV...")
    candidate_models = initialize_candidate_models(random_state=42)
    results, test_preds = evaluate_models(candidate_models, X_train, y_train, X_test, y_test)

    for m_name, m_res in results.items():
        print(f"   [{m_name}]")
        print(f"     CV Macro F1 : {m_res['cv_macro_f1_mean']:.4f} ± {m_res['cv_macro_f1_std']:.4f}")
        print(f"     Test Macro F1: {m_res['test_macro_f1']:.4f} | Weighted F1: {m_res['test_weighted_f1']:.4f} | Acc: {m_res['test_accuracy']:.4f}")
        print(f"     Per-class F1 : Neg={m_res['test_f1_negative']:.4f} | Neu={m_res['test_f1_neutral']:.4f} | Pos={m_res['test_f1_positive']:.4f}")
        print(f"     Train time   : {m_res['train_time_seconds']:.2f}s")

    # 5. Select Best Model
    best_name = max(results.keys(), key=lambda k: results[k]["test_macro_f1"])
    best_model = candidate_models[best_name]
    print(f"\n5. Best Model Selected: {best_name} (Test Macro F1: {results[best_name]['test_macro_f1']:.4f})")

    # 6. Extract top polar features
    print("6. Extracting top polar features from best model...")
    top_polar = extract_top_polar_features(best_model, vectorizer, top_k=20)
    print(f"   Top Positive: {[p['feature'] for p in top_polar.get('top_positive', [])[:5]]}")
    print(f"   Top Negative: {[n['feature'] for n in top_polar.get('top_negative', [])[:5]]}")

    # 7. Predict full corpus & append sentiment scores
    print("\n7. Predicting full corpus sentiment scores for downstream TV5 handoff...")
    df_scored = predict_full_corpus_sentiment(best_model, vectorizer, df, best_name)

    # Export scored jsonl
    REVIEWS_TV6_SENTIMENT_BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REVIEWS_TV6_SENTIMENT_BASELINE_FILE.open("w", encoding="utf-8") as f:
        for rec in df_scored.to_dict(orient="records"):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"   Saved scored dataset: {REVIEWS_TV6_SENTIMENT_BASELINE_FILE} ({len(df_scored):,} records)")

    # 8. Generate tables & figures
    print("\n8. Generating tables and high-resolution figures...")
    generate_baseline_tables(results, top_polar)
    generate_baseline_figures(results, top_polar)
    print("   Tables saved in data/tv6/tables/ (table_3_1, table_3_2, table_3_3)")
    print("   Figures saved in data/tv6/figures/ (fig_3_1, fig_3_2, fig_3_3)")

    # 9. Save JSON metadata report
    total_elapsed = round(time.time() - t0, 2)
    report_data = {
        "pipeline_version": TV6_PIPELINE_VERSION,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step": "step3_1_sentiment_baseline",
        "inputs": {
            "preprocessed_file": str(REVIEWS_TV6_PREPROCESSED_FILE),
            "record_count": total_reviews,
        },
        "dataset_split": {
            "train_size": len(train_df),
            "test_size": len(test_df),
            "test_ratio": 0.20,
            "random_state": 42,
        },
        "class_distribution_total": dist,
        "best_model_selected": best_name,
        "model_results": results,
        "top_polar_features": top_polar,
        "total_runtime_seconds": total_elapsed,
    }

    with SENTIMENT_BASELINE_REPORT_FILE.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    DOCS_SENTIMENT_BASELINE_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DOCS_SENTIMENT_BASELINE_REPORT_FILE.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"   Saved report: {SENTIMENT_BASELINE_REPORT_FILE}")
    print("=" * 65)
    print(f"STEP 3.1 COMPLETED IN {total_elapsed}s.")
    print("=" * 65)

    return report_data


if __name__ == "__main__":
    run_sentiment_baseline_pipeline()
