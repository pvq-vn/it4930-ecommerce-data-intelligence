try:
    from crawler.cellphoneS.base_spider import CellphonesBaseSpider
except ImportError:
    from base_spider import CellphonesBaseSpider


class CellphonesSmartphoneSpider(CellphonesBaseSpider):
    """
    Spider crawl Smartphone (Điện thoại) từ CellphoneS.
    URL nguồn: https://cellphones.com.vn/mobile.html
    GraphQL categoryId: 3
    """

    name = "cellphones_smartphone"
    category = "smartphone"
    cate_id = "3"
    canonical_url = "https://cellphones.com.vn/mobile.html"
    crawl_reviews = True
