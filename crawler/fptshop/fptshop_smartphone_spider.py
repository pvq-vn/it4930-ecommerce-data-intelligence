try:
    from crawler.fptshop.base_spider import FptshopBaseSpider
except ImportError:
    from base_spider import FptshopBaseSpider


class FptshopSmartphoneSpider(FptshopBaseSpider):
    """
    Spider crawl Smartphone (Điện thoại) từ FPT Shop.
    URL nguồn: https://fptshop.com.vn/dien-thoai
    """

    name = "fptshop_smartphone"
    category = "smartphone"
    slug = "dien-thoai"
    crawl_reviews = True
