"""
CellphoneS items re-exporting the canonical raw contract items.
CellphoneS, TGDĐ và FPTShop đều sử dụng chung một schema và semantic contract logic.
"""

try:
    from crawler.tgdd.items import TechProductRawItem, TechReviewRawItem
except ImportError:
    from items import TechProductRawItem, TechReviewRawItem

__all__ = ["TechProductRawItem", "TechReviewRawItem"]
