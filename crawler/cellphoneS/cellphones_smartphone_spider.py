"""
Alias module for CellphonesSmartphoneSpider.
"""
try:
    from crawler.cellphoneS.cellphone_smartphone_spider import CellphonesSmartphoneSpider
except ImportError:
    from cellphone_smartphone_spider import CellphonesSmartphoneSpider

__all__ = ["CellphonesSmartphoneSpider"]
