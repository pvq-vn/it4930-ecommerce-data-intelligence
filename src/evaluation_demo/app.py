"""IT4930 Multi-Retailer E-Commerce Market Intelligence & Fair-Value Analytics App."""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from demo_data import (
    audit_listing_fair_value,
    build_catalog,
    build_compatibility_options,
    load_demo_data,
    load_demo_model,
    local_explanation,
    prediction_frame,
    similar_listings,
)
from market_data import (
    ANOMALY_TYPE_LABELS,
    EDA_THEMES,
    RECOMMENDED_ACTION_LABELS,
    TV7_OUT_DIR,
    get_eda_items,
    get_tv6_charts,
    load_bipartite_html,
    load_eda_table,
    load_jaccard_matrix,
    load_louvain_segments,
    load_platform_kpis,
    load_retailer_stats,
    load_structural_holes,
    load_tv6_aspect_by_category,
    load_tv6_aspect_summary,
    load_tv6_lda_topics,
    load_tv6_model_comparison,
    load_tv7_full_flags,
    load_tv7_method_summary,
    summarize_tv7_types,
)


OUTPUT = Path(__file__).resolve().parent / "outputs"
TAB_LABELS = [
    "Tổng quan & Quy luật giá (TV1–TV3)",
    "Cạnh tranh đa sàn & Review (TV4 & TV6)",
    "Thẩm định giá hợp lý (TV5–TV8)",
    "Kiểm toán bất thường (TV7)",
    "Đánh giá mô hình & XAI (TV8)",
]
CATEGORIES = {"laptop": "Laptop", "smartphone": "Điện thoại"}
MODELS = {"lgbm": "LightGBM", "rf": "Random Forest", "ridge": "Ridge"}
MODEL_ORDER = ["Ridge", "Random Forest", "LightGBM"]
MODEL_COLORS = ["#196A9F", "#CE572E", "#008778"]
TABLES = {
    1: "table_10_1_model_benchmark_3d.csv",
    2: "table_10_2_ablation_and_tv7_sensitivity.csv",
    3: "table_10_3_error_by_price_tier.csv",
    4: "table_10_4_error_by_brand_and_seller.csv",
    5: "table_10_5_error_by_stock_and_missingness.csv",
    6: "table_10_6_cross_store_generalization.csv",
    7: "table_10_7_top20_worst_predictions_audit.csv",
}
DIMENSIONS = {
    "price_tier": "Khoảng giá",
    "brand": "Thương hiệu",
    "seller_name": "Nhà bán lẻ",
    "availability_status": "Tồn kho",
    "ram_status": "Thông tin RAM",
    "cross_store_group": "Độ phủ cửa hàng",
}
SEGMENTS = {
    "under_10m": "Dưới 10 triệu",
    "10m_to_under_20m": "10 đến dưới 20 triệu",
    "20m_to_35m": "20 đến 35 triệu",
    "over_35m": "Trên 35 triệu",
    "in_stock": "Còn hàng",
    "out_of_stock": "Hết hàng",
    "unknown": "Chưa rõ",
    "missing": "Thiếu",
    "present": "Có dữ liệu",
    "missing_configuration": "Thiếu cấu hình",
    "seen_other_store": "Đã thấy ở cửa hàng khác",
    "seen_same_store_only": "Chỉ thấy ở cùng cửa hàng",
    "unseen_configuration": "Cấu hình chưa thấy",
    "unknown_seller": "Chưa rõ cửa hàng",
}
SEVERITIES = {"none": "Không có cờ", "review": "Cần kiểm tra", "extreme": "Cực đoan"}
GAP_TYPE_LABELS = {
    "all": "Tất cả khoảng trống",
    "retailer_blind_spot": "Điểm mù danh mục của từng sàn (Retailer Blind Spot)",
    "underserved_high_demand": "Phân khúc cầu cao – ít sàn bán (Underserved High Demand)",
}

_ST_PARTS = tuple(int(x) for x in st.__version__.split(".")[:2] if x.isdigit())
_STRETCH_KW = {"width": "stretch"} if _ST_PARTS >= (1, 49) else {"use_container_width": True}


def money(vnd: float) -> str:
    return f"{vnd:,.0f}".replace(",", ".") + " đ"


def signed_money(vnd: float) -> str:
    sign = "+" if vnd >= 0 else "−"
    return f"{sign}{money(abs(vnd))}"


@st.cache_resource(show_spinner="Đang nạp dữ liệu nền tảng…")
def splits_for_demo():
    return load_demo_data()


@st.cache_resource(show_spinner=False, max_entries=6)
def cached_model(category: str, key: str):
    return load_demo_model(category, key)


@st.cache_data(show_spinner=False)
def catalog_for_demo() -> pd.DataFrame:
    return build_catalog(splits=splits_for_demo())


@st.cache_data(show_spinner=False)
def kpis_for_demo() -> dict:
    return load_platform_kpis(catalog_for_demo())


@st.cache_data(show_spinner=False)
def tv7_flags_for_demo() -> pd.DataFrame:
    return load_tv7_full_flags()


@st.cache_data(show_spinner=False)
def read_table(filename: str, modified_ns: int) -> pd.DataFrame:
    return pd.read_csv(OUTPUT / "tables" / filename)


def table(which: int | str) -> pd.DataFrame:
    filename = TABLES[which] if isinstance(which, int) else which
    path = OUTPUT / "tables" / filename
    return read_table(filename, path.stat().st_mtime_ns)


def show_image_path(path: Path, caption: str) -> None:
    if path.is_file():
        st.image(str(path), caption=caption, **_STRETCH_KW)
    else:
        st.caption(f"Chưa tìm thấy tệp hình ảnh: {path.name} ({caption}).")


def show_figure(filename: str, caption: str) -> None:
    show_image_path(OUTPUT / "figures" / filename, caption)


def preferred(values: list, desired) -> int:
    for idx, value in enumerate(values):
        if isinstance(value, str) and isinstance(desired, str) and value.casefold() == desired.casefold():
            return idx
        if value == desired:
            return idx
    return 0


def render_insight_box(question: str, finding: str, action: str) -> None:
    with st.container(border=True):
        st.markdown(f"**1. Câu hỏi nghiệp vụ:** {question}")
        st.markdown(f"**2. Phát hiện định lượng từ dữ liệu:** {finding}")
        st.markdown(f"**3. Ý nghĩa kinh doanh & Quyết định phân tích:** {action}")


def plot_contributions(contribution: pd.DataFrame) -> None:
    ordered = contribution.assign(magnitude=contribution["delta_vnd"].abs()).sort_values("magnitude", ascending=False)
    top = ordered.head(6)[["label", "delta_vnd"]].reset_index(drop=True)
    if len(ordered) > len(top):
        top.loc[len(top)] = ["Các yếu tố còn lại", ordered.iloc[len(top):]["delta_vnd"].sum()]
    top["Triệu đồng"] = top["delta_vnd"] / 1e6
    top["Hướng"] = np.where(top["delta_vnd"].ge(0), "Tăng", "Giảm")
    top["Đóng góp"] = top["delta_vnd"].map(signed_money)
    chart = alt.Chart(top).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("Triệu đồng:Q", title="Đóng góp vào giá hợp lý (triệu đồng)"),
        y=alt.Y("label:N", sort=top["label"].tolist(), title=None, axis=alt.Axis(labelLimit=185)),
        color=alt.Color("Hướng:N", scale=alt.Scale(domain=["Tăng", "Giảm"], range=["#C54F2C", "#196A9F"]), legend=None),
        tooltip=[alt.Tooltip("label:N", title="Yếu tố"), alt.Tooltip("Đóng góp:N")],
    ).properties(height=240)
    st.altair_chart(chart, **_STRETCH_KW)


def example_row(train: pd.DataFrame, brand: str, device: str) -> dict:
    pool = train.loc[
        train["brand"].fillna("").str.casefold().eq(brand.casefold())
        & train["model_clean"].fillna("").str.casefold().eq(device.casefold())
    ]
    if pool.empty:
        return {}
    if brand.casefold() == "apple" and device.casefold() == "iphone 15 pro max":
        rank = pool["seller_name"].fillna("").str.casefold().eq("fpt").astype(int) * 2 + pool["storage_gb"].eq(256).astype(int)
        pool = pool.loc[[rank.idxmax()]]
    else:
        present = pool[["ram_gb", "storage_gb", "screen_size_inch", "cpu_model"]].notna().sum(axis=1)
        pool = pool.loc[[present.idxmax()]]
    return pool.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# TAB 1: TV1 - TV3 (Data Acquisition, Integration & Exploratory Data Analysis)
# ---------------------------------------------------------------------------
def overview_eda_tab() -> None:
    kpis = kpis_for_demo()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng sản phẩm thu thập (TV1)", f"{kpis['total_listings']:,}".replace(",", "."), "Laptop & Smartphone")
    c2.metric("Hệ thống bán lẻ tích hợp", f"{kpis['retailer_count']} sàn", "CellphoneS · TGDĐ · FPT · Hoàng Hà · Viettel")
    c3.metric("Đánh giá khách hàng (TV6)", f"{kpis['total_reviews']:,}".replace(",", "."), f"{kpis['usable_reviews']:,} review có văn bản".replace(",", "."))
    c4.metric("Bản ghi sạch phân tích giá", f"{kpis['clean_listings']:,}".replace(",", "."), f"{kpis['canonical_products']:,} sản phẩm chuẩn TV4".replace(",", "."))

    st.caption(
        "Quy trình Khoa học Dữ liệu khép kín: Thu thập đa nguồn bất biến (TV1) → Chuẩn hóa 5 tầng Staging/Silver/Gold (TV2) "
        "→ Khám phá quy luật thị trường & kiểm định giả thuyết thống kê (TV3)."
    )

    theme_key = st.selectbox(
        "Chọn nhóm câu hỏi nghiên cứu EDA (TV3)",
        list(EDA_THEMES),
        format_func=EDA_THEMES.get,
        key="eda_theme_selector",
    )
    items = get_eda_items(theme_key)
    for item in items:
        st.subheader(item["title"])
        show_image_path(item["figure_path"], item["title"])
        render_insight_box(item["question"], item["finding"], item["action"])
        df_tbl = load_eda_table(item["table"])
        if not df_tbl.empty:
            with st.expander(f"Xem bảng thống kê gốc ({item['table']})"):
                st.dataframe(df_tbl, hide_index=True, **_STRETCH_KW)

    st.info(
        "Lưu ý phương pháp luận (TV3): Mọi hệ số tương quan (Pearson r, Spearman ρ) và kiểm định (ANOVA F, Kruskal-Wallis H, Mann-Whitney U) "
        "phản ánh mối liên hệ thống kê quan sát trên thị trường thương mại điện tử Việt Nam, không đồng nhất với quan hệ nhân quả về chi phí sản xuất."
    )


# ---------------------------------------------------------------------------
# TAB 2: TV4 (Market Graph & Structural Holes) + TV6 (Customer Review NLP)
# ---------------------------------------------------------------------------
def market_and_nlp_tab() -> None:
    st.subheader("A. Đồ thị cạnh tranh đa sàn & Khoảng trống thị trường (TV4)")
    category = st.radio(
        "Ngành hàng phân tích đồ thị",
        list(CATEGORIES),
        format_func=CATEGORIES.get,
        horizontal=True,
        key="tv4_category",
    )

    stats = load_retailer_stats(category)
    if not stats.empty:
        display_stats = stats.rename(columns={
            "retailer": "Nhà bán lẻ",
            "total_canonical_products": "Số SP chuẩn",
            "exclusive_count": "SP độc quyền (1 sàn)",
            "competitive_count": "SP cạnh tranh (≥2 sàn)",
            "exclusive_pct": "Tỷ lệ độc quyền (%)",
            "price_leader_win_rate_pct": "Tỷ lệ thắng giá đáy (%)",
            "avg_price_premium_pct": "Đắt hơn giá đáy TB (%)",
            "median_price_premium_pct": "Đắt hơn giá đáy trung vị (%)",
        })
        keep_cols = [c for c in [
            "Nhà bán lẻ", "Số SP chuẩn", "SP độc quyền (1 sàn)", "SP cạnh tranh (≥2 sàn)",
            "Tỷ lệ độc quyền (%)", "Tỷ lệ thắng giá đáy (%)", "Đắt hơn giá đáy TB (%)", "Đắt hơn giá đáy trung vị (%)",
        ] if c in display_stats.columns]
        st.markdown("**Định vị danh mục & Năng lực cạnh tranh giá giữa 5 sàn**")
        st.dataframe(display_stats[keep_cols].round(2), hide_index=True, **_STRETCH_KW)
        render_insight_box(
            question="Nhà bán lẻ nào dẫn đầu về độ phủ độc quyền và nhà bán lẻ nào dẫn đầu về giá rẻ trên các mẫu máy bán trùng?",
            finding=(
                "CellphoneS nắm danh mục độc quyền lớn nhất ở cả Laptop (93,19% trên 2.350 mẫu chuẩn) và Smartphone (87,10% trên 1.039 mẫu chuẩn). "
                "Trên nhóm sản phẩm cạnh tranh trực tiếp, Hoàng Hà Mobile dẫn đầu tỷ lệ thắng giá đáy (75,86% ở Laptop; 64,44% ở Smartphone), "
                "trong khi mức chênh giá trung bình so với giá đáy của 5 sàn chỉ dao động từ 0,55% đến 5,20%."
            ),
            action=(
                "Người tiêu dùng mua các mẫu phổ thông bán trùng giữa nhiều sàn nên so sánh trực tiếp với Hoàng Hà Mobile/Viettel Store/CellphoneS; "
                "nhà bán lẻ muốn tránh chiến tranh giá trực diện cần mở rộng các cấu hình độc quyền (long-tail SKU)."
            ),
        )

    jaccard = load_jaccard_matrix(category)
    if not jaccard.empty:
        st.markdown("**Ma trận trùng lặp danh mục sản phẩm chuẩn Jaccard (%)**")
        jaccard_pct = jaccard.copy()
        for col in jaccard_pct.columns[1:]:
            jaccard_pct[col] = (pd.to_numeric(jaccard_pct[col], errors="coerce") * 100.0).round(2)
        st.dataframe(jaccard_pct, hide_index=True, **_STRETCH_KW)

    st.markdown("**Khám phá Khoảng trống thị trường & Khuyến nghị nhập hàng (Structural Holes)**")
    all_holes = load_structural_holes()
    if not all_holes.empty:
        f1, f2, f3 = st.columns(3)
        cat_filter = f1.selectbox(
            "Lọc ngành hàng",
            ["all", "laptop", "smartphone"],
            format_func={"all": "Cả Laptop & Điện thoại", "laptop": "Laptop", "smartphone": "Điện thoại"}.get,
            key="hole_cat",
        )
        retailer_opts = ["all", *sorted(all_holes["retailer"].dropna().unique().tolist())]
        ret_filter = f2.selectbox(
            "Lọc nhà bán lẻ / Toàn thị trường",
            retailer_opts,
            format_func=lambda x: "Tất cả đối tượng" if x == "all" else ("Toàn thị trường (ALL_MARKET)" if x == "ALL_MARKET" else x),
            key="hole_retailer",
        )
        gap_filter = f3.selectbox("Loại khoảng trống", list(GAP_TYPE_LABELS), format_func=GAP_TYPE_LABELS.get, key="hole_gap")

        filtered_holes = load_structural_holes(category=cat_filter, retailer=ret_filter, gap_type=gap_filter)
        st.caption(f"Tìm thấy **{len(filtered_holes)}** khoảng trống danh mục (trên tổng số 68 điểm mù nhà bán lẻ & 22 phân khúc thiếu cung toàn thị trường).")
        hole_cols = {
            "gap_type": "Loại khoảng trống",
            "retailer": "Đơn vị",
            "segment_label": "Phân khúc Louvain",
            "price_range_m": "Khoảng giá (triệu)",
            "top_brands": "Hãng chủ đạo",
            "segment_total_products": "Tổng SP phân khúc",
            "retailer_products": "Số SP hiện có",
            "perf_recommendation": "Khuyến nghị cấu hình nhập hàng (B2B Action)",
        }
        present_hole_cols = [c for c in hole_cols if c in filtered_holes.columns]
        st.dataframe(filtered_holes[present_hole_cols].rename(columns=hole_cols), hide_index=True, **_STRETCH_KW)

    segments = load_louvain_segments(category)
    if not segments.empty:
        with st.expander(f"Xem chi tiết {len(segments)} phân khúc vi mô Louvain ({CATEGORIES[category]})"):
            st.dataframe(segments.round(2), hide_index=True, **_STRETCH_KW)

    with st.expander(f"Mở đồ thị tương tác hai phía Nhà bán lẻ – Sản phẩm chuẩn ({CATEGORIES[category]})"):
        html_doc = load_bipartite_html(category)
        if html_doc:
            components.html(html_doc, height=580, scrolling=True)
        else:
            st.caption("Không tìm thấy tệp đồ thị HTML tương tác.")

    st.divider()
    st.subheader("B. Khai phá Tiếng nói Khách hàng bằng Xử lý Ngôn ngữ Tự nhiên (TV6)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tỷ lệ đánh giá 5 sao", "84,79%", "Lạm phát điểm sao (TB 4,56★)")
    m2.metric("Tỷ lệ sản phẩm Cold-Start", "73,10%", "5.154/7.051 SP cha chưa có review")
    m3.metric("PhoBERT Macro F1", "0,6491", "+10,0% so với Logistic Baseline")
    m4.metric("Điểm nóng phàn nàn số 1", "21,70% tiêu cực", "Hiệu năng & Tản nhiệt")

    lda = load_tv6_lda_topics()
    aspect = load_tv6_aspect_summary()
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**5 Chủ đề thảo luận tiềm ẩn (LDA Topic Modeling)**")
        if not lda.empty:
            st.dataframe(
                lda.rename(columns={
                    "topic_id": "Mã",
                    "topic_name": "Chủ đề thảo luận",
                    "corpus_share_pct": "Tỷ trọng (%)",
                    "dominant_doc_count": "Số review",
                    "top_keywords": "Từ khóa đặc trưng",
                }),
                hide_index=True,
                **_STRETCH_KW,
            )
    with col_r:
        st.markdown("**Phân tích cảm xúc theo 5 khía cạnh kỹ thuật (ABSA)**")
        if not aspect.empty:
            st.dataframe(aspect.round(2), hide_index=True, **_STRETCH_KW)

    tv6_charts = get_tv6_charts()
    chosen_idx = st.selectbox(
        "Chọn biểu đồ phân tích NLP chuyên sâu (TV6)",
        list(range(len(tv6_charts))),
        format_func=lambda idx: tv6_charts[idx]["title"],
        key="tv6_chart_selector",
    )
    chosen_chart = tv6_charts[chosen_idx]
    show_image_path(chosen_chart["figure_path"], chosen_chart["title"])
    render_insight_box(chosen_chart["question"], chosen_chart["finding"], chosen_chart["action"])

    aspect_cat = load_tv6_aspect_by_category()
    model_cmp = load_tv6_model_comparison()
    with st.expander("Xem đối sánh khía cạnh Laptop vs Smartphone & Bảng thực nghiệm PhoBERT"):
        if not aspect_cat.empty:
            st.dataframe(aspect_cat, hide_index=True, **_STRETCH_KW)
        if not model_cmp.empty:
            st.dataframe(model_cmp, hide_index=True, **_STRETCH_KW)


# ---------------------------------------------------------------------------
# TAB 3: TV5 + TV8 (Hedonic Fair-Value Audit & Hardware-Compatible Simulator)
# ---------------------------------------------------------------------------
def _default_audit_row(cat_df: pd.DataFrame, category: str) -> pd.Series:
    if category == "smartphone":
        mask = (
            cat_df["brand"].fillna("").str.casefold().eq("apple")
            & cat_df["model_clean"].fillna("").str.casefold().eq("iphone 15 pro max")
            & cat_df["seller_name"].fillna("").str.casefold().eq("fpt")
            & pd.to_numeric(cat_df["storage_gb"], errors="coerce").eq(256)
        )
        if mask.any():
            return cat_df.loc[mask].iloc[0]
    return cat_df.iloc[0]


def _render_real_sku_audit_mode(splits: dict, catalog: pd.DataFrame) -> None:
    st.caption(
        "Dành cho người mua (B2C) & kiểm toán viên ngành hàng (B2B): Chọn trực tiếp sản phẩm đang niêm yết trên 5 sàn "
        "(không cần tự nhập thông số kỹ thuật) để đối chiếu Giá bán thực tế với Giá trị Hợp lý theo cấu hình (Hedonic Fair Value)."
    )
    c1, c2 = st.columns(2)
    category = c1.selectbox("Loại thiết bị", list(CATEGORIES), index=1, format_func=CATEGORIES.get, key="audit_category")
    model_key = c2.selectbox("Mô hình định giá tham chiếu", list(MODELS), format_func=MODELS.get, key="audit_model")

    cat_df = catalog.loc[catalog["category_clean"].eq(category)].reset_index(drop=True)
    default_row = _default_audit_row(cat_df, category)

    b1, b2 = st.columns([1, 1.4])
    brands = sorted(cat_df["brand"].dropna().unique().tolist(), key=str.casefold)
    brand = b1.selectbox(
        "Thương hiệu",
        brands,
        index=preferred(brands, default_row["brand"]),
        key=f"audit_brand_{category}",
    )
    brand_df = cat_df.loc[cat_df["brand"].eq(brand)].reset_index(drop=True)
    devices = sorted(brand_df["model_clean"].dropna().unique().tolist(), key=str.casefold)
    device = b2.selectbox(
        "Dòng sản phẩm",
        devices,
        index=preferred(devices, default_row["model_clean"]),
        key=f"audit_device_{category}_{brand}",
    )
    sku_df = brand_df.loc[brand_df["model_clean"].eq(device)].sort_values(["price_vnd", "listing_record_id"]).reset_index(drop=True)

    def _sku_label(idx: int) -> str:
        r = sku_df.iloc[idx]
        ram = f"{int(r['ram_gb'])}GB" if pd.notna(r.get("ram_gb")) else "?GB"
        rom = f"{int(r['storage_gb'])}GB" if pd.notna(r.get("storage_gb")) else "?GB"
        stock = "Còn hàng" if r.get("availability_status") == "in_stock" else "Hết/Ngừng KD"
        return f"{r['product_name']} | {r['seller_name']} | {ram}/{rom} | {money(float(r['price_vnd']))} ({stock})"

    default_sku_idx = 0
    if default_row["listing_record_id"] in set(sku_df["listing_record_id"]):
        default_sku_idx = int(np.flatnonzero(sku_df["listing_record_id"].eq(default_row["listing_record_id"]))[0])

    chosen_sku_idx = st.selectbox(
        "Chọn phiên bản niêm yết thực tế trên sàn",
        list(range(len(sku_df))),
        index=default_sku_idx,
        format_func=_sku_label,
        key=f"audit_sku_{category}_{brand}_{device}",
    )
    row = sku_df.iloc[chosen_sku_idx]

    bench_row = table(1).query("category == @category and model == @model_key")
    mdape_pct = float(bench_row.iloc[0]["mdape_pct"]) if not bench_row.empty else 10.0
    split = splits[category]
    model = cached_model(category, model_key)
    audit = audit_listing_fair_value(row, split, model, mdape_pct=mdape_pct)

    k1, k2, k3 = st.columns(3)
    k1.metric("Giá niêm yết thực tế tại sàn", money(audit["recorded_price_vnd"]), f"Sàn: {row['seller_name']}")
    k2.metric(
        "Giá hợp lý theo cấu hình (Fair Value)",
        money(audit["fair_value_vnd"]),
        f"Dải ±{mdape_pct:.1f}% MdAPE",
    )
    k3.metric(
        "Độ lệch (Thực tế − Hợp lý)",
        signed_money(audit["gap_vnd"]),
        f"{audit['gap_pct']:+.1f}%",
        delta_color="inverse",
    )

    if audit["verdict"] == "undervalued":
        st.success(
            f"**Kết luận thẩm định:** {audit['verdict_label']} · Dải tham chiếu: "
            f"**{money(audit['low_fair_vnd'])} – {money(audit['high_fair_vnd'])}**."
        )
    elif audit["verdict"] == "overvalued":
        st.warning(
            f"**Kết luận thẩm định:** {audit['verdict_label']} · Dải tham chiếu: "
            f"**{money(audit['low_fair_vnd'])} – {money(audit['high_fair_vnd'])}**."
        )
    else:
        st.info(
            f"**Kết luận thẩm định:** {audit['verdict_label']} · Dải tham chiếu: "
            f"**{money(audit['low_fair_vnd'])} – {money(audit['high_fair_vnd'])}**."
        )

    left_col, right_col = st.columns([1.15, 1], gap="large")
    with left_col:
        st.markdown("**Giải thích các yếu tố cấu thành Giá hợp lý (SHAP VNĐ)**")
        try:
            base, contributions = local_explanation(model, model_key, audit["frame"], split.X_train)
            st.caption(f"Mức nền thị trường: {money(base)} · Cộng tổng các đóng góp khớp chính xác Giá hợp lý {money(audit['fair_value_vnd'])}.")
            plot_contributions(contributions)
        except (ImportError, ValueError, RuntimeError) as exc:
            st.caption(f"Chưa hiển thị được biểu đồ đóng góp cho mô hình này: {exc}")

    with right_col:
        st.markdown("**Hồ sơ Kiểm toán Dữ liệu (TV7) & Cảm xúc Khách hàng (TV6)**")
        with st.container(border=True):
            a_type = str(row.get("anomaly_type", "none"))
            a_act = str(row.get("recommended_action", "none"))
            a_sev = SEVERITIES.get(str(row.get("anomaly_severity", "none")), "Không rõ")
            st.markdown(f"- **Mức cờ kiểm toán TV7:** `{a_sev}`")
            st.markdown(f"- **Phân loại bản chất (`anomaly_type`):** {ANOMALY_TYPE_LABELS.get(a_type, a_type)}")
            st.markdown(f"- **Khuyến nghị xử lý (`recommended_action`):** {RECOMMENDED_ACTION_LABELS.get(a_act, a_act)}")
            if row.get("anomaly_reasons"):
                st.markdown(f"- **Lý do chi tiết:** {row['anomaly_reasons']}")
            st.divider()
            has_rev = int(row.get("has_review_data", 0) or 0)
            rev_cnt = int(row.get("review_count_usable", 0) or 0)
            if has_rev > 0 and rev_cnt > 0:
                avg_sent = float(row.get("avg_sentiment_score", 0.0) or 0.0)
                pos_ratio = float(row.get("sentiment_positive_ratio", 0.0) or 0.0) * 100.0
                avg_rat = row.get("avg_rating")
                rat_str = f"{float(avg_rat):.2f}★" if pd.notna(avg_rat) else "N/A"
                st.markdown(
                    f"- **Đánh giá thực tế (TV6):** Có **{rev_cnt}** review hợp lệ · Sao TB: **{rat_str}** · "
                    f"Tích cực PhoBERT: **{pos_ratio:.1f}%** (Điểm cảm xúc: `{avg_sent:+.3f}`)"
                )
            else:
                st.markdown(
                    "- **Đánh giá thực tế (TV6):** Sản phẩm thuộc nhóm Cold-Start (chưa có bình luận văn bản); "
                    "mô hình sử dụng chỉ số uy tín cảm xúc thương hiệu (`brand_sentiment_prior`)."
                )

    st.markdown("**Đối chiếu giá niêm yết của các cấu hình tương đương trên 5 sàn**")
    examples = similar_listings(catalog, category, row.to_dict(), limit=5)
    display = examples[["product_name", "seller_name", "ram_gb", "storage_gb", "price_vnd", "anomaly_type", "anomaly_severity"]].copy()
    display["price_vnd"] = display["price_vnd"].map(money)
    display["anomaly_type"] = display["anomaly_type"].map(ANOMALY_TYPE_LABELS).fillna("Bình thường")
    display["anomaly_severity"] = display["anomaly_severity"].map(SEVERITIES).fillna("Không có cờ")
    st.dataframe(
        display.rename(columns={
            "product_name": "Sản phẩm",
            "seller_name": "Nhà bán lẻ",
            "ram_gb": "RAM (GB)",
            "storage_gb": "Bộ nhớ (GB)",
            "price_vnd": "Giá niêm yết",
            "anomaly_type": "Phân loại TV7",
            "anomaly_severity": "Mức cờ",
        }),
        hide_index=True,
        **_STRETCH_KW,
    )


def _render_compatible_simulator_mode(splits: dict, catalog: pd.DataFrame) -> None:
    st.caption(
        "Dành cho Quản trị ngành hàng / Đơn vị thu mua (B2B): Mô phỏng định giá cho SKU sắp nhập hàng. "
        "Các trường linh kiện được khóa cứng theo miền tương thích phần cứng thực tế của từng hãng và dòng máy."
    )
    c1, c2 = st.columns(2)
    category = c1.selectbox("Loại thiết bị", list(CATEGORIES), index=1, format_func=CATEGORIES.get, key="prediction_category")
    key = c2.selectbox("Mô hình dự đoán", list(MODELS), format_func=MODELS.get, key="prediction_model")
    split = splits[category]
    train = split.X_train

    entry, outcome = st.columns([1.08, 1], gap="large")
    with entry:
        base_compat = build_compatibility_options(train, category)
        brand_options = base_compat["brands"]
        brand = st.selectbox(
            "Thương hiệu",
            brand_options,
            index=preferred(brand_options, "Apple" if category == "smartphone" else "ASUS"),
            key=f"brand_{category}",
        )
        brand_compat = build_compatibility_options(train, category, brand=brand)
        device_options = brand_compat["devices"]
        device = st.selectbox(
            "Dòng máy",
            device_options,
            index=preferred(device_options, "iPhone 15 Pro Max"),
            key=f"device_{category}_{brand}",
        )
        sample = example_row(train, brand, device) if device else {}
        dev_compat = build_compatibility_options(train, category, brand=brand, device=device)

        cpu_opts = [None, *dev_compat["cpu_models"]]
        cpu = st.selectbox(
            "Vi xử lý (CPU tương thích)",
            cpu_opts,
            index=preferred(cpu_opts, sample.get("cpu_model")),
            format_func=lambda v: "Không rõ" if v is None else v,
            key=f"sim_cpu_{category}_{brand}_{device}",
        )
        compat = build_compatibility_options(train, category, brand=brand, device=device, cpu_model=cpu)
        allow_custom = st.checkbox(
            "Cho phép thử mức RAM/Bộ nhớ nâng cấp ngoài cấu hình đã quan sát của dòng máy",
            value=False,
            key=f"custom_spec_{category}_{brand}_{device}",
        )

        form_key = f"configuration_{category}_{brand}_{device}"
        with st.form(form_key):
            a, b = st.columns(2)
            with a:
                seller_opts = [None, *compat["sellers"]]
                seller = st.selectbox(
                    "Nhà bán lẻ dự kiến",
                    seller_opts,
                    index=preferred(seller_opts, sample.get("seller_name")),
                    format_func=lambda v: "Không rõ" if v is None else v,
                    key=f"{form_key}_seller",
                )
                if allow_custom:
                    ram_max = 24 if category == "smartphone" else 128
                    raw_ram = sample.get("ram_gb")
                    def_ram = int(raw_ram) if pd.notna(raw_ram) and 2 <= float(raw_ram) <= ram_max else None
                    ram = st.number_input("RAM (GB)", min_value=2, max_value=ram_max, value=def_ram, step=1)
                else:
                    ram_opts = [None, *compat["ram_gb_options"]]
                    ram_sample = int(round(float(sample["ram_gb"]))) if pd.notna(sample.get("ram_gb")) else None
                    ram = st.selectbox(
                        "RAM tương thích (GB)",
                        ram_opts,
                        index=preferred(ram_opts, ram_sample),
                        format_func=lambda v: "Không rõ" if v is None else f"{v} GB",
                        key=f"{form_key}_ram",
                    )
                pin_field = "battery_wh" if category == "laptop" else "battery_mah"
                pin_label = "Pin (Wh)" if category == "laptop" else "Pin (mAh)"
                raw_pin = sample.get(pin_field)
                if category == "laptop":
                    def_pin = float(raw_pin) if pd.notna(raw_pin) and 1.0 <= float(raw_pin) <= 200.0 else None
                    pin = st.number_input(pin_label, min_value=1.0, max_value=200.0, value=def_pin, step=0.1)
                else:
                    def_pin = int(raw_pin) if pd.notna(raw_pin) and 1 <= float(raw_pin) <= 20_000 else None
                    pin = st.number_input(pin_label, min_value=1, max_value=20_000, value=def_pin, step=1)
            with b:
                if allow_custom:
                    raw_rom = sample.get("storage_gb")
                    def_rom = int(raw_rom) if pd.notna(raw_rom) and 32 <= float(raw_rom) <= 8192 else None
                    storage = st.number_input("Bộ nhớ (GB)", min_value=32, max_value=8192, value=def_rom, step=32)
                else:
                    rom_opts = [None, *compat["storage_gb_options"]]
                    rom_sample = int(round(float(sample["storage_gb"]))) if pd.notna(sample.get("storage_gb")) else None
                    storage = st.selectbox(
                        "Bộ nhớ tương thích (GB)",
                        rom_opts,
                        index=preferred(rom_opts, rom_sample),
                        format_func=lambda v: "Không rõ" if v is None else f"{v} GB",
                        key=f"{form_key}_storage",
                    )
                scr_opts = compat["screen_size_options"]
                if not allow_custom and scr_opts:
                    s_opts = [None, *scr_opts]
                    scr_sample = round(float(sample["screen_size_inch"]), 1) if pd.notna(sample.get("screen_size_inch")) else None
                    screen = st.selectbox(
                        "Màn hình tương thích (inch)",
                        s_opts,
                        index=preferred(s_opts, scr_sample),
                        format_func=lambda v: "Không rõ" if v is None else f'{v}"',
                        key=f"{form_key}_screen",
                    )
                else:
                    bounds = (11.0, 18.5) if category == "laptop" else (4.0, 8.5)
                    raw_scr = sample.get("screen_size_inch")
                    def_scr = float(raw_scr) if pd.notna(raw_scr) and bounds[0] <= float(raw_scr) <= bounds[1] else None
                    screen = st.number_input("Màn hình (inch)", min_value=bounds[0], max_value=bounds[1], value=def_scr, step=0.1)

                if category == "laptop":
                    gpu_opts = [None, *compat["gpu_models"]]
                    gpu_val = st.selectbox(
                        "GPU tương thích",
                        gpu_opts,
                        index=preferred(gpu_opts, sample.get("gpu_model")),
                        format_func=lambda v: "Không rõ" if v is None else v,
                        key=f"{form_key}_gpu",
                    )

            product = {
                "brand": brand,
                "model_clean": device,
                "seller_name": seller,
                "cpu_model": cpu,
                "ram_gb": ram,
                "storage_gb": storage,
                "screen_size_inch": screen,
                pin_field: pin,
            }
            if category == "laptop":
                product["gpu_model"] = gpu_val
            else:
                d1, d2 = st.columns(2)
                with d1:
                    disp_opts = [None, *compat["display_types"]]
                    product["display_type_norm"] = st.selectbox(
                        "Công nghệ màn hình",
                        disp_opts,
                        index=preferred(disp_opts, sample.get("display_type_norm")),
                        format_func=lambda v: "Không rõ" if v is None else v,
                        key=f"{form_key}_display",
                    )
                    raw_cam = sample.get("camera_mp")
                    def_cam = int(raw_cam) if pd.notna(raw_cam) and 1 <= float(raw_cam) <= 250 else None
                    product["camera_mp"] = st.number_input("Camera chính (MP)", min_value=1, max_value=250, value=def_cam, step=1)
                with d2:
                    net_opts = [None, *compat["network_types"]]
                    product["network_type_norm"] = st.selectbox(
                        "Chuẩn mạng",
                        net_opts,
                        index=preferred(net_opts, sample.get("network_type_norm")),
                        format_func=lambda v: "Không rõ" if v is None else v,
                        key=f"{form_key}_network",
                    )

            submitted = st.form_submit_button("Dự đoán giá", type="primary", disabled=device is None, **_STRETCH_KW)

    request = (category, key, brand, device)
    with outcome:
        if submitted:
            st.session_state.pop("prediction_result", None)
            with st.spinner("Đang ước lượng Giá trị Hợp lý theo cấu hình…"):
                try:
                    frame = prediction_frame(product, category, split)
                    model = cached_model(category, key)
                    price = float(model.predict(frame)[0])
                    if not np.isfinite(price) or price <= 0:
                        raise ValueError("Giá nằm ngoài miền dự đoán hợp lệ.")
                    try:
                        base, contributions = local_explanation(model, key, frame, split.X_train)
                        explanation_error = None
                    except (ImportError, ValueError, RuntimeError) as exc:
                        base, contributions, explanation_error = None, None, str(exc)
                    st.session_state["prediction_result"] = (request, product, price, base, contributions, explanation_error)
                except (OSError, ValueError, SystemExit) as exc:
                    st.error(f"Chưa thể dự đoán. {exc}")

        result = st.session_state.get("prediction_result")
        if not result or result[0] != request:
            with st.container(border=True):
                st.subheader("Giá hợp lý ước lượng")
                st.write("Chọn cấu hình tương thích rồi bấm **Dự đoán giá** để xem mức định giá tham chiếu và giải thích SHAP.")
            return

        _, used, price, base, contributions, explanation_error = result
        with st.container(border=True):
            st.metric("Giá dự đoán", money(price))
            row = table(1).query("category == @category and model == @key")
            if not row.empty:
                typical = float(row.iloc[0]["mdape_pct"]) / 100
                st.write(f"**Dải tham chiếu:** {money(max(0, price * (1 - typical)))} đến {money(price * (1 + typical))}")
                st.caption(f"Dùng sai số phần trăm trung vị trên test ({typical:.1%}). Dải này không mang mức độ bao phủ xác suất.")

        unsupported = [
            label for field, label in (("ram_gb", "RAM"), ("storage_gb", "bộ nhớ"))
            if used[field] is not None and not pd.to_numeric(train[field], errors="coerce").eq(float(used[field])).any()
        ]
        if unsupported:
            st.warning(f"Tập huấn luyện chưa từng xuất hiện mức {' và '.join(unsupported)} đã nhập. Đây là ngoại suy ngoài phân phối dữ liệu.")

        st.subheader("Yếu tố kéo giá lên hoặc xuống")
        if explanation_error:
            st.caption(f"Chưa hiển thị được giải thích cho mô hình này. {explanation_error}")
        else:
            st.caption(f"Mô hình bắt đầu từ mức nền {money(base)}. Cộng các đóng góp sẽ ra giá hợp lý ước lượng.")
            if key == "rf" and contributions.attrs.get("approximated"):
                st.caption("Đóng góp được ước tính bằng 128 thứ tự hoán vị đặc trưng.")
            plot_contributions(contributions)

    st.subheader("Sản phẩm thực tế tương tự trên thị trường")
    examples = similar_listings(catalog, category, used)
    display = examples[["product_name", "seller_name", "ram_gb", "storage_gb", "price_vnd", "anomaly_severity"]].copy()
    display["price_vnd"] = display["price_vnd"].map(money)
    display["anomaly_severity"] = display["anomaly_severity"].map(SEVERITIES).fillna("Chưa có cờ")
    st.dataframe(
        display.rename(columns={
            "product_name": "Sản phẩm",
            "seller_name": "Nhà bán lẻ",
            "ram_gb": "RAM (GB)",
            "storage_gb": "Bộ nhớ (GB)",
            "price_vnd": "Giá ghi nhận",
            "anomaly_severity": "Cờ TV7",
        }),
        hide_index=True,
        **_STRETCH_KW,
    )


def fair_value_tab() -> None:
    st.subheader("Thẩm định Giá Hợp lý & Mô phỏng Định giá Cấu hình (Hedonic Fair-Value Analytics)")
    try:
        splits = splits_for_demo()
        catalog = catalog_for_demo()
    except (OSError, ValueError, SystemExit) as exc:
        st.error(f"Chưa đọc được dữ liệu thẩm định giá. {exc}")
        return

    mode = st.radio(
        "Chế độ nghiệp vụ",
        ["audit_sku", "simulate_sku"],
        format_func={
            "audit_sku": "1. Thẩm định SKU đang niêm yết thực tế trên 5 sàn (B2C & B2B — Khuyến nghị)",
            "simulate_sku": "2. Mô phỏng định giá SKU mới có khóa tương thích phần cứng (B2B Category Manager)",
        }.get,
        horizontal=True,
        key="fair_value_mode",
    )
    if mode == "audit_sku":
        _render_real_sku_audit_mode(splits, catalog)
    else:
        _render_compatible_simulator_mode(splits, catalog)


# ---------------------------------------------------------------------------
# TAB 4: TV7 (Market Anomaly Detection & Catalog Hygiene Audit)
# ---------------------------------------------------------------------------
def anomaly_audit_tab() -> None:
    st.subheader("Kiểm toán Bất thường Thị trường & Chất lượng Danh mục (TV7)")
    flags = tv7_flags_for_demo()
    methods = load_tv7_method_summary()
    if flags.empty:
        st.warning("Chưa tìm thấy bảng cờ kiểm toán TV7.")
        return

    total_rows = len(flags)
    valid_price_rows = int(flags["price_status"].eq("valid").sum())
    flagged_rows = int(flags["combined_flag_bool"].sum())
    flagship_rows = int(flags["anomaly_type"].eq("rare_valid_flagship").sum())

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Tổng bản ghi kiểm toán", f"{total_rows:,}".replace(",", "."), f"{valid_price_rows:,} bản ghi có giá dương".replace(",", "."))
    a2.metric("Tổng listing gắn cờ (Hợp 3 PP)", f"{flagged_rows:,}".replace(",", "."), f"{100 * flagged_rows / total_rows:.2f}% toàn bộ dữ liệu")
    a3.metric("Đồng thuận ≥ 2 phương pháp", f"{int((flags['methods_agree'] >= 2).sum())}", "Ưu tiên rà soát cao (Extreme)")
    a4.metric("Siêu phẩm hợp lệ cần bảo toàn", f"{flagship_rows}", "rare_valid_flagship (Giữ lại)")

    col_m, col_t = st.columns([1, 1.45])
    with col_m:
        st.markdown("**Số lượng phát hiện theo từng phương pháp**")
        if not methods.empty:
            st.dataframe(
                methods.rename(columns={"method": "Phương pháp phát hiện", "flagged": "Số listing gắn cờ"}),
                hide_index=True,
                **_STRETCH_KW,
            )
    with col_t:
        st.markdown("**Phân rã theo 4 nhóm bản chất nghiệp vụ (`anomaly_type`)**")
        type_summary = summarize_tv7_types(flags)
        if not type_summary.empty:
            st.dataframe(
                type_summary[[
                    "anomaly_type_vi",
                    "listing_count",
                    "share_of_flagged_pct",
                    "extreme_count",
                    "recommended_action_vi",
                ]].rename(columns={
                    "anomaly_type_vi": "Nhóm bất thường",
                    "listing_count": "Số listing",
                    "share_of_flagged_pct": "Tỷ trọng cờ (%)",
                    "extreme_count": "Mức Extreme",
                    "recommended_action_vi": "Hành động khuyến nghị",
                }),
                hide_index=True,
                **_STRETCH_KW,
            )

    st.markdown("**Tra cứu trực tiếp các bản ghi bất thường trên 5 sàn**")
    f1, f2, f3, f4 = st.columns(4)
    cat_f = f1.selectbox(
        "Ngành hàng",
        ["all", "laptop", "smartphone"],
        format_func={"all": "Tất cả", "laptop": "Laptop", "smartphone": "Smartphone"}.get,
        key="tv7_cat",
    )
    type_opts = ["all_flagged", "low_price_or_category_noise", "hardware_spec_error", "rare_valid_flagship", "spec_price_mismatch_review"]
    type_f = f2.selectbox(
        "Loại bất thường",
        type_opts,
        format_func=lambda k: "Mọi bản ghi có cờ (715)" if k == "all_flagged" else ANOMALY_TYPE_LABELS.get(k, k),
        key="tv7_type",
    )
    sev_f = f3.selectbox(
        "Mức độ nghiêm trọng",
        ["all", "extreme", "review"],
        format_func={"all": "Tất cả mức cờ", "extreme": "Extreme (Cực đoan)", "review": "Review (Cần kiểm tra)"}.get,
        key="tv7_sev",
    )
    sources = ["all", *sorted(flags["source"].dropna().unique().tolist())]
    src_f = f4.selectbox("Nguồn thu thập", sources, format_func=lambda s: "Tất cả 5 sàn" if s == "all" else s, key="tv7_source")

    view = flags.loc[flags["combined_flag_bool"]].copy()
    if cat_f != "all":
        view = view.loc[view["category_group"].eq(cat_f)]
    if type_f != "all_flagged":
        view = view.loc[view["anomaly_type"].eq(type_f)]
    if sev_f != "all":
        view = view.loc[view["anomaly_severity"].eq(sev_f)]
    if src_f != "all":
        view = view.loc[view["source"].eq(src_f)]

    view = view.sort_values(["methods_agree", "isolation_score"], ascending=[False, False])
    st.caption(f"Đang hiển thị **{len(view)}** bản ghi khớp bộ lọc kiểm toán.")
    display_view = view[[
        "product_name", "source", "category_group", "brand_norm", "price_vnd",
        "anomaly_severity", "anomaly_type_vi", "recommended_action_vi", "methods_agree", "anomaly_reasons",
    ]].head(150).copy()
    display_view["price_vnd"] = display_view["price_vnd"].map(lambda v: money(v) if pd.notna(v) and v > 0 else "Thiếu / <= 0 đ")
    st.dataframe(
        display_view.rename(columns={
            "product_name": "Sản phẩm",
            "source": "Sàn",
            "category_group": "Ngành hàng",
            "brand_norm": "Hãng",
            "price_vnd": "Giá ghi nhận",
            "anomaly_severity": "Mức cờ",
            "anomaly_type_vi": "Phân loại bất thường",
            "recommended_action_vi": "Khuyến nghị xử lý",
            "methods_agree": "Số PP đồng thuận",
            "anomaly_reasons": "Lý do chi tiết",
        }),
        hide_index=True,
        **_STRETCH_KW,
    )

    show_image_path(
        TV7_OUT_DIR / "anomaly_price_vs_ram.png",
        "Phân bố Log(Giá bán) theo RAM và mức độ bất thường trên 2 ngành hàng (TV7)",
    )
    render_insight_box(
        question="Vì sao trong Khoa học Dữ liệu không được xóa mù toàn bộ điểm ngoại lai (combined_flag) trước khi phân tích và mô hình hóa?",
        finding=(
            "Trong 715 bản ghi gắn cờ có 401 lỗi giá thấp/sai danh mục (như cáp sạc 189k, Galaxy Z Fold giá 390k hay 105 máy bàn iMac nằm trong mục laptop) "
            "nhưng đồng thời có 65 siêu phẩm hợp lệ (rare_valid_flagship như MacBook Pro 128GB/8TB, ROG Strix SCAR, MSI Titan). "
            "Thực nghiệm S5b (TV8) chứng minh: xóa mù toàn bộ combined_flag làm mất 10/13 smartphone >=80M trong tập train và khiến MAE phân khúc cao tăng vọt gấp đôi từ 20,0M lên 40,4M."
        ),
        action=(
            "Áp dụng cơ chế xử lý phân tầng theo anomaly_type: chỉ loại bỏ nhóm lỗi danh mục/giá dưới sàn (filter_before_modeling), "
            "sửa thông số bẩn (verify_or_correct_specs), và giữ nguyên nhóm siêu phẩm hợp lệ với biến đổi log-price."
        ),
    )


# ---------------------------------------------------------------------------
# TAB 5: TV8 (3D Model Validation, S1-S5 Ablation, Sliced Errors & Global SHAP)
# ---------------------------------------------------------------------------
def _render_benchmark_and_ablation() -> None:
    st.markdown("#### So sánh 3 chiều: Độ chính xác – Tốc độ suy luận – Độ bền vững khi khuyết cấu hình")
    category = st.selectbox("Loại thiết bị", list(CATEGORIES), format_func=CATEGORIES.get, key="benchmark_category")
    benchmark = table(1).query("category == @category").copy()
    benchmark["Mô hình"] = benchmark["model"].map(MODELS)
    names = {
        "mae_vnd": "MAE (đ)",
        "rmse_vnd": "RMSE (đ)",
        "mdape_pct": "MdAPE (%)",
        "r2": "R²",
        "latency_ms_per_sample": "Thời gian (ms/mẫu)",
        "model_size_mb": "Tệp (MB)",
        "mae_change_pct": "MAE tăng khi che 20% RAM/bộ nhớ (%)",
    }
    st.caption("Đánh giá trên tập kiểm thử độc lập phân tách theo source_parent_id (Zero Data Leakage).")
    st.dataframe(benchmark[["Mô hình", *names]].rename(columns=names).round(2), hide_index=True, **_STRETCH_KW)
    with st.expander("Xem bảng chỉ số đầy đủ (Bảng 10.1)"):
        st.dataframe(benchmark.drop(columns=["model", "category"], errors="ignore"), hide_index=True, **_STRETCH_KW)

    st.markdown("#### Thí nghiệm Ablation (S1 → S2A → S3 → S4): Đo giá trị đóng góp của từng thành viên")
    stage_data = table(2).query("category == @category")
    no_charger = table("s2_charger_comparison.csv").query("category == @category and test_subset == 'all'")
    stock = no_charger[["model", "without_charger_mae_vnd"]].rename(columns={"without_charger_mae_vnd": "mae_vnd"}).assign(stage="S2A")
    stages = pd.concat([stage_data.loc[stage_data["stage"].isin(["S1", "S3", "S4"]), ["stage", "model", "mae_vnd"]], stock])
    stages["MAE"] = stages["mae_vnd"] / 1e6
    stages["Mô hình"] = stages["model"].map(MODELS)
    st.altair_chart(
        alt.Chart(stages).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X("stage:N", sort=["S1", "S2A", "S3", "S4"], title="Giai đoạn tích hợp tri thức liên nhóm"),
            y=alt.Y("MAE:Q", scale=alt.Scale(zero=False), title="MAE (triệu đồng)"),
            color=alt.Color("Mô hình:N", scale=alt.Scale(domain=MODEL_ORDER, range=MODEL_COLORS)),
            tooltip=[alt.Tooltip("stage:N", title="Giai đoạn"), "Mô hình:N", alt.Tooltip("MAE:Q", format=".3f")],
        ).properties(height=280),
        **_STRETCH_KW,
    )
    st.caption("S1: Đặc trưng cơ sở · S2A: +Tồn kho & Chuẩn màn hình (TV3) · S3: +Benchmark & Độ phủ sàn (TV4) · S4: +Review cảm xúc (TV6).")

    st.markdown("#### Phân tích độ nhạy lọc ngoại lai TV7 (S5a vs S5b)")
    choice = st.radio(
        "Nguồn cờ kiểm định",
        ["delivered", "train_only"],
        horizontal=True,
        format_func={"delivered": "Cờ TV7 bàn giao", "train_only": "Tính lại độc lập chỉ từ tập Train"}.get,
        key="flag_source",
    )
    sensitivity = table("s5_tv7_sensitivity_details.csv").query(
        "category == @category and flag_source == @choice and test_price_tier == 'all'",
    ).copy()
    sensitivity["model"] = sensitivity["model"].map(MODELS)
    st.altair_chart(
        alt.Chart(sensitivity).mark_bar().encode(
            x=alt.X("stage:N", sort=["S5a", "S5b"], title="Chiến lược lọc trên tập Train"),
            xOffset=alt.XOffset("model:N", sort=MODEL_ORDER),
            y=alt.Y("mae_change_vs_s4_pct:Q", title="Thay đổi MAE so với S4 (%)"),
            color=alt.Color("model:N", title="Mô hình", scale=alt.Scale(domain=MODEL_ORDER, range=MODEL_COLORS)),
            tooltip=[
                alt.Tooltip("stage:N", title="Cách lọc"),
                alt.Tooltip("model:N", title="Mô hình"),
                alt.Tooltip("mae_change_vs_s4_pct:Q", title="MAE thay đổi (%)", format="+.2f"),
            ],
        ).properties(height=230),
        **_STRETCH_KW,
    )
    s5_names = {
        "stage": "Kịch bản",
        "model": "Mô hình",
        "n_train_removed": "Dòng train bị bỏ",
        "n_train_removed_ge_80m": "Số mẫu >=80M bị bỏ",
        "mae_vnd": "MAE (đ)",
        "mae_change_vs_s4_pct": "MAE đổi so với S4 (%)",
    }
    st.dataframe(sensitivity[list(s5_names)].rename(columns=s5_names).round(2), hide_index=True, **_STRETCH_KW)
    with st.expander("Xem Hình 10.3 tổng hợp Ablation & Độ nhạy TV7"):
        show_figure("fig_10_3_ablation_and_sensitivity_chart.png", "Hình 10.3 · Ablation S1–S4 và Độ nhạy lọc cờ TV7")


def _render_error_diagnostics() -> None:
    st.markdown("#### Chẩn đoán sai số đa lát cắt & Đối chiếu cờ TV7")
    a, b = st.columns(2)
    category = a.selectbox("Loại thiết bị", list(CATEGORIES), format_func=CATEGORIES.get, key="error_category")
    key = b.selectbox("Mô hình TV5", list(MODELS), format_func=MODELS.get, key="error_model")
    points = table("test_predictions.csv").query("category == @category and model == @key").copy()
    points["Giá ghi nhận"] = points["recorded_price_vnd"] / 1e6
    points["Sai số"] = points["signed_error_vnd"] / 1e6
    residual = alt.Chart(points).mark_circle(size=28, opacity=0.52, color="#196A9F").encode(
        x=alt.X("Giá ghi nhận:Q", title="Giá ghi nhận thực tế (triệu đồng)"),
        y=alt.Y("Sai số:Q", title="Giá hợp lý dự đoán − Giá ghi nhận (triệu đồng)"),
        tooltip=[
            alt.Tooltip("product_name:N", title="Sản phẩm"),
            alt.Tooltip("Giá ghi nhận:Q", format=".2f"),
            alt.Tooltip("Sai số:Q", format="+.2f"),
        ],
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#536778", strokeDash=[4, 3]).encode(y="y:Q")
    st.altair_chart((residual + zero).properties(height=290), **_STRETCH_KW)

    cuts = pd.concat([table(n) for n in (3, 4, 5, 6)], ignore_index=True).query("category == @category and model == @key")
    dims = cuts["dimension"].unique().tolist()
    dim = st.selectbox("Chiều phân tích sai số", dims, format_func=lambda v: DIMENSIONS.get(v, v), key="slice_dimension")
    slice_data = cuts.loc[cuts["dimension"].eq(dim)].sort_values("n_test", ascending=False).copy()
    slice_data["segment"] = slice_data["segment"].map(lambda v: SEGMENTS.get(v, v)).fillna("Chưa rõ")
    slice_names = {
        "segment": "Nhóm lát cắt",
        "n_test": "Số dòng test",
        "mae_vnd": "MAE (đ)",
        "mape_pct": "MAPE (%)",
        "mean_signed_error_vnd": "Sai lệch có dấu TB (đ)",
    }
    st.dataframe(slice_data[list(slice_names)].rename(columns=slice_names).round(2), hide_index=True, **_STRETCH_KW)

    st.markdown("#### Kiểm toán 20 ca chênh lệch lớn nhất toàn tập kiểm thử (Bảng 10.7)")
    cases = table(7).query("category == @category").copy()
    cases["model"] = cases["model"].map(MODELS)
    cases["anomaly_severity"] = cases["anomaly_severity"].map(SEVERITIES).fillna("Chưa rõ")
    case_names = {
        "rank": "Hạng",
        "product_name": "Sản phẩm",
        "seller_name": "Nhà bán lẻ",
        "model": "Mô hình lệch lớn nhất",
        "recorded_price_vnd": "Giá ghi nhận (đ)",
        "predicted_price_vnd": "Giá hợp lý dự đoán (đ)",
        "absolute_error_vnd": "Độ lệch tuyệt đối (đ)",
        "anomaly_severity": "Cờ TV7",
        "anomaly_reasons": "Lý do gắn cờ",
    }
    st.dataframe(cases[list(case_names)].rename(columns=case_names).round(0), hide_index=True, **_STRETCH_KW)
    with st.expander("Xem Hình 10.1 & Hình 10.2 (300 DPI) trong báo cáo"):
        show_figure("fig_10_1_residual_and_actual_vs_pred.png", "Hình 10.1 · Giá dự đoán và phân phối phần dư")
        show_figure("fig_10_2_error_by_price_tier_and_seller.png", "Hình 10.2 · MAE theo phân khúc giá và nhà bán lẻ")


def _render_global_xai() -> None:
    st.markdown("#### Giải thích mô hình toàn cục (TreeSHAP) & Kiểm thử tính đơn điệu vật lý")
    category = st.selectbox("Loại thiết bị", list(CATEGORIES), format_func=CATEGORIES.get, key="shap_category")
    number = 4 if category == "laptop" else 5
    show_figure(f"fig_10_{number}_shap_summary_{category}.png", f"Hình 10.{number} · Phân phối đóng góp TreeSHAP toàn cục ({CATEGORIES[category]})")
    with st.expander("Xem phân rã SHAP cục bộ trên 3 phân khúc Bình dân – Tầm trung – Cao cấp"):
        show_figure("fig_10_6_shap_waterfall_examples.png", "Hình 10.6 · Giải thích từng dự đoán quy đổi sang triệu đồng")
    st.markdown("#### Kiểm thử tính hợp lý kinh tế học khi tăng RAM & Bộ nhớ (Monotonicity Sanity Check)")
    show_figure("fig_10_7_monotonicity_sanity_check.png", "Hình 10.7 · Phản ứng giá dự đoán khi tăng bậc RAM và Bộ nhớ")
    st.caption(
        "Cảnh báo ngoại suy: Tập huấn luyện điện thoại không có mức RAM 32–64 GB (đánh dấu *). "
        "Mô hình tuyến tính Ridge bị vọt giá phi thực tế khi ngoại suy ngoài miền dữ liệu — lý do Tab 3 khóa chặt ràng buộc tương thích phần cứng."
    )


def validation_xai_tab() -> None:
    st.subheader("Kiểm định Độ tin cậy Công cụ Định giá & Giải thích Mô hình (TV8)")
    section = st.radio(
        "Chọn nội dung thẩm định kỹ thuật",
        ["benchmark_ablation", "error_slices", "global_shap"],
        format_func={
            "benchmark_ablation": "1. Benchmark 3 chiều, Ablation (S1–S4) & Độ nhạy TV7 (S5)",
            "error_slices": "2. Phân tích sai số đa lát cắt & Kiểm toán Top-20 lệch giá",
            "global_shap": "3. Giải thích TreeSHAP toàn cục & Kiểm thử đơn điệu cấu hình",
        }.get,
        horizontal=True,
        key="tv8_subview",
    )
    if section == "benchmark_ablation":
        _render_benchmark_and_ablation()
    elif section == "error_slices":
        _render_error_diagnostics()
    else:
        _render_global_xai()


def main() -> None:
    st.set_page_config(
        page_title="IT4930 · Phân tích Thị trường & Thẩm định Giá Công nghệ Đa sàn",
        layout="wide",
    )
    st.markdown(
        """
        <style>
          :root { --ds-ink:#152C47; --ds-blue:#1E40AF; --ds-line:#DBEAFE; }
          .block-container { max-width: 1320px; padding-top: 2.2rem; padding-bottom: 3rem; }
          .ds-banner { padding: clamp(1.1rem,2.6vw,1.85rem) clamp(1.15rem,2.8vw,2.2rem); margin-bottom: .9rem;
            border: 1px solid var(--ds-line); border-radius: 1rem; color: var(--ds-ink);
            background: linear-gradient(112deg,#EFF6FF,#F8FAFC 60%,#EDF8F7); }
          .ds-banner h1 { font-size: clamp(1.6rem,3.6vw,2.55rem); margin: .25rem 0; padding: 0; color: inherit; }
          .ds-banner p { color: #3B5269; font-size: .98rem; margin: .4rem 0 0; line-height: 1.5; }
          .ds-tag { color: var(--ds-blue); font-size: .78rem; font-weight: 750; letter-spacing: .09em; }
          [role='tab'] { min-height: 44px; padding-inline: .65rem; }
          .stButton button, .stFormSubmitButton button { min-height: 44px; }
          button:focus-visible, [role='tab']:focus-visible { outline: 2px solid var(--ds-blue); outline-offset: 2px; }
          @media (max-width:640px) { .block-container { padding: 1.2rem 1rem 2rem; } }
        </style>
        <section class="ds-banner" aria-label="Nền tảng Khoa học Dữ liệu Thị trường Công nghệ Đa sàn">
          <span class="ds-tag">IT4930 · NHÓM 12 · DATA SCIENCE PLATFORM</span>
          <h1>Phân tích Thị trường & Thẩm định Giá Công nghệ Đa sàn</h1>
          <p>Tích hợp dữ liệu từ 5 hệ thống bán lẻ Việt Nam: Khám phá quy luật định giá (TV3), Đồ thị cạnh tranh &amp; Điểm mù (TV4), Tiếng nói khách hàng NLP (TV6), Kiểm toán bất thường (TV7) và Định giá hợp lý + XAI (TV5 &amp; TV8).</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    renderers = (
        overview_eda_tab,
        market_and_nlp_tab,
        fair_value_tab,
        anomaly_audit_tab,
        validation_xai_tab,
    )
    for tab, render in zip(st.tabs(TAB_LABELS), renderers):
        with tab:
            try:
                render()
            except FileNotFoundError as exc:
                st.error(f"Thiếu tệp dữ liệu: {Path(exc.filename or '').name}. Hãy kiểm tra các tệp đầu ra tương ứng.")


if __name__ == "__main__":
    main()
