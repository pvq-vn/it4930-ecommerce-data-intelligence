try:
    from crawler.viettelStore.base_spider import ViettelstoreBaseSpider
except ImportError:
    from base_spider import ViettelstoreBaseSpider


class ViettelstoreSmartphoneSpider(ViettelstoreBaseSpider):
    """
    Spider crawl Smartphone (Điện thoại) từ Viettel Store.
    URL nguồn: https://viettelstore.vn/dien-thoai
    CatID: '010001'
    """

    name = "viettelstore_smartphone"
    category = "smartphone"
    cat_id = "010001"
    start_url = "https://viettelstore.vn/dien-thoai"
