try:
    from crawler.tgdd.base_spider import TgddBaseSpider
except ImportError:
    from base_spider import TgddBaseSpider


class TgddSmartphoneSpider(TgddBaseSpider):
    """
    Spider crawl Smartphone (Điện thoại) từ Thế Giới Di Động (TGDĐ).
    URL nguồn: https://www.thegioididong.com/dtdd
    """

    name = "tgdd_smartphone"
    category = "smartphone"
    url_cate = "dtdd"
    cate_id = "42"
    referer = "https://www.thegioididong.com/dtdd"
    crawl_reviews = True
