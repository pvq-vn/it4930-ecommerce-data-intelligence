try:
    from crawler.tgdd.base_spider import TgddBaseSpider
except ImportError:
    from base_spider import TgddBaseSpider


class TgddLaptopSpider(TgddBaseSpider):
    """
    Spider crawl Laptop từ Thế Giới Di Động (TGDĐ).
    URL nguồn: https://www.thegioididong.com/laptop
    """

    name = "tgdd_laptop"
    category = "laptop"
    url_cate = "laptop"
    cate_id = "17"
    referer = "https://www.thegioididong.com/laptop"
    crawl_reviews = True