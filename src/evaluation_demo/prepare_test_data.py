from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
TV5_MODELS_DIR = REPO_ROOT / "src" / "price_prediction" / "models"
DATA_COMMIT = "24cd858"
AUDIT_ID = "_tv8_listing_record_id"


@dataclass(frozen=True)
class TV5Split:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    test_metadata: pd.DataFrame
    train_metadata: pd.DataFrame


def use_tv5_modules():
    # TV5's code and saved models refer to modules by short names such as `features`.
    if str(TV5_MODELS_DIR) not in sys.path:
        sys.path.insert(0, str(TV5_MODELS_DIR))


def read_snapshot(filename):
    git_path = f"{DATA_COMMIT}:data/processed/{filename}"
    return subprocess.check_output(["git", "show", git_path], cwd=REPO_ROOT)


def prepare_tv5_splits():
    cleaned_bytes = read_snapshot("products_cleaned.jsonl")
    processed_bytes = read_snapshot("products_processed.jsonl")
    cleaned = [json.loads(line) for line in cleaned_bytes.splitlines() if line.strip()]
    processed = [json.loads(line) for line in processed_bytes.splitlines() if line.strip()]

    processed_by_id = {
        row["listing_record_id"]: row for row in processed if row["source_parent_id"]
    }
    matched = sum(row["listing_record_id"] in processed_by_id for row in cleaned)
    print(f"Tim thay ban ghi tuong ung: {matched}/{len(cleaned)}")
    if matched != len(cleaned):
        raise SystemExit("Co ban ghi khong tim duoc ma nhom. Dung truoc khi chia tap.")

    use_tv5_modules()
    try:
        from features import load_and_split_data
        from utils import prepare_raw_data, split_by_group
    except ModuleNotFoundError as exc:
        if exc.name not in {"numpy", "pandas", "sklearn"}:
            raise
        raise SystemExit(
            f"Python dang chay: {sys.executable}\n"
            f"Moi truong nay thieu thu vien {exc.name}. "
            "Hay chon Python cua moi truong TV8, hoac cai pandas va scikit-learn "
            "vao moi truong Python ban muon dung."
        ) from None

    # TV5 drops listing_record_id. Carry a separate audit key through its filters
    # and remove that key before preparing any model inputs.
    cleaned_with_audit_id = "\n".join(
        json.dumps({**row, AUDIT_ID: row["listing_record_id"]}) for row in cleaned
    ).encode("utf-8")
    laptops, smartphones = load_and_split_data(
        BytesIO(cleaned_with_audit_id), BytesIO(processed_bytes)
    )
    product_names = {row["listing_record_id"]: row["product_name"] for row in cleaned}
    extra_fields = {
        field: {listing_id: row.get(field) for listing_id, row in processed_by_id.items()}
        for field in ("availability_status", "charger_watt")
    }

    splits = {}
    for category, rows, expected_train, expected_test in (
        ("laptop", laptops, 3227, 819),
        ("smartphone", smartphones, 3300, 797),
    ):
        listing_ids = rows.pop(AUDIT_ID)
        X, y, groups = prepare_raw_data(rows)
        X_train, X_test, y_train, y_test, train_groups = split_by_group(X, y, groups)
        test_groups = groups.loc[X_test.index]
        print(f"{category.title()}: train={len(X_train)}, test={len(X_test)}")

        if (len(X_train), len(X_test)) != (expected_train, expected_test):
            raise SystemExit(f"So dong {category} khac voi phep chia cua TV5.")
        if not set(train_groups).isdisjoint(test_groups):
            raise SystemExit(f"Tap train va test cua {category} co nhom trung nhau.")
        metadata = listing_ids.rename("listing_record_id").to_frame()
        metadata["product_name"] = listing_ids.map(product_names)
        for field, mapping in extra_fields.items():
            metadata[field] = listing_ids.map(mapping)
        metadata["source_parent_id"] = groups
        splits[category] = TV5Split(
            X_train, y_train, X_test, y_test,
            metadata.loc[X_test.index], metadata.loc[X_train.index],
        )

    return splits


def main():
    prepare_tv5_splits()
    print("BUOC 1 OK")


if __name__ == "__main__":
    main()
