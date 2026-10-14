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

    # Identifiers & URLs (Product / Variant level)
    product_id_raw = scrapy.Field()
    product_url_raw = scrapy.Field()
    product_name_raw = scrapy.Field()

    # Parent ProductGroup Hierarchy
    parent_product_id_raw = scrapy.Field()
    parent_product_name_raw = scrapy.Field()
    parent_url_raw = scrapy.Field()

    # Variant & Configuration Specifics
    variant_name_raw = scrapy.Field()
    variant_color_raw = scrapy.Field()
    variant_url_raw = scrapy.Field()
    variant_sku_raw = scrapy.Field()
    availability_raw = scrapy.Field()

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
    raw_payload = scrapy.Field()


class TechReviewRawItem(scrapy.Item):
    """
    Raw review/comment record của TV1 (Web Crawling & Data Acquisition).
    Thu thập và bảo toàn dữ liệu đánh giá/bình luận người dùng từ TGDĐ.
    Bảo toàn toàn bộ raw data, không normalize, không sentiment analysis, không NLP.
    """

    # Provenance & Metadata
    source = scrapy.Field()
    category = scrapy.Field()
    crawl_batch = scrapy.Field()
    crawl_time = scrapy.Field()

    # Linkage to Parent Product
    parent_product_id_raw = scrapy.Field()
    parent_product_url_raw = scrapy.Field()

    # Review Specifics
    review_id_raw = scrapy.Field()
    rating_raw = scrapy.Field()
    review_text_raw = scrapy.Field()
    author_raw = scrapy.Field()
    review_time_raw = scrapy.Field()
    like_count_raw = scrapy.Field()

    # Variant Linkage & Raw Product Identifiers from Source
    review_product_code_raw = scrapy.Field()
    variant_code_raw = scrapy.Field()
    variant_sku_raw = scrapy.Field()

    # Additional Raw Attributes from Source
    buy_date_raw = scrapy.Field()
    reply_raw = scrapy.Field()
    attached_files_raw = scrapy.Field()
    raw_payload = scrapy.Field()

