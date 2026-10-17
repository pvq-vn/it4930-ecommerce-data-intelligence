try:
    from crawler.viettelStore.base_spider import ViettelstoreBaseSpider
except ImportError:
    from base_spider import ViettelstoreBaseSpider


class ViettelstoreLaptopSpider(ViettelstoreBaseSpider):
    """
    Spider crawl Laptop từ Viettel Store.
    URL nguồn: https://viettelstore.vn/laptop
    CatID: '010002'
    """

    name = "viettelstore_laptop"
    category = "laptop"
    cat_id = "010002"
    start_url = "https://viettelstore.vn/laptop"
