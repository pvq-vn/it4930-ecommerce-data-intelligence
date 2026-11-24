"""Local TV8 demo. Run from the repository root with Streamlit."""

from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from demo_data import (
    build_catalog, load_demo_data, load_demo_model, local_explanation,
    prediction_frame, similar_listings,
)


OUTPUT = Path(__file__).resolve().parent / "outputs"
CATEGORIES = {"laptop": "Laptop", "smartphone": "Điện thoại"}
MODELS = {"lgbm": "LightGBM", "rf": "Random Forest", "ridge": "Ridge"}
MODEL_ORDER = ["Ridge", "Random Forest", "LightGBM"]
MODEL_COLORS = ["#196A9F", "#CE572E", "#008778"]
TABLES = {
    1: "table_10_1_model_benchmark_3d.csv", 2: "table_10_2_ablation_and_tv7_sensitivity.csv",
    3: "table_10_3_error_by_price_tier.csv", 4: "table_10_4_error_by_brand_and_seller.csv",
    5: "table_10_5_error_by_stock_and_missingness.csv", 6: "table_10_6_cross_store_generalization.csv",
    7: "table_10_7_top20_worst_predictions_audit.csv",
}
DIMENSIONS = {
    "price_tier": "Khoảng giá", "brand": "Thương hiệu", "seller_name": "Nhà bán lẻ",
    "availability_status": "Tồn kho", "ram_status": "Thông tin RAM", "cross_store_group": "Độ phủ cửa hàng",
}
SEGMENTS = {
    "under_10m": "Dưới 10 triệu", "10m_to_under_20m": "10 đến dưới 20 triệu",
    "20m_to_35m": "20 đến 35 triệu", "over_35m": "Trên 35 triệu",
    "in_stock": "Còn hàng", "out_of_stock": "Hết hàng", "unknown": "Chưa rõ",
    "missing": "Thiếu", "present": "Có dữ liệu", "missing_configuration": "Thiếu cấu hình",
    "seen_other_store": "Đã thấy ở cửa hàng khác", "seen_same_store_only": "Chỉ thấy ở cùng cửa hàng",
    "unseen_configuration": "Cấu hình chưa thấy", "unknown_seller": "Chưa rõ cửa hàng",
}
SEVERITIES = {"none": "Không có cờ", "review": "Cần kiểm tra", "extreme": "Cực đoan"}


def money(vnd):
    return f"{vnd:,.0f}".replace(",", ".") + " đ"


@st.cache_resource(show_spinner="Đang đọc dữ liệu thiết bị…")
def splits_for_demo():
    return load_demo_data()


@st.cache_resource(show_spinner=False, max_entries=6)
def cached_model(category, key):
    return load_demo_model(category, key)


@st.cache_data(show_spinner=False)
def catalog_for_demo():
    return build_catalog(splits=splits_for_demo())


@st.cache_data(show_spinner=False)
def read_table(filename, modified_ns):
    # Including file mtime refreshes the app when experiments are rerun locally.
    return pd.read_csv(OUTPUT / "tables" / filename)


def table(which):
    filename = TABLES[which] if isinstance(which, int) else which
    path = OUTPUT / "tables" / filename
    return read_table(filename, path.stat().st_mtime_ns)


def show_figure(filename, caption):
    path = OUTPUT / "figures" / filename
    if path.exists():
        st.image(str(path), caption=caption, use_container_width=True)
    else:
        st.caption(f"Chưa xuất {caption}.")


def preferred(values, desired):
    for i, value in enumerate(values):
        if isinstance(value, str) and isinstance(desired, str) and value.casefold() == desired.casefold():
            return i
    return 0


def choices(series):
    values = {v for v in series.dropna().unique() if isinstance(v, str) and v.strip()}
    return sorted(values - {"unknown", "Unknown"}, key=str.casefold)


def example_row(train, brand, device):
    pool = train.loc[train["brand"].eq(brand) & train["model_clean"].eq(device)]
    if pool.empty:
        return {}
    if brand.casefold() == "apple" and device.casefold() == "iphone 15 pro max":
        # Keep the known example easy to reproduce while offering every reference choice.
        rank = pool["seller_name"].str.casefold().eq("fpt").astype(int) * 2 + pool["storage_gb"].eq(256).astype(int)
        pool = pool.loc[[rank.idxmax()]]
    else:
        present = pool[["ram_gb", "storage_gb", "screen_size_inch", "cpu_model"]].notna().sum(axis=1)
        pool = pool.loc[[present.idxmax()]]
    return pool.iloc[0].to_dict()


def measure_input(label, field, sample, low, high, step=1, **kwargs):
    raw = sample.get(field)
    default = None
    if pd.notna(raw) and low <= float(raw) <= high:
        default = int(raw) if isinstance(step, int) else float(raw)
    return st.number_input(label, min_value=low, max_value=high, value=default, step=step, **kwargs)


def pick_input(label, train, field, sample, key):
    options = [None, *choices(train[field])]
    return st.selectbox(label, options, index=preferred(options, sample.get(field)),
                        format_func=lambda value: "Không rõ" if value is None else value, key=key)


def plot_contributions(contribution):
    ordered = contribution.assign(magnitude=contribution["delta_vnd"].abs()).sort_values("magnitude", ascending=False)
    top = ordered.head(6)[["label", "delta_vnd"]].reset_index(drop=True)
    if len(ordered) > len(top):
        top.loc[len(top)] = ["Các yếu tố còn lại", ordered.iloc[len(top):]["delta_vnd"].sum()]
    top["Triệu đồng"] = top["delta_vnd"] / 1e6
    top["Hướng"] = np.where(top["delta_vnd"].ge(0), "Tăng", "Giảm")
    top["Đóng góp"] = top["delta_vnd"].map(lambda amount: ("+" if amount >= 0 else "−") + money(abs(amount)))
    chart = alt.Chart(top).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("Triệu đồng:Q", title="Đóng góp (triệu đồng)"),
        y=alt.Y("label:N", sort=top["label"].tolist(), title=None, axis=alt.Axis(labelLimit=165)),
        color=alt.Color("Hướng:N", scale=alt.Scale(domain=["Tăng", "Giảm"], range=["#C54F2C", "#196A9F"]), legend=None),
        tooltip=[alt.Tooltip("label:N", title="Yếu tố"), alt.Tooltip("Đóng góp:N")],
    ).properties(height=230)
    st.altair_chart(chart, use_container_width=True)


def prediction_tab():
    st.subheader("Ước lượng giá từ cấu hình")
    st.caption("Dự đoán giá niêm yết trong đợt thu thập bằng mô hình gốc của TV5.")
    try:
        splits = splits_for_demo()
    except (OSError, ValueError, SystemExit) as exc:
        st.error(f"Chưa đọc được dữ liệu dự đoán. {exc}")
        return
    category_control, model_control = st.columns(2)
    category = category_control.selectbox("Loại thiết bị", list(CATEGORIES), index=1, format_func=CATEGORIES.get, key="prediction_category")
    key = model_control.selectbox("Mô hình dự đoán", list(MODELS), format_func=MODELS.get, key="prediction_model")
    split = splits[category]
    train = split.X_train
    entry, outcome = st.columns([1.05, 1], gap="large")
    with entry:
        brand_options = choices(train["brand"])
        brand = st.selectbox("Thương hiệu", brand_options, index=preferred(brand_options, "Apple" if category == "smartphone" else "Asus"), key=f"brand_{category}")
        device_options = choices(train.loc[train["brand"].eq(brand), "model_clean"])
        device = st.selectbox("Dòng máy", device_options, index=preferred(device_options, "iPhone 15 Pro Max"), key=f"device_{category}_{brand}")
        sample = example_row(train, brand, device) if device else {}
        form_key = f"configuration_{category}_{brand}_{device}"
        with st.form(form_key):
            a, b = st.columns(2)
            with a:
                seller = pick_input("Nhà bán lẻ", train, "seller_name", sample, f"{form_key}_seller")
                ram_max = 24 if category == "smartphone" else 128
                ram = measure_input("RAM (GB)", "ram_gb", sample, 2, ram_max, help="Có thể để trống nếu không biết.")
                pin_field = "battery_wh" if category == "laptop" else "battery_mah"
                pin_label = "Pin (Wh)" if category == "laptop" else "Pin (mAh)"
                pin = measure_input(pin_label, pin_field, sample, 1.0, 200.0, step=0.1) if category == "laptop" else measure_input(pin_label, pin_field, sample, 1, 20_000)
            with b:
                cpu = pick_input("CPU", train, "cpu_model", sample, f"{form_key}_cpu")
                storage = measure_input("Bộ nhớ (GB)", "storage_gb", sample, 32, 4096, help="Có thể để trống nếu không biết.")
                bounds = (10.0, 18.5) if category == "laptop" else (4.0, 8.5)
                screen = measure_input("Màn hình (inch)", "screen_size_inch", sample, *bounds, step=0.1)
            product = {
                "brand": brand, "model_clean": device, "seller_name": seller, "cpu_model": cpu,
                "ram_gb": ram, "storage_gb": storage, "screen_size_inch": screen, pin_field: pin,
            }
            if category == "laptop":
                product["gpu_model"] = pick_input("GPU", train, "gpu_model", sample, f"{form_key}_gpu")
            else:
                a, b = st.columns(2)
                with a:
                    product["display_type_norm"] = pick_input("Loại màn hình", train, "display_type_norm", sample, f"{form_key}_display")
                    product["camera_mp"] = measure_input("Camera chính (MP)", "camera_mp", sample, 1, 250)
                with b:
                    network = train.loc[~train["network_type_norm"].fillna("").str.contains(r"\d[,.]\d{3}|vnđ|vnd", case=False)]
                    product["network_type_norm"] = pick_input("Mạng", network, "network_type_norm", sample, f"{form_key}_network")
            submitted = st.form_submit_button("Dự đoán giá", type="primary", use_container_width=True, disabled=device is None)
    request = (category, key, brand, device)
    with outcome:
        if submitted:
            st.session_state.pop("prediction_result", None)
            with st.spinner("Đang tính giá dự đoán…"):
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
                st.subheader("Giá dự đoán")
                st.write("Chọn cấu hình rồi bấm **Dự đoán giá** để xem mức ước lượng và các yếu tố đóng góp.")
            return
        _, used, price, base, contributions, explanation_error = result
        with st.container(border=True):
            st.metric("Giá dự đoán", money(price))
            row = table(1).query("category == @category and model == @key")
            if not row.empty:
                typical = float(row.iloc[0]["mdape_pct"]) / 100
                st.write(f"**Dải tham chiếu:** {money(max(0, price * (1-typical)))} đến {money(price * (1+typical))}")
                st.caption(f"Dùng sai số phần trăm trung vị trên test ({typical:.1%}). Dải này không có mức bảo đảm xác suất.")
        unsupported = [
            label for field, label in (("ram_gb", "RAM"), ("storage_gb", "bộ nhớ"))
            if used[field] is not None and not train[field].eq(used[field]).any()
        ]
        if unsupported:
            st.warning(f"Tập huấn luyện chưa có chính xác mức {' và '.join(unsupported)} đã nhập. Giá có thể kém ổn định.")
        st.subheader("Yếu tố kéo giá lên hoặc xuống")
        if explanation_error:
            st.caption(f"Chưa hiển thị được giải thích cho mô hình này. {explanation_error}")
        else:
            st.caption(f"Mô hình bắt đầu từ mức nền {money(base)}. Cộng các đóng góp sẽ ra giá dự đoán.")
            if key == "rf" and contributions.attrs.get("approximated"):
                st.caption("Đóng góp được ước tính bằng cách thử 128 thứ tự thay đổi đặc trưng.")
            plot_contributions(contributions)
    st.subheader("Sản phẩm tương tự trong dữ liệu")
    st.caption("Mỗi cửa hàng hiển thị một dòng cho mỗi cấu hình phần cứng.")
    examples = similar_listings(catalog_for_demo(), category, used)
    display = examples[["product_name", "seller_name", "ram_gb", "storage_gb", "price_vnd", "anomaly_severity"]].copy()
    display["price_vnd"] = display["price_vnd"].map(money)
    display["anomaly_severity"] = display["anomaly_severity"].map(SEVERITIES).fillna("Chưa có cờ đối chiếu")
    st.dataframe(display.rename(columns={
        "product_name": "Sản phẩm", "seller_name": "Nhà bán lẻ", "ram_gb": "RAM (GB)",
        "storage_gb": "Bộ nhớ (GB)", "price_vnd": "Giá ghi nhận", "anomaly_severity": "Cờ TV7",
    }), hide_index=True, use_container_width=True)


def benchmark_tab():
    st.subheader("Mỗi mô hình mạnh ở điểm nào?")
    category = st.selectbox("Loại thiết bị", list(CATEGORIES), format_func=CATEGORIES.get, key="benchmark_category")
    benchmark = table(1).query("category == @category").copy()
    benchmark["Mô hình"] = benchmark["model"].map(MODELS)
    names = {
        "mae_vnd": "MAE (đ)", "rmse_vnd": "RMSE (đ)", "mdape_pct": "MdAPE (%)", "r2": "R²",
        "latency_ms_per_sample": "Thời gian (ms/mẫu)", "model_size_mb": "Tệp (MB)",
        "mae_change_pct": "MAE tăng khi thiếu RAM/bộ nhớ (%)",
    }
    st.caption("Mô hình TV5 gốc · Cùng tập test · Thời gian đo trên máy chạy đánh giá.")
    st.dataframe(benchmark[["Mô hình", *names]].rename(columns=names).round(2), hide_index=True, use_container_width=True)
    with st.expander("Xem các chỉ số đầy đủ"):
        st.dataframe(benchmark.drop(columns=["model", "category"], errors="ignore"), hide_index=True, use_container_width=True)

    st.subheader("Đóng góp của các nhóm đặc trưng")
    stage_data = table(2).query("category == @category")
    no_charger = table("s2_charger_comparison.csv").query("category == @category and test_subset == 'all'")
    stock = no_charger[["model", "without_charger_mae_vnd"]].rename(columns={"without_charger_mae_vnd": "mae_vnd"}).assign(stage="S2A")
    stages = pd.concat([stage_data.loc[stage_data["stage"].isin(["S1", "S3", "S4"]), ["stage", "model", "mae_vnd"]], stock])
    stages["MAE"] = stages["mae_vnd"] / 1e6
    stages["Mô hình"] = stages["model"].map(MODELS)
    st.altair_chart(alt.Chart(stages).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X("stage:N", sort=["S1", "S2A", "S3", "S4"], title="Giai đoạn"),
        y=alt.Y("MAE:Q", scale=alt.Scale(zero=False), title="MAE (triệu đồng)"),
        color=alt.Color("Mô hình:N", scale=alt.Scale(domain=MODEL_ORDER, range=MODEL_COLORS)),
        tooltip=[alt.Tooltip("stage:N", title="Giai đoạn"), "Mô hình:N", alt.Tooltip("MAE:Q", format=".3f")],
    ).properties(height=280), use_container_width=True)
    st.caption("S1 dùng đặc trưng TV5 · S2A thêm tồn kho và sửa lỗi màn hình · S3 thêm đặc trưng TV4 · S4 thêm review TV6.")

    st.subheader("Ảnh hưởng của việc lọc cờ TV7")
    choice = st.radio("Nguồn cờ", ["delivered", "train_only"], horizontal=True,
                      format_func={"delivered": "Cờ TV7 bàn giao", "train_only": "Tính lại chỉ từ train"}.get, key="flag_source")
    sensitivity = table("s5_tv7_sensitivity_details.csv").query(
        "category == @category and flag_source == @choice and test_price_tier == 'all'",
    ).copy()
    sensitivity["model"] = sensitivity["model"].map(MODELS)
    st.altair_chart(alt.Chart(sensitivity).mark_bar().encode(
        x=alt.X("stage:N", sort=["S5a", "S5b"], title="Cách lọc"),
        xOffset=alt.XOffset("model:N", sort=MODEL_ORDER),
        y=alt.Y("mae_change_vs_s4_pct:Q", title="MAE đổi so với S4 (%)"),
        color=alt.Color("model:N", title="Mô hình", scale=alt.Scale(domain=MODEL_ORDER, range=MODEL_COLORS)),
        tooltip=[alt.Tooltip("stage:N", title="Cách lọc"), alt.Tooltip("model:N", title="Mô hình"),
                 alt.Tooltip("mae_change_vs_s4_pct:Q", title="MAE thay đổi (%)", format="+.2f")],
    ).properties(height=230), use_container_width=True)
    names = {"stage": "Giai đoạn", "model": "Mô hình", "n_train_removed": "Dòng train bị bỏ",
             "n_train_removed_ge_80m": "Dòng bị bỏ từ 80 triệu", "mae_vnd": "MAE (đ)", "mae_change_vs_s4_pct": "MAE đổi so với S4 (%)"}
    st.dataframe(sensitivity[list(names)].rename(columns=names).round(2), hide_index=True, use_container_width=True)
    st.caption("S5a bỏ nhóm extreme · S5b bỏ tất cả dòng có cờ · Cả hai chấm trên tập test của S4.")


def diagnostics_tab():
    st.subheader("Mô hình thường sai ở đâu?")
    a, b = st.columns(2)
    category = a.selectbox("Loại thiết bị", list(CATEGORIES), format_func=CATEGORIES.get, key="error_category")
    key = b.selectbox("Mô hình TV5", list(MODELS), format_func=MODELS.get, key="error_model")
    points = table("test_predictions.csv").query("category == @category and model == @key").copy()
    points["Giá ghi nhận"] = points["recorded_price_vnd"] / 1e6
    points["Sai số"] = points["signed_error_vnd"] / 1e6
    residual = alt.Chart(points).mark_circle(size=28, opacity=0.52, color="#196A9F").encode(
        x=alt.X("Giá ghi nhận:Q", title="Giá ghi nhận (triệu đồng)"),
        y=alt.Y("Sai số:Q", title="Dự đoán trừ giá ghi nhận (triệu đồng)"),
        tooltip=[alt.Tooltip("product_name:N", title="Sản phẩm"), alt.Tooltip("Giá ghi nhận:Q", format=".2f"), alt.Tooltip("Sai số:Q", format="+.2f")],
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#536778", strokeDash=[4, 3]).encode(y="y:Q")
    st.altair_chart((residual + zero).properties(height=290), use_container_width=True)
    st.caption("Các điểm trên đường 0 là dự đoán cao hơn giá ghi nhận. Mỗi điểm là một dòng test.")

    st.subheader("So sánh sai số theo nhóm")
    cuts = pd.concat([table(n) for n in (3, 4, 5, 6)], ignore_index=True).query("category == @category and model == @key")
    dims = cuts["dimension"].unique().tolist()
    dim = st.selectbox("Cách nhóm", dims, format_func=lambda value: DIMENSIONS.get(value, value), key="slice_dimension")
    slice_data = cuts.loc[cuts["dimension"].eq(dim)].sort_values("n_test", ascending=False).copy()
    slice_data["segment"] = slice_data["segment"].map(lambda value: SEGMENTS.get(value, value)).fillna("Chưa rõ")
    names = {"segment": "Nhóm", "n_test": "Số dòng test", "mae_vnd": "MAE (đ)",
             "mape_pct": "MAPE (%)", "mean_signed_error_vnd": "Sai lệch trung bình (đ)"}
    st.dataframe(slice_data[list(names)].rename(columns=names).round(2), hide_index=True, use_container_width=True)

    st.subheader("Ca dự đoán lệch nhiều nhất")
    cases = table(7).query("category == @category").copy()
    cases["model"] = cases["model"].map(MODELS)
    cases["anomaly_severity"] = cases["anomaly_severity"].map(SEVERITIES).fillna("Chưa rõ")
    names = {"rank": "Hạng", "product_name": "Sản phẩm", "seller_name": "Nhà bán lẻ", "model": "Mô hình",
             "recorded_price_vnd": "Giá ghi nhận (đ)", "predicted_price_vnd": "Giá dự đoán (đ)",
             "absolute_error_vnd": "Độ lệch (đ)", "anomaly_severity": "Cờ TV7", "anomaly_reasons": "Lý do gắn cờ"}
    st.caption("Lọc theo loại thiết bị trong 20 dòng sai nhất toàn tập. Mỗi dòng hiển thị mô hình sai nhiều nhất ở dòng đó.")
    st.dataframe(cases[list(names)].rename(columns=names).round(0), hide_index=True, use_container_width=True)
    with st.expander("Biểu đồ sai số trong báo cáo"):
        show_figure("fig_10_1_residual_and_actual_vs_pred.png", "Hình 10.1 · Giá dự đoán và sai số")
        show_figure("fig_10_2_error_by_price_tier_and_seller.png", "Hình 10.2 · Sai số theo nhóm")


def explanations_tab():
    st.subheader("Mô hình S4 dùng thông tin nào?")
    category = st.selectbox("Loại thiết bị", list(CATEGORIES), format_func=CATEGORIES.get, key="shap_category")
    number = 4 if category == "laptop" else 5
    show_figure(f"fig_10_{number}_shap_summary_{category}.png", f"Hình 10.{number} · SHAP của LightGBM S4")
    with st.expander("Xem SHAP cho ba dự đoán cụ thể"):
        show_figure("fig_10_6_shap_waterfall_examples.png", "Hình 10.6 · Đóng góp theo triệu đồng")
    st.subheader("Khi tăng RAM hoặc bộ nhớ")
    show_figure("fig_10_7_monotonicity_sanity_check.png", "Hình 10.7 · Giá dự đoán trên hai cấu hình tham chiếu")
    st.caption("Tập train điện thoại thiếu 32 và 64 GB RAM. Các mức đánh dấu * trên hình là phép thử ngoài dữ liệu.")


def main():
    st.set_page_config(page_title="TV8 · Dự đoán giá thiết bị", layout="wide")
    st.markdown("""
        <style>
          :root { --tv8-ink:#152C47; --tv8-blue:#1E40AF; --tv8-line:#DBEAFE; }
          .block-container { max-width: 1280px; padding-top: 2.5rem; padding-bottom: 3rem; }
          .tv8-intro { padding: clamp(1.15rem,3vw,2rem) clamp(1.15rem,3vw,2.2rem); margin-bottom: .85rem;
            border: 1px solid var(--tv8-line); border-radius: 1rem; color:var(--tv8-ink);
            background: linear-gradient(112deg,#EFF6FF,#F8FAFC 60%,#EDF8F7); }
          .tv8-intro h1 { font-size: clamp(1.7rem,4.5vw,3rem); margin: .2rem 0; padding: 0; color:inherit; }
          .tv8-intro p { color:#3B5269; font-size:1rem; margin:.45rem 0 0; }
          .tv8-tag { color:var(--tv8-blue); font-size:.78rem; font-weight:750; letter-spacing:.09em; }
          [role='tab'] { min-height: 44px; padding-inline:.65rem; }
          .stButton button, .stFormSubmitButton button { min-height: 44px; }
          button:focus-visible, [role='tab']:focus-visible { outline: 2px solid var(--tv8-blue); outline-offset: 2px; }
          @media (max-width:640px) { .block-container { padding:1.35rem 1rem 2rem; } }
        </style>
        <section class="tv8-intro" aria-label="Đánh giá mô hình giá thiết bị">
          <span class="tv8-tag">IT4930 · THÀNH VIÊN 8</span>
          <h1>Dự đoán giá thiết bị</h1>
          <p>Khám phá giá laptop và điện thoại qua cấu hình, kết quả đánh giá và giải thích mô hình.</p>
        </section>
    """, unsafe_allow_html=True)
    for tab, render in zip(
        st.tabs(["Dự đoán giá", "So sánh mô hình", "Phân tích sai số", "Giải thích mô hình"]),
        (prediction_tab, benchmark_tab, diagnostics_tab, explanations_tab),
    ):
        with tab:
            try:
                render()
            except FileNotFoundError as exc:
                st.error(f"Thiếu tệp kết quả: {Path(exc.filename or '').name}. Hãy chạy bước đánh giá tương ứng.")


if __name__ == "__main__":
    main()
