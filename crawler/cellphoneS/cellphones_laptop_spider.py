try:
    from crawler.cellphoneS.base_spider import CellphonesBaseSpider
except ImportError:
    from base_spider import CellphonesBaseSpider


class CellphonesLaptopSpider(CellphonesBaseSpider):
    """
    Spider crawl Laptop từ CellphoneS.
    URL nguồn: https://cellphones.com.vn/laptop.html
    GraphQL categoryId: 380
    """

    name = "cellphones_laptop"
    category = "laptop"
    cate_id = "380"
    canonical_url = "https://cellphones.com.vn/laptop.html"
    crawl_reviews = True
