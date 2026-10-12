import scrapy


class TechProductRawItem(scrapy.Item):
    """
    Raw record của TV1 (Web Crawling & Data Acquisition).
    Chỉ thu thập và bảo toàn dữ liệu gốc, không thực hiện normalize hay clean semantic.
    """

    # Provenance & Metadata
    source = scrapy.Field()
    category = scrapy.Field()
    crawl_batch = scrapy.Field()
    crawl_time = scrapy.Field()

    # Identifiers & URLs
    product_id_raw = scrapy.Field()
    product_url_raw = scrapy.Field()
    product_name_raw = scrapy.Field()

    # Pricing (bảo toàn kiểu dữ liệu gốc, không chuẩn hóa chuỗi)
    price_raw = scrapy.Field()
    original_price_raw = scrapy.Field()

    # Seller & Reputation
    seller_raw = scrapy.Field()
    rating_raw = scrapy.Field()
    review_count_raw = scrapy.Field()

    # Technical Specifications (dictionary key-value gốc)
    attributes_raw = scrapy.Field()

    # Useful Raw Extensions
    brand_raw = scrapy.Field()
    total_sold_raw = scrapy.Field()
    sku_raw = scrapy.Field()
