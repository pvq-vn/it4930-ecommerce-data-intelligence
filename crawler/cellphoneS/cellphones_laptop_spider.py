"""
Alias module for CellphonesLaptopSpider.
"""
try:
    from crawler.cellphoneS.cellphone_laptop_spider import CellphonesLaptopSpider
except ImportError:
    from cellphone_laptop_spider import CellphonesLaptopSpider

__all__ = ["CellphonesLaptopSpider"]
