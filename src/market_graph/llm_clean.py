"""Step 1: Export raw product names/specs to CSV and normalize via DeepSeek API.

Filters out listings with missing/zero prices, exports raw CSV, supports
stratified 100-row pilot sampling, and extracts clean `brand`, `model_clean`,
`cpu_model`, and core hardware specs using DeepSeek (`deepseek-chat`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "TV2_Data_Handoff" / "processed" / "products_processed.jsonl"
DEFAULT_WORK_DIR = PROJECT_ROOT / "data" / "market_graph"
DEFAULT_CSV = DEFAULT_WORK_DIR / "raw_products_export.csv"
DEFAULT_SAMPLE_CSV = DEFAULT_WORK_DIR / "sample_100_raw.csv"
DEFAULT_SAMPLE_OUT = DEFAULT_WORK_DIR / "sample_100_cleaned.jsonl"
DEFAULT_OUTPUT = DEFAULT_WORK_DIR / "products_llm_cleaned.jsonl"
DEFAULT_CACHE = DEFAULT_WORK_DIR / "llm_spec_cache.jsonl"

WHITESPACE_RE = re.compile(r"\s+")
PREFIX_RE = re.compile(r"^(?:điện thoại|laptop|máy tính xách tay)\s+", re.IGNORECASE)

SELLER_MAP: dict[str, str] = {
    "tgdd": "TGDĐ",
    "Thế Giới Di Động": "TGDĐ",
    "fptshop": "FPT",
    "FPT Shop": "FPT",
    "cellphones": "CellphoneS",
    "CellphoneS": "CellphoneS",
    "viettelstore": "Viettel",
    "Viettel Store": "Viettel",
    "hoanghamobile": "Hoàng Hà",
    "Hoàng Hà Mobile": "Hoàng Hà",
}

BRAND_PRE_MAP: dict[str, str | None] = {
    "iPhone (Apple)": "Apple",
    "Nothing Phone": "Nothing",
    "Inoi": "INOI",
    "intel": "Intel",
    "Google Pixel": "Google",
    "Hãng khác": None,
}

BRAND_CANON_MAP: dict[str, str] = {
    "apple": "Apple",
    "asus": "ASUS",
    "samsung": "Samsung",
    "xiaomi": "Xiaomi",
    "lenovo": "Lenovo",
    "hp": "HP",
    "dell": "Dell",
    "oppo": "OPPO",
    "msi": "MSI",
    "acer": "Acer",
    "vivo": "Vivo",
    "realme": "Realme",
    "honor": "Honor",
    "nubia": "Nubia",
    "tecno": "Tecno",
    "nokia": "Nokia",
    "huawei": "Huawei",
    "masstel": "Masstel",
    "vsmart": "Vsmart",
    "gigabyte": "Gigabyte",
    "microsoft": "Microsoft",
    "infinix": "Infinix",
    "lg": "LG",
    "motorola": "Motorola",
    "oneplus": "OnePlus",
    "tcl": "TCL",
    "itel": "Itel",
    "mobell": "Mobell",
    "zte": "ZTE",
    "meizu": "Meizu",
    "nothing": "Nothing",
    "sony": "Sony",
    "google": "Google",
    "inoi": "INOI",
    "intel": "Intel",
    "sharp": "Sharp",
    "bphone": "Bphone",
    "htc": "HTC",
    "vaio": "VAIO",
    "fujitsu": "Fujitsu",
    "philips": "Philips",
    "colorful": "Colorful",
    "thunderobot": "Thunderobot",
    "avita": "Avita",
    "benco": "Benco",
    "energizer": "Energizer",
    "oscal": "OSCAL",
    "doogee": "Doogee",
    "blackview": "Blackview",
    "leitz": "Leitz",
    "xor": "XOR",
    "singpc": "SingPC",
    "viettel": "Viettel",
    "xphone": "Xphone",
}


def normalize_seller(row: dict[str, Any]) -> str:
    for field in ("seller_raw", "source"):
        value = row.get(field)
        if value in SELLER_MAP:
            return SELLER_MAP[value]
    return str(row.get("seller_raw") or row.get("source") or "Unknown")


def pre_clean_brand(brand_raw: str | None) -> str | None:
    if not brand_raw:
        return None
    brand_str = brand_raw.strip()
    if brand_str in BRAND_PRE_MAP:
        return BRAND_PRE_MAP[brand_str]
    return brand_str


def canonicalize_brand(brand: str | None) -> str | None:
    if not brand:
        return None
    cleaned = WHITESPACE_RE.sub(" ", brand).strip()
    return BRAND_CANON_MAP.get(cleaned.lower(), cleaned)


def post_clean_product_name(name: str) -> str:
    cleaned = PREFIX_RE.sub("", name.strip())
    return WHITESPACE_RE.sub(" ", cleaned).strip()


SYSTEM_PROMPT = """Bạn là chuyên gia chuẩn hóa dữ liệu phần cứng điện thoại & laptop tại Việt Nam.
Với mỗi sản phẩm trong danh sách JSON đầu vào, hãy trích xuất chính xác các trường sau và trả về một JSON object có key duy nhất là `"items"` (mảng các object):

1. `idx`: Số nguyên khớp với `idx` đầu vào.
2. `brand`: Tên hãng chuẩn hóa (VD: "Apple", "Samsung", "ASUS", "Dell", "HP", "Lenovo", "Acer", "MSI", "Xiaomi", "OPPO", "Vivo", "Realme", "Honor", "LG", "Gigabyte", "Microsoft", "Tecno", "Nokia", "Nubia"...).
3. `model_clean`: Tên dòng máy sạch, chuẩn hóa để gom cụm cùng model giữa các nhà bán lẻ:
   - Bỏ tiền tố ("Điện thoại", "Laptop", "Máy tính xách tay", "Gaming").
   - Bỏ tên hãng ở đầu nếu bị lặp, nhưng giữ tên dòng đặc trưng (VD: "MacBook Air M3 13 inch", "Inspiron 15 3520", "Vivobook 15 OLED", "iPhone 15 Pro Max", "Galaxy S24 Ultra", "Nitro V ANV15-51").
   - Bỏ mã SKU/part-number rác (VD: "9Q970PA", "70157552", "NXJRRSV002", "82B500GUVN", "VN/A", "L1114W"), bỏ màu sắc, bỏ dung lượng RAM/SSD/ROM ("8GB/256GB", "16GB", "512GB", "1TB"), bỏ từ khóa quảng cáo ("Chính hãng", "Trả góp").
4. `cpu_model`: Tên model CPU/SoC ngắn gọn, chuẩn hóa (VD: "Core i5-13420H", "Core 5 120U", "Ryzen 5 7535HS", "Apple M3", "Apple A17 Pro", "Snapdragon 8 Gen 3", "Dimensity 8300 Ultra", "Exynos 1480", "Unknown" nếu hoàn toàn không có thông tin).
5. `ram_gb`: Số nguyên GB RAM (VD: 8, 16, 32, hoặc null nếu không rõ).
6. `storage_gb`: Số nguyên GB bộ nhớ trong/SSD (VD: 128, 256, 512, 1024, hoặc null nếu không rõ).
7. `gpu_model`: Tên GPU ngắn gọn cho laptop (VD: "RTX 4050", "GTX 1650 Ti", "Intel Iris Xe", "Apple 10-core GPU", hoặc null cho smartphone/không rõ).
8. `screen_size_inch`: Số thực kích thước màn hình (VD: 15.6, 14.0, 6.7, hoặc null).
9. `category_clean`: Chỉ chọn "laptop", "smartphone", hoặc "other" (nếu là PC/All-in-One/iPad/Tablet/phụ kiện).

Chỉ trả về JSON hợp lệ theo format: {"items": [...]}."""


class CleanedSpecItem(BaseModel):
    idx: int
    brand: str
    model_clean: str
    cpu_model: str
    ram_gb: int | None = None
    storage_gb: int | None = None
    gpu_model: str | None = None
    screen_size_inch: float | None = None
    category_clean: Literal["laptop", "smartphone", "other"]


class CleanedSpecBatch(BaseModel):
    items: list[CleanedSpecItem]


def build_raw_specs(row: dict[str, Any]) -> str:
    """Combine raw hardware fields into a compact spec string for CSV/LLM."""
    parts: list[str] = []
    if row.get("cpu_norm"):
        parts.append(f"CPU: {row['cpu_norm']}")
    if row.get("gpu_norm"):
        parts.append(f"GPU: {row['gpu_norm']}")
    if row.get("installed_ram_gb") is not None:
        parts.append(f"RAM: {row['installed_ram_gb']}GB")
    if row.get("storage_gb") is not None:
        parts.append(f"Storage: {row['storage_gb']}GB")
    if row.get("screen_size_inch") is not None:
        parts.append(f"Screen: {row['screen_size_inch']}in")
    if row.get("operating_system_norm"):
        parts.append(f"OS: {row['operating_system_norm']}")
    return " | ".join(parts)


def _safe_float(val: Any) -> float | None:
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
    except (ValueError, TypeError):
        return None
    return f if pd.notna(f) else None


def load_valid_price_rows(input_path: Path) -> tuple[list[dict[str, Any]], int]:
    """Load products_processed.jsonl, skipping rows with missing or non-positive price."""
    valid_rows: list[dict[str, Any]] = []
    skipped = 0
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            price_val = _safe_float(row.get("price_vnd"))
            if row.get("is_price_missing") or price_val is None or price_val <= 0:
                skipped += 1
                continue
            valid_rows.append(
                {
                    "listing_record_id": row["listing_record_id"],
                    "source": row["source"],
                    "seller_name": normalize_seller(row),
                    "category": str(row.get("category") or "").strip().lower(),
                    "brand_norm": pre_clean_brand(row.get("brand_norm")),
                    "price_vnd": price_val,
                    "rating_norm": row.get("rating_norm"),
                    "review_count_normalized": row.get("review_count_normalized") or 0.0,
                    "product_name": str(row.get("product_name") or "").strip(),
                    "raw_specs": build_raw_specs(row),
                    "installed_ram_gb": row.get("installed_ram_gb"),
                    "storage_gb": row.get("storage_gb"),
                    "screen_size_inch": row.get("screen_size_inch"),
                }
            )
    return valid_rows, skipped


def export_raw_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    """Export raw product names and specs to CSV."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    cols = [
        "listing_record_id",
        "source",
        "seller_name",
        "category",
        "price_vnd",
        "rating_norm",
        "review_count_normalized",
        "brand_norm",
        "product_name",
        "raw_specs",
    ]
    df[cols].to_csv(csv_path, index=False, encoding="utf-8-sig")


def stratified_sample(rows: list[dict[str, Any]], sample_size: int, seed: int = 42) -> list[dict[str, Any]]:
    """Sample rows proportionally across (seller_name, category) groups."""
    if sample_size >= len(rows):
        return list(rows)
    df = pd.DataFrame(rows)
    # Ensure every (seller_name, category) stratum gets at least 1 row
    sampled_parts: list[pd.DataFrame] = []
    groups = list(df.groupby(["seller_name", "category"]))
    for _, grp in groups:
        n_take = max(1, round(len(grp) / len(df) * sample_size))
        n_take = min(n_take, len(grp))
        sampled_parts.append(grp.sample(n=n_take, random_state=seed))
    sampled_df = pd.concat(sampled_parts, ignore_index=True)
    if len(sampled_df) > sample_size:
        sampled_df = sampled_df.sample(n=sample_size, random_state=seed)
    elif len(sampled_df) < sample_size:
        used_ids = set(sampled_df["listing_record_id"])
        rest = df[~df["listing_record_id"].isin(used_ids)]
        extra = rest.sample(n=min(sample_size - len(sampled_df), len(rest)), random_state=seed)
        sampled_df = pd.concat([sampled_df, extra], ignore_index=True)
    sampled_df = sampled_df.astype(object).where(pd.notna(sampled_df), None)
    return sampled_df.to_dict(orient="records")


def make_cache_key(product_name: str, raw_specs: str, brand_pre: str | None, category: str) -> str:
    payload = f"{product_name}\x1f{raw_specs}\x1f{brand_pre or ''}\x1f{category}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    if not cache_path.exists():
        return cache
    with cache_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    cache[entry["key"]] = entry["result"]
                except (json.JSONDecodeError, KeyError):
                    continue
    return cache


def append_cache(cache_path: Path, entries: list[dict[str, Any]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_dotenv_key(var_name: str) -> str | None:
    val = os.environ.get(var_name)
    if val:
        return val
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == var_name:
                return v.strip().strip('"').strip("'")
    return None


def call_deepseek_batch(
    client: Any,
    model: str,
    batch: list[dict[str, Any]],
    max_retries: int = 4,
) -> dict[int, CleanedSpecItem]:
    prompt_items = [
        {
            "idx": i,
            "product_name": item["product_name"],
            "raw_specs": item["raw_specs"],
            "brand_hint": item["brand_norm"],
            "category_hint": item["category"],
        }
        for i, item in enumerate(batch)
    ]
    user_msg = (
        f"Chuẩn hóa {len(prompt_items)} sản phẩm sau:\n"
        f"{json.dumps(prompt_items, ensure_ascii=False)}"
    )

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            parsed = CleanedSpecBatch.model_validate_json(content)
            by_idx = {item.idx: item for item in parsed.items}
            if len(by_idx) != len(batch):
                missing = set(range(len(batch))) - set(by_idx.keys())
                raise ValueError(f"LLM response missing indices: {sorted(missing)}")
            return by_idx
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait_sec = 2.0 * (2**attempt)
            print(
                f"  [WARN] DeepSeek batch attempt {attempt + 1}/{max_retries} failed ({exc}). "
                f"Retrying in {wait_sec:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(wait_sec)

    raise RuntimeError(f"DeepSeek batch failed after {max_retries} attempts: {last_err}") from last_err


def normalize_cpu_text(cpu: str) -> str:
    """Light post-normalization on extracted cpu_model."""
    if not cpu:
        return "Unknown"
    cleaned = WHITESPACE_RE.sub(" ", cpu).strip()
    cleaned = re.sub(r"[™®]", "", cleaned)
    return cleaned


def run_step1(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
    csv_path: Path = DEFAULT_CSV,
    cache_path: Path = DEFAULT_CACHE,
    export_csv: bool = True,
    sample_size: int | None = None,
    batch_size: int = 25,
    model: str = "deepseek-chat",
    dry_run: bool = False,
) -> Path:
    rows, skipped_price = load_valid_price_rows(input_path)
    print(f"[Step 1] Loaded {len(rows)} valid-price listings (skipped {skipped_price} missing/zero-price rows).")

    if export_csv:
        export_raw_csv(rows, csv_path)
        print(f"[Step 1] Exported raw CSV -> {csv_path}")

    if sample_size is not None:
        rows = stratified_sample(rows, sample_size=sample_size)
        sample_csv = csv_path.parent / f"sample_{sample_size}_raw.csv"
        export_raw_csv(rows, sample_csv)
        if output_path == DEFAULT_OUTPUT:
            output_path = csv_path.parent / f"sample_{sample_size}_cleaned.jsonl"
        print(f"[Step 1] Stratified sample ({len(rows)} rows) -> {sample_csv}")

    # Deduplicate by (product_name, raw_specs, brand_norm, category)
    unique_items: dict[str, dict[str, Any]] = {}
    row_keys: list[str] = []
    for row in rows:
        key = make_cache_key(row["product_name"], row["raw_specs"], row["brand_norm"], row["category"])
        row_keys.append(key)
        if key not in unique_items:
            unique_items[key] = row

    cache = load_cache(cache_path)
    pending_keys = [k for k in unique_items if k not in cache]
    print(
        f"[Step 1] Unique items: {len(unique_items)} | Cached: {len(unique_items) - len(pending_keys)} | "
        f"Pending LLM: {len(pending_keys)}"
    )

    if dry_run:
        print("[Step 1] Dry-run mode: skipping DeepSeek API calls.")
        return output_path

    if pending_keys:
        api_key = _load_dotenv_key("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY not found in environment or .env file. "
                "Please export DEEPSEEK_API_KEY before running Step 1 LLM cleaning."
            )
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        total_batches = (len(pending_keys) + batch_size - 1) // batch_size
        for b_idx in range(total_batches):
            batch_keys = pending_keys[b_idx * batch_size : (b_idx + 1) * batch_size]
            batch_rows = [unique_items[k] for k in batch_keys]
            print(f"[Step 1] Calling DeepSeek ({model}) batch {b_idx + 1}/{total_batches} ({len(batch_rows)} items)...")
            result_map = call_deepseek_batch(client, model, batch_rows)
            new_entries: list[dict[str, Any]] = []
            for idx, key in enumerate(batch_keys):
                item = result_map[idx]
                res_dict = {
                    "brand": canonicalize_brand(item.brand) or item.brand,
                    "model_clean": post_clean_product_name(item.model_clean),
                    "cpu_model": normalize_cpu_text(item.cpu_model),
                    "ram_gb": item.ram_gb,
                    "storage_gb": item.storage_gb,
                    "gpu_model": item.gpu_model,
                    "screen_size_inch": item.screen_size_inch,
                    "category_clean": item.category_clean,
                }
                cache[key] = res_dict
                new_entries.append({"key": key, "result": res_dict})
            append_cache(cache_path, new_entries)

    # Write cleaned output (excluding 'other' accessories/tablets)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kept_rows: list[dict[str, Any]] = []
    dropped_other = 0
    cat_counts: Counter[str] = Counter()
    with output_path.open("w", encoding="utf-8") as f:
        for row, key in zip(rows, row_keys):
            res = cache.get(key)
            if not res:
                continue
            if res["category_clean"] == "other":
                dropped_other += 1
                continue
            raw_ram = _safe_float(row.get("installed_ram_gb"))
            raw_storage = _safe_float(row.get("storage_gb"))
            raw_screen = _safe_float(row.get("screen_size_inch"))
            merged = {
                "listing_record_id": row["listing_record_id"],
                "seller_name": row["seller_name"],
                "category_clean": res["category_clean"],
                "brand": res["brand"],
                "model_clean": res["model_clean"],
                "cpu_model": res["cpu_model"],
                "ram_gb": res["ram_gb"] if res["ram_gb"] is not None else (int(raw_ram) if raw_ram is not None else None),
                "storage_gb": res["storage_gb"] if res["storage_gb"] is not None else (int(raw_storage) if raw_storage is not None else None),
                "gpu_model": res["gpu_model"],
                "screen_size_inch": (
                    res["screen_size_inch"] if res["screen_size_inch"] is not None else raw_screen
                ),
                "price_vnd": row["price_vnd"],
                "rating_norm": row.get("rating_norm"),
                "review_count_normalized": row.get("review_count_normalized"),
                "source": row["source"],
                "product_name": row["product_name"],
                "raw_specs": row["raw_specs"],
            }
            f.write(json.dumps(merged, ensure_ascii=False) + "\n")
            kept_rows.append(merged)
            cat_counts[res["category_clean"]] += 1

    # Also export a CSV for easy side-by-side inspection
    csv_out = output_path.with_suffix(".csv")
    pd.DataFrame(kept_rows).to_csv(csv_out, index=False, encoding="utf-8-sig")

    print(
        f"[Step 1] Saved {len(kept_rows)} cleaned listings -> {output_path} & {csv_out} "
        f"(dropped {dropped_other} 'other'; breakdown: {dict(cat_counts)})"
    )
    return output_path
