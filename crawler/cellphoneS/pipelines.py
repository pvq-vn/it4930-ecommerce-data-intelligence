import json
import logging
from pathlib import Path
from typing import Optional

from scrapy.exceptions import DropItem

try:
    from crawler.cellphoneS.items import TechReviewRawItem
except ImportError:
    from items import TechReviewRawItem


class CellphonesReviewExportPipeline:
    """
    Pipeline xuất TechReviewRawItem cho CellphoneS ra file JSONL riêng biệt.
    Đảm bảo:
    - Product/variant records không bị trộn với review records.
    - Cùng batch_id để bảo toàn provenance liên kết giữa product và review.
    - Immutable snapshot: bảo toàn snapshot cũ, ghi ra thư mục data/raw/cellphoneS/{category}_reviews/
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.file = None
        self.review_output_path: Optional[Path] = None
        self.reviews_written = 0

    def open_spider(self, spider):
        rev_out = getattr(spider, "review_output", None)
        if rev_out:
            self.review_output_path = Path(rev_out)
        else:
            project_root = Path(__file__).resolve().parent.parent.parent
            category = getattr(spider, "category", "general")
            batch_id = getattr(spider, "batch_id", "default_batch")
            self.review_output_path = (
                project_root / "data" / "raw" / "cellphoneS" / f"{category}_reviews" / f"{batch_id}.jsonl"
            )

        self.review_output_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.review_output_path, "a", encoding="utf-8")
        self.logger.info("CellphonesReviewExportPipeline mở file review snapshot: %s", self.review_output_path)

    def close_spider(self, spider):
        if self.file:
            self.file.flush()
            self.file.close()
            self.file = None
        self.logger.info(
            "CellphonesReviewExportPipeline hoàn tất. Đã xuất %s review records vào %s",
            self.reviews_written,
            self.review_output_path,
        )

    def process_item(self, item, spider):
        if isinstance(item, TechReviewRawItem):
            line = json.dumps(dict(item), ensure_ascii=False) + "\n"
            if self.file:
                self.file.write(line)
                self.reviews_written += 1
            # DropItem để Scrapy FeedExporter (-o target_out) không ghi đè review vào file product
            raise DropItem(f"Review {item.get('review_id_raw')} đã được lưu vào review snapshot.")
        return item
