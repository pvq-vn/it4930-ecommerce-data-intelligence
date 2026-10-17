try:
    from crawler.hoanghamobile.base_spider import HoanghamobileBaseSpider
except ImportError:
    from base_spider import HoanghamobileBaseSpider


class HoanghamobileLaptopSpider(HoanghamobileBaseSpider):
    """
    Spider crawl Laptop từ Hoàng Hà Mobile.
    URL nguồn: https://hoanghamobile.com/laptop
    Category slug: 'laptop'
    """

    name = "hoanghamobile_laptop"
    category = "laptop"
    slug = "laptop"
    canonical_url = "https://hoanghamobile.com/laptop"
