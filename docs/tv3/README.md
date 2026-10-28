# Tài liệu Thành viên 3 (TV3 - Exploratory Data Analysis)

Hệ thống tài liệu hướng dẫn và sản phẩm bàn giao của TV3:
1. **[tv3.md](tv3.md)**: Hướng dẫn nhiệm vụ chi tiết và kế hoạch triển khai.
2. **[tv3_to_tv5_handoff.md](tv3_to_tv5_handoff.md)**: Tài liệu bàn giao kỹ thuật chính thức cho TV5 (Price Prediction Modeling).
3. **[report_section_5_eda.md](report_section_5_eda.md)**: Bản thảo hoàn chỉnh Phần 5 Báo cáo Tổng kết Học phần (EDA).

---

## Tái lập Thực nghiệm Độc lập (1-Click Reproducibility)

Toàn bộ 36 bảng Markdown (`src/eda/outputs/tables/`), 15 biểu đồ chuẩn xuất bản 300 DPI (`src/eda/outputs/figures/`), và 5 Jupyter Notebooks (`src/eda/notebooks/`) có thể được tái lập độc lập 100% từ dữ liệu sạch `data/processed/products_processed.jsonl`:

```bash
# Cài đặt phụ thuộc:
pip install -r ../../requirements.txt -r ../../requirements-eda.txt

# 1. Tái lập toàn bộ bảng biểu và biểu đồ tự động (mất ~45s):
python ../../src/eda/scripts/reproduce_all.py

# 2. Hoặc tái lập đồng thời thực thi và cập nhật output cho cả 5 Notebooks:
python ../../src/eda/scripts/reproduce_all.py --execute-notebooks
```

