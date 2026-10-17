"""
Viettel Store items re-exporting the canonical raw contract items.
Mọi nguồn crawler (TGDĐ, FPTShop, CellphoneS, Viettel Store, Hoàng Hà Mobile)
đều sử dụng chung một schema và semantic contract logic.
"""

try:
    from crawler.tgdd.items import TechProductRawItem, TechReviewRawItem
except ImportError:
    try:
        from tgdd.items import TechProductRawItem, TechReviewRawItem
    except ImportError:
        import importlib.util
        from pathlib import Path
        _tgdd_items_path = Path(__file__).resolve().parent.parent / "tgdd" / "items.py"
        _spec = importlib.util.spec_from_file_location("crawler.tgdd.items", _tgdd_items_path)
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            TechProductRawItem = _mod.TechProductRawItem
            TechReviewRawItem = _mod.TechReviewRawItem
        else:
            raise

__all__ = ["TechProductRawItem", "TechReviewRawItem"]
