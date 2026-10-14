try:
    from crawler.fptshop.base_spider import FptshopBaseSpider
except ImportError:
    from base_spider import FptshopBaseSpider


class FptshopLaptopSpider(FptshopBaseSpider):
    """
    Spider crawl Laptop (Máy tính xách tay) từ FPT Shop.
    URL nguồn: https://fptshop.com.vn/may-tinh-xach-tay
    """

    name = "fptshop_laptop"
    category = "laptop"
    slug = "may-tinh-xach-tay"
    crawl_reviews = True
