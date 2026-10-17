try:
    from crawler.hoanghamobile.base_spider import HoanghamobileBaseSpider
except ImportError:
    from base_spider import HoanghamobileBaseSpider


class HoanghamobileSmartphoneSpider(HoanghamobileBaseSpider):
    """
    Spider crawl Smartphone (Điện thoại) từ Hoàng Hà Mobile.
    URL nguồn: https://hoanghamobile.com/dien-thoai-di-dong
    Category slug: 'dien-thoai-di-dong'
    """

    name = "hoanghamobile_smartphone"
    category = "smartphone"
    slug = "dien-thoai-di-dong"
    canonical_url = "https://hoanghamobile.com/dien-thoai-di-dong"
