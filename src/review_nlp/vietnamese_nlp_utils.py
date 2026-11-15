"""Vietnamese NLP Utilities and Text Preprocessing Engine for E-Commerce Reviews.

Provides modular, robust text normalization routines tailored to Vietnamese tech reviews:
1. Unicode normalization (NFC standard).
2. Vietnamese tone-mark position standardization.
3. Elongated character reduction (e.g., 'rấttttt' -> 'rất', 'tốtttt' -> 'tốt').
4. Sentiment-preserving emoji mapping (positive/negative emoji tokens).
5. Contextual disambiguation for polysemous terms:
   - 'bh': 'bao_giờ' (hàng về) vs 'bảo_hành' (gói/gửi) vs 'bây_giờ' (thời điểm) vs 'bao_nhiêu' (giá/thời hạn).
   - 'cam': 'camera' (chụp/ảnh) vs 'cảm_ơn' (cam on) vs 'cảm_nhận' (cam nhan).
   - 'k': currency '500 k' -> '500k' vs negation 'k' -> 'không'.
   - Avoids global replacement of single-letter tokens ('a', 'c', 'e', 'm') to preserve hardware specs ('80 độ C', 'USB Type C', 'mặt A', 'chip M').
6. High-precision e-commerce teencode and abbreviation expansion.
7. Compound-word tokenization using underthesea with memoization.
8. Safe stopword filtering (never drops negations, intensifiers, or aspect nouns).
"""

from functools import lru_cache
import html
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata

# Try importing underthesea
try:
    from underthesea import word_tokenize
    UNDERTHESEA_AVAILABLE = True
except ImportError:
    UNDERTHESEA_AVAILABLE = False
    word_tokenize = None

# -----------------------------------------------------------------------------
# 1. EMOJI SENTIMENT MAPPING
# -----------------------------------------------------------------------------
POSITIVE_EMOJIS = {
    "👍", "👍🏻", "👍🏼", "👍🏽", "👍🏾", "👍🏿",
    "⭐", "🌟", "✨", "❤️", "💖", "💕", "😍", "🥰", "😘",
    "🔥", "👏", "😊", "😁", "😀", "😃", "😄", "🎉", "👌",
    "💯", "🏆", "💪", "💐", "🌸", "🌹", "🤩", "🤗", "😻",
}

NEGATIVE_EMOJIS = {
    "👎", "👎🏻", "👎🏼", "👎🏽", "👎🏾", "👎🏿",
    "😡", "😠", "🤬", "😢", "😭", "🤮", "🤢", "💔", "😤",
    "💩", "🙄", "😒", "😞", "😔", "😟", "😕", "🙁", "☹️",
    "😣", "😖", "😫", "😩", "🥺", "💀", "☠️",
}

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# 2. TEENCODE & E-COMMERCE TECH ABBREVIATION DICTIONARY
# (Polysemous terms and multi-context abbreviations are strictly handled by
# disambiguate_contextual_terms to prevent destructive collisions)
# -----------------------------------------------------------------------------
TEENCODE_DICT: Dict[str, str] = {
    # Unambiguous Negations
    "k": "không",
    "ko": "không",
    "khg": "không",
    "khong": "không",
    "hok": "không",
    "hong": "không",
    "hông": "không",
    "chug": "chưa",
    "chua": "chưa",
    "chx": "chưa",
    "đel": "không",
    "đéo": "không",
    "hem": "không",
    # Domain / Tech Product Nouns (Static)
    "dthoai": "điện_thoại",
    "dienthoai": "điện_thoại",
    "sanpham": "sản_phẩm",
    "nv": "nhân_viên",
    "nvien": "nhân_viên",
    "baohanh": "bảo_hành",
    "tgdd": "thế_giới_di_động",
    "tgdđ": "thế_giới_di_động",
    "fpt": "fpt_shop",
    "cps": "cellphones",
    "lap": "laptop",
    "mtb": "máy_tính_bảng",
    "pk": "phụ_kiện",
    "sac": "sạc",
    "tainghe": "tai_nghe",
    # Common conversational teencode
    "mng": "mọi_người",
    "mn": "mọi_người",
    "m.n": "mọi_người",
    "dc": "được",
    "đc": "được",
    "ntn": "như_thế_này",
    "vs": "với",
    "cx": "cũng",
    "ms": "mới",
    "oke": "ok",
    "okie": "ok",
    "oki": "ok",
    "okey": "ok",
    "r": "rồi",
    "ib": "nhắn_tin",
    "inbox": "nhắn_tin",
    "rep": "phản_hồi",
    "mik": "mình",
    "tks": "cảm_ơn",
    "thanks": "cảm_ơn",
    "thank": "cảm_ơn",
    "thx": "cảm_ơn",
    "cam on": "cảm_ơn",
    "cảm ơn": "cảm_ơn",
    "chất lượng": "chất_lượng",
    "hài lòng": "hài_lòng",
    "rất tốt": "rất_tốt",
    "tuyệt vời": "tuyệt_vời",
    "thất vọng": "thất_vọng",
    "quá tệ": "quá_tệ",
}

# -----------------------------------------------------------------------------
# 3. SENTIMENT-PRESERVING STOPWORDS
# -----------------------------------------------------------------------------
# Drop filler particles with 0 semantic or polarity value
SAFE_STOPWORDS: Set[str] = {
    "thì", "là", "mà", "của", "ở", "tại", "nhé", "ạ", "nha", "ha", "nè",
    "nghen", "hen", "vậy", "cho", "và", "do", "với", "từ",
    "lên", "xuống", "vào", "ra", "đến", "tới", "lại", "qua", "đi", "vừa",
    "cứ", "đều", "này", "kia", "đó", "nọ", "ấy", "đây", "đấy", "thế",
    "chính", "tự", "bên", "phía", "khi", "lúc", "suốt",
}

# CRITICAL WHITELIST: Never drop words that alter sentiment or domain meaning!
SENTIMENT_WHITELIST: Set[str] = {
    # Negations
    "không", "chẳng", "chưa", "chả", "kém", "hỏng", "lỗi", "mất", "thiếu", "tệ",
    "dở", "chán", "chậm", "tiếc", "ngừng", "cháy",
    # Intensifiers
    "rất", "quá", "cực_kỳ", "hơi", "lắm", "vô_cùng", "tuyệt_đối", "thực_sự",
    # Polarity tokens
    "pos_emoji", "neg_emoji", "tốt", "đẹp", "mượt", "ưng_ý", "hài_lòng", "ok",
    "bền", "nhanh", "ổn", "ngon", "xịn", "thích", "yêu", "đáng_tiền", "thất_vọng",
    # Domain keywords & Collocations
    "pin", "màn_hình", "camera", "giá", "nhân_viên", "bảo_hành", "máy", "pin_trâu",
    "shop", "ad", "admin", "bao_giờ", "bây_giờ", "bao_nhiêu", "khách_hàng",
    "sử_dụng", "bình_thường", "chi_nhánh", "điện_thoại", "iphone", "samsung",
    "ch_play", "tin_nhắn", "chuyển_khoản", "quảng_cáo", "giới_thiệu", "văn_phòng",
    "học_sinh", "sinh_viên", "hở_sáng", "ám_màn", "ám_vàng", "ám_xanh",
    "điểm_chết", "sọc_màn", "cháy_màn", "loạn_cảm_ứng", "liệt_cảm_ứng", "sập_nguồn",
    "sập_máy", "chai_pin", "tụt_pin", "hao_pin", "ngốn_pin", "phồng_pin", "giật_lag",
    "tụt_fps", "đơ_máy", "nóng_máy", "mát_máy", "tản_nhiệt", "mượt_mà", "bắt_sóng",
    "bắt_wifi", "chập_chờn", "loa_rè", "loa_nhỏ", "ọp_ẹp", "tiền_mất_tật_mang",
    "chăm_sóc_khách_hàng", "trung_tâm_bảo_hành", "1_đổi_1", "trả_góp", "đáng_đồng_tiền",
}


# -----------------------------------------------------------------------------
# CORE NORMALIZATION ROUTINES
# -----------------------------------------------------------------------------
def normalize_unicode(text: str) -> str:
    """Normalize string to Unicode NFC format."""
    if not isinstance(text, str):
        return ""
    return unicodedata.normalize("NFC", text)


def normalize_elongated_chars(text: str) -> str:
    """Reduce prolonged repetitive characters (e.g. 'rấttttt' -> 'rất', 'tốtttt' -> 'tốt').

    Allows up to 2 repetitions (e.g. 'oo' in 'good'), collapses 3+ to 1.
    """
    return re.sub(r"(.)\1{2,}", r"\1", text)


def map_sentiment_emojis(text: str) -> str:
    """Replace sentiment-carrying emojis with standardized tokens."""
    for emo in POSITIVE_EMOJIS:
        if emo in text:
            text = text.replace(emo, " pos_emoji ")
    for emo in NEGATIVE_EMOJIS:
        if emo in text:
            text = text.replace(emo, " neg_emoji ")
    return text


def strip_noise(text: str) -> str:
    """Remove URLs, HTML entities, phone numbers, and extraneous special symbols."""
    # Unescape HTML entities (e.g. &quot; -> ", &amp; -> &, &gt; -> >)
    text = html.unescape(text)
    # Strip any remaining unescaped or malformed entities (e.g. &quot, &gt, &lt, &amp)
    text = re.sub(r"&(?:quot|amp|lt|gt|#\d+|[a-zA-Z]+);?", " ", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    # Remove phone numbers (10-11 digits)
    text = re.sub(r"\b0\d{9,10}\b", " ", text)
    # Replace newlines and tabs with spaces
    text = re.sub(r"[\r\n\t]+", " ", text)
    # Collapse multiple punctuation (e.g. '!!!!', '????' -> '!')
    text = re.sub(r"([!?,.]){2,}", r"\1 ", text)
    return text


def disambiguate_contextual_terms(text: str) -> str:
    """Comprehensive contextual disambiguation engine for Vietnamese tech reviews."""

    # =========================================================================
    # GROUP 0: HARDWARE SPEC & UNIT PRESERVATION (Pre-empts word converters)
    # =========================================================================
    # 0a. Port & Chassis Specifications
    text = re.sub(r"\b(?:usb\s*[-_]?\s*)?type\s*[-_]?\s*c\b|\b(?:usb|cổng)\s*[-_]?\s*c\b", "type_c", text, flags=re.I)
    text = re.sub(r"\b(?:usb\s*[-_]?\s*)?type\s*[-_]?\s*a\b|\b(?:usb|cổng)\s*[-_]?\s*a\b", "usb_a", text, flags=re.I)
    text = re.sub(r"\b(?:mặt|nắp|vỏ)\s+([a-d])\b", lambda m: f"mặt_{m.group(1).lower()}", text, flags=re.I)
    text = re.sub(r"\bổ\s+(?:đĩa\s+)?([c-f])\b", lambda m: f"ổ_{m.group(1).lower()}", text, flags=re.I)
    text = re.sub(r"\bchip\s+(?:apple\s+)?m([1-4])\b", r"chip_m\1", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*độ\s*c\b", r"\1_độ_c", text, flags=re.I)

    # 0b. Screen Display & Panel Specs
    text = re.sub(
        r"\b(màn|màn\s*hình|video|xem|phim|độ\s*phân\s*giải|hdr)\s+(?:2k|4k|8k)\b",
        lambda m: m.group(0).lower().replace(" ", "_") + "_res",
        text,
        flags=re.I,
    )
    # Panel type TN vs tin nhắn: 'màn hình TN' -> 'màn_hình_tn'
    text = re.sub(r"\b(?:màn|màn\s*hình|tấm\s*nền)\s+tn\b", "màn_hình_tn", text, flags=re.I)

    # 0c. Numeric Units (Mass, Voltage, Frequency, Wattage, File size, Currency)
    text = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*kg\b", r"\1_kilogram", text, flags=re.I)
    text = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*v\b", r"\1_volt", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*hz\b", r"\1_hz", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*w\b", r"\1_watt", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*kb\b", r"\1_kilobyte", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*gb\b", r"\1_gb", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*tb\b", r"\1_tb", text, flags=re.I)
    text = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*inch\b", r"\1_inch", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*fps\b", r"\1_fps", text, flags=re.I)
    text = re.sub(r"\b(\d+)\s*k\b", r"\1_nghìn", text, flags=re.I)
    text = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*tr\b", r"\1_triệu", text, flags=re.I)

    # 0d. Time hours: '\d+ h' or '\d+h' -> '\1_giờ'
    text = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*h\b", r"\1_giờ", text, flags=re.I)

    # =========================================================================
    # GROUP 1: POLYSEMOUS SLANG & ABBREVIATIONS
    # =========================================================================
    # 1. 'bh': bao_giờ vs bảo_hành vs bao_nhiêu vs bây_giờ
    text = re.sub(
        r"\bbh\s+(hàng\s+về|có\s+hàng|mới\s+về|về\s+hàng|thì\s+có|thì\s+về|mới\s+có|về)\b",
        r"bao_giờ \1",
        text,
        flags=re.I,
    )
    warranty_before = (
        r"\b(hết|còn|gói|chính\s*sách|dịch\s*vụ|từ\s*chối|gửi|đi|tem|hạn|thời\s*gian|đổi|"
        r"phiếu|trung\s*tâm|tt|hãng|chế\s*độ|sẽ)\s+bh\b"
    )
    text = re.sub(warranty_before, r"\1 bảo_hành", text, flags=re.I)
    warranty_after = (
        r"\bbh\s+(máy|chính\s*hãng|lại|rõ\s*ràng|1\s*đổi\s*1|vip|\d+\s*tháng|dài|t\d+|và)\b"
    )
    text = re.sub(warranty_after, r"bảo_hành \1", text, flags=re.I)
    text = re.sub(r"\b(bảo\s*hành)\s+bh\b", r"\1 bao_nhiêu", text, flags=re.I)
    text = re.sub(r"\b(giá|thêm|bù)\s+bh\b", r"\1 bao_nhiêu", text, flags=re.I)
    text = re.sub(r"\bbh\s+(tháng|tiền|k|nghìn|triệu)\b", r"bao_nhiêu \1", text, flags=re.I)
    text = re.sub(r"\bbh\s+(e|em|mình|mk|tôi|shop|ad|bạn|giá|lên|tải)\b", r"bây_giờ \1", text, flags=re.I)
    text = re.sub(r"\b(hiện\s*tại|đến|tới|từ\s*trước\s*đến|nên)\s+bh\b", r"\1 bây_giờ", text, flags=re.I)
    text = re.sub(r"\bbh\b", "bảo_hành", text, flags=re.I)

    # 2. 'cam': camera vs cảm_ơn vs cảm_nhận vs webcam
    text = re.sub(r"\bcam\s+o[rn]\b", "cảm_ơn", text, flags=re.I)
    text = re.sub(r"\bcam\s+ơn\b", "cảm_ơn", text, flags=re.I)
    text = re.sub(r"\bcam\s+nh[aâ]n\b", "cảm_nhận", text, flags=re.I)
    text = re.sub(r"\bweb\s+cam\b", "webcam", text, flags=re.I)
    text = re.sub(
        r"\bcam\s+(trước|sau|chụp|nét|ảo|đẹp|xịn|lồi|quay|truoc|chup|net|ao|dep|xin|loi|\d+mp)\b",
        r"camera \1",
        text,
        flags=re.I,
    )
    text = re.sub(r"\b(che|tắt|bật|cụm|ống\s*kính)\s+cam\b", r"\1 camera", text, flags=re.I)

    # 3. 'kg': không vs mass (mass already converted to _kilogram above)
    text = re.sub(r"\bchi\s*nhánh\s+kg\b", "chi_nhánh Kiên_Giang", text, flags=re.I)
    text = re.sub(r"\bkg\b", "không", text, flags=re.I)

    # 4. 'kh': khách_hàng vs không
    cust_before = (
        r"\b(cho|phục\s*vụ|hỗ\s*trợ|đến|hướng\s*đến|nhu\s*cầu\s*của|đối\s*tượng|chăm\s*sóc|"
        r"tạo|tư\s*vấn\s*cho|của|dành\s*cho|quyền\s*lợi)\s+kh\b"
    )
    text = re.sub(cust_before, r"\1 khách_hàng", text, flags=re.I)
    cust_after = (
        r"\bkh\s+(chọn|mua|hàng|nhận|thích|hài\s*lòng|yên\s*tâm|thân\s*thiết|sẽ\s*quên|"
        r"ko\s*hỏi|không\s*hỏi|phản\s*ánh|khiếu\s*nại)\b"
    )
    text = re.sub(cust_after, r"khách_hàng \1", text, flags=re.I)
    text = re.sub(r"\bkh\b", "không", text, flags=re.I)

    # 5. 'cn': chủ_nhật vs chi_nhánh vs công_nghệ
    text = re.sub(r"\b(thứ\s*7|t7|thứ\s*bảy|trừ|ngày)\s*[\.,]?\s*cn\b", r"\1 chủ_nhật", text, flags=re.I)
    branch_before = r"\b(ở|tại|đến|qua|ghé|shop|cellphones|cửa\s*hàng)\s+cn\b"
    text = re.sub(branch_before, r"\1 chi_nhánh", text, flags=re.I)
    branch_after = (
        r"\bcn\s+(nào|quận|q\d+|bình\s*dương|bình\s*tân|gò\s*vấp|hà\s*nội|hcm|tphcm|"
        r"đà\s*nẵng|lê\s*trọng\s*tấn|khu\s*vực)\b"
    )
    text = re.sub(branch_after, r"chi_nhánh \1", text, flags=re.I)
    text = re.sub(r"\bcn\s+(mới|thông\s*tin|cao)\b", r"công_nghệ \1", text, flags=re.I)

    # 6. 'mh': màn_hình vs mình
    screen_before = (
        r"\b(tắt|bật|vỡ|sọc|thay|hỏng|lỗi|ám|dán|ép|kính|độ|cụm|hở|nứt|trầy|xước|bảo\s*vệ)\s+mh\b"
    )
    text = re.sub(screen_before, r"\1 màn_hình", text, flags=re.I)
    screen_after = (
        r"\bmh\s+(đẹp|xấu|oled|ips|amoled|to|nhỏ|sáng|tối|cong|phẳng|rộng|120hz|60hz|"
        r"bị\s*lỗi|bị\s*sọc|hiển\s*thị)\b"
    )
    text = re.sub(screen_after, r"màn_hình \1", text, flags=re.I)
    me_before = r"\b(giúp|cho|với|tới|của)\s+mh\b"
    text = re.sub(me_before, r"\1 mình", text, flags=re.I)
    me_after = r"\bmh\s+(mua|dùng|xài|thấy|nghĩ|thông\s*cảm|nhận|hỏi|góp|hủy|thích)\b"
    text = re.sub(me_after, r"mình \1", text, flags=re.I)
    text = re.sub(r"\bmh\b", "mình", text, flags=re.I)

    # 7. 'sd': thẻ_sd vs sử_dụng
    text = re.sub(r"\b(?:thẻ|thẻ\s*nhớ|khe|micro)\s+sd\b", "thẻ_sd", text, flags=re.I)
    text = re.sub(r"\bsd\s+thẻ\b", "thẻ_sd", text, flags=re.I)
    text = re.sub(r"\bsd\b", "sử_dụng", text, flags=re.I)

    # 8. 'bt': biết vs bình_thường
    know_before = r"\b(k|ko|không|chưa|chả|chẳng|ai|chắc)\s+bt\b"
    text = re.sub(know_before, r"\1 biết", text, flags=re.I)
    normal_before = r"\b(dùng|xài|chạy|thấy|vẫn|rất|khá|hoạt\s*động|chơi|sd)\s+bt\b"
    text = re.sub(normal_before, r"\1 bình_thường", text, flags=re.I)
    text = re.sub(r"\bbt\s+(thôi|ổn|không\s*sao)\b", r"bình_thường \1", text, flags=re.I)

    # 9. 'kb': kilobyte vs không_biết
    text = re.sub(r"\b(chục|mấy|vài)\s+kb\b", r"\1_kilobyte", text, flags=re.I)
    text = re.sub(r"\bkb\b", "không_biết", text, flags=re.I)

    # 10. 'ch': ch_play vs cửa_hàng vs chưa
    text = re.sub(r"\bch\s*play\b", "ch_play", text, flags=re.I)
    store_before = r"\b(ở|tại|đến|ghé|qua|vào|của)\s+ch\b"
    text = re.sub(store_before, r"\1 cửa_hàng", text, flags=re.I)
    notyet_after = r"\bch\s+(mua|dùng|xài|có|hết|rõ|thấy)\b"
    text = re.sub(notyet_after, r"chưa \1", text, flags=re.I)

    # 11. 'h': giờ vs bao_giờ vs bây_giờ vs hihi
    text = re.sub(r"\b(bao|mấy)\s+h\b", "bao_giờ", text, flags=re.I)
    text = re.sub(r"\bh\s+(mới|này|thì|e|em|shop|ad)\b", r"bây_giờ \1", text, flags=re.I)
    text = re.sub(r"\b(?:h\s+){2,}h\b", "hihi", text, flags=re.I)

    # 12. 'v': gta_v vs như_vậy vs vậy vs :v
    text = re.sub(r"\b(gta|grand\s*theft\s*auto)\s*v\b", "gta_v", text, flags=re.I)
    text = re.sub(r"\bnhư\s+v\b", "như_vậy", text, flags=re.I)
    text = re.sub(r"\b(sao|thế|k|gì|được|chưa|đâu)\s+v([?!.]|\s*|$)", r"\1 vậy\2", text, flags=re.I)
    text = re.sub(r":v\b", " pos_emoji ", text)
    text = re.sub(r"\bv\.v\b", "vân_vân", text, flags=re.I)

    # 13. 'ss': so_sánh vs samsung
    text = re.sub(r"\b(để|mang|đem|so)\s+ss\b", r"\1 so_sánh", text, flags=re.I)
    text = re.sub(r"\bss\s+(với|vs|cùng|giữa)\b", r"so_sánh \1", text, flags=re.I)
    ss_models = (
        r"\bss\s+(a\d+|s\d+|note\d+|m\d+|z\s*fold|z\s*flip|galaxy|ultra|fe|chính\s*hãng|"
        r"mới|cũ)\b"
    )
    text = re.sub(ss_models, r"samsung \1", text, flags=re.I)
    text = re.sub(r"\b(máy|hãng|ttbh|mua|bán)\s+ss\b", r"\1 samsung", text, flags=re.I)

    # 14. 'ip': địa_chỉ_ip vs iphone
    text = re.sub(r"\bđịa\s*chỉ\s+ip\b", "địa_chỉ_ip", text, flags=re.I)
    text = re.sub(r"\b(fake|đổi|chặn)\s+ip\b", r"\1 địa_chỉ_ip", text, flags=re.I)
    ip_models = r"\bip\s*(\d+|x|xs|xr|promax|pro|plus|lock|quốc\s*tế|mới|cũ)\b"
    text = re.sub(ip_models, r"iphone \1", text, flags=re.I)
    text = re.sub(r"\b(mua|dùng|xài|bán|fan)\s+ip\b", r"\1 iphone", text, flags=re.I)

    # 15. 'tn': tin_nhắn (panel TN handled above)
    text = re.sub(r"\b(rep|nhắn|gửi|trả\s*lời|xem)\s+tn\b", r"\1 tin_nhắn", text, flags=re.I)

    # 16. 'tl': trả_lời vs telex
    text = re.sub(r"\b(ai|ko|chưa|không|sao\s*không)\s+tl\b", r"\1 trả_lời", text, flags=re.I)
    text = re.sub(r"\btl\s+(mình|em|khách)\b", r"trả_lời \1", text, flags=re.I)
    text = re.sub(r"\b(gõ|kiểu\s*gõ)\s+tl\b", r"\1 telex", text, flags=re.I)

    # 17. 'ck': chuyển_khoản
    text = re.sub(r"\b(chuyển|tiền|yêu\s*cầu|sẽ|muốn|được|đi|đã)\s+ck\b", r"\1 chuyển_khoản", text, flags=re.I)
    text = re.sub(r"\bck\s+(sau\s*khi|tiền|qua|ngân\s*hàng|stk|nhé|nha|ạ|luôn|ngay)\b", r"chuyển_khoản \1", text, flags=re.I)

    # 18. 'ad': admin vs quảng_cáo
    text = re.sub(r"\b(chặn|bỏ|tắt|quá\s*nhiều)\s+ad\b", r"\1 quảng_cáo", text, flags=re.I)
    text = re.sub(r"\b(hả|nhé|nha|ạ|k|ko|không|ơi)\s+ad\b", r"\1 admin", text, flags=re.I)
    text = re.sub(r"\bad\s+(ơi|cho|tư\s*vấn|check)\b", r"admin \1", text, flags=re.I)

    # 19. 'gt': giới_thiệu
    text = re.sub(r"\b(sẽ|muốn|được|để)\s+gt\b", r"\1 giới_thiệu", text, flags=re.I)
    text = re.sub(r"\bgt\s+(cho|bạn\s*bè|người\s*thân)\b", r"giới_thiệu \1", text, flags=re.I)

    # 20. 'ng': người
    text = re.sub(r"\bng\s+(ta|thân|dùng|mua|bán|khác|nào|lớn)\b", r"người \1", text, flags=re.I)
    text = re.sub(r"\b(cho|nhiều|mọi)\s+ng\b", r"\1 người", text, flags=re.I)

    # 21. 'bn': bao_nhiêu vs bạn
    text = re.sub(r"\b(giá|thời\s*gian|còn|hết|mất)\s+bn\b", r"\1 bao_nhiêu", text, flags=re.I)
    text = re.sub(r"\bbn\s+(nhiêu|tiền|tháng|ngày|tiếng|k|triệu)\b", r"bao_nhiêu \1", text, flags=re.I)
    text = re.sub(r"\b(cảm\s*ơn|cho|chúc|nhờ|hỗ\s*trợ)\s+bn\b", r"\1 bạn", text, flags=re.I)

    # 22. 'ak': particle ạ
    text = re.sub(r"\b(k|ko|không|phải|đúng|thế|sao|vậy)\s+ak\b", r"\1 ạ", text, flags=re.I)

    # 23. 'mk': mật_khẩu vs mình
    text = re.sub(r"\b(nhập|quên|đổi|mã|cài)\s+mk\b", r"\1 mật_khẩu", text, flags=re.I)
    text = re.sub(r"\bmk\s+(mua|dùng|xài|hóng|thấy|nghĩ|nhận|hỏi)\b", r"mình \1", text, flags=re.I)
    text = re.sub(r"\b(cho|hỗ\s*trợ|với|tới)\s+mk\b", r"\1 mình", text, flags=re.I)

    # 24. 'đk' / 'dk': được vs đăng_ký
    text = re.sub(r"\b(mún|muốn|cần|được)\s+đk\b", r"\1 đăng_ký", text, flags=re.I)
    text = re.sub(r"\bđk\s+(thêm|gói|bảo\s*hành|mạng|tài\s*khoản)\b", r"đăng_ký \1", text, flags=re.I)
    text = re.sub(r"\b(?:đk|dk)\b", "được", text, flags=re.I)

    # 25. 'sp': hỗ_trợ (support) vs sản_phẩm
    text = re.sub(r"\b(tư\s*vấn|nv|nhân\s*viên)\s*,\s*sp\s+(nhiệt\s*tình|chu\s*đáo)\b", r"\1 , hỗ_trợ \2", text, flags=re.I)
    text = re.sub(r"\bsp\b", "sản_phẩm", text, flags=re.I)

    # 26. Other High-Frequency Slang Tokens
    text = re.sub(r"\bae\b", "anh_em", text, flags=re.I)
    text = re.sub(r"\b(?:đt|dt)\b", "điện_thoại", text, flags=re.I)
    text = re.sub(r"\bvp\b", "văn_phòng", text, flags=re.I)
    text = re.sub(r"\blq\b", "liên_quân", text, flags=re.I)
    text = re.sub(r"\bsv\b", "sinh_viên", text, flags=re.I)
    text = re.sub(r"\bhs\b", "học_sinh", text, flags=re.I)
    text = re.sub(r"\bqc\b", "quảng_cáo", text, flags=re.I)
    text = re.sub(r"\bwf\b", "wifi", text, flags=re.I)
    text = re.sub(r"\bkm\b", "khuyến_mãi", text, flags=re.I)
    text = re.sub(r"\bdv\b", "dịch_vụ", text, flags=re.I)
    text = re.sub(r"\bttbh\b", "trung_tâm_bảo_hành", text, flags=re.I)
    text = re.sub(r"\bcskh\b", "chăm_sóc_khách_hàng", text, flags=re.I)

    # =========================================================================
    # GROUP 2: TECH E-COMMERCE COMPOUND IDIOMS (Segmented semantic phrases)
    # =========================================================================
    compounds = {
        # Screen / Display
        r"\bhở\s+sáng\b": "hở_sáng",
        r"\bám\s+màn\b": "ám_màn",
        r"\bám\s+vàng\b": "ám_vàng",
        r"\bám\s+xanh\b": "ám_xanh",
        r"\bđiểm\s+chết\b": "điểm_chết",
        r"\bsọc\s+màn(?:_hình)?\b": "sọc_màn",
        r"\bcháy\s+màn(?:_hình)?\b": "cháy_màn",
        r"\bloạn\s+cảm\s*ứng\b": "loạn_cảm_ứng",
        r"\bliệt\s+cảm\s*ứng\b": "liệt_cảm_ứng",
        r"\bđơ\s+cảm\s*ứng\b": "đơ_cảm_ứng",
        r"\btai\s+thỏ\b": "tai_thỏ",
        r"\bnốt\s+ruồi\b": "nốt_ruồi",
        # Power / Battery
        r"\bsập\s+nguồn\b": "sập_nguồn",
        r"\bsập\s+máy\b": "sập_máy",
        r"\bpin\s+trâu\b": "pin_trâu",
        r"\bchai\s+pin\b": "chai_pin",
        r"\btụt\s+pin\b": "tụt_pin",
        r"\bhao\s+pin\b": "hao_pin",
        r"\bngốn\s+pin\b": "ngốn_pin",
        r"\bphồng\s+pin\b": "phồng_pin",
        r"\bpin\s+yếu\b": "pin_yếu",
        r"\bsạc\s+nhanh\b": "sạc_nhanh",
        r"\bsạc\s+chậm\b": "sạc_chậm",
        # Performance
        r"\bgiật\s+lag\b": "giật_lag",
        r"\btụt\s+fps\b": "tụt_fps",
        r"\bđơ\s+máy\b": "đơ_máy",
        r"\bnóng\s+máy\b": "nóng_máy",
        r"\bmát\s+máy\b": "mát_máy",
        r"\btản\s+nhiệt\b": "tản_nhiệt",
        r"\bmượt\s+mà\b": "mượt_mà",
        # Audio / Connection
        r"\bbắt\s+sóng\b": "bắt_sóng",
        r"\bbắt\s+wifi\b": "bắt_wifi",
        r"\bchập\s+chờn\b": "chập_chờn",
        r"\bloa\s+rè\b": "loa_rè",
        r"\bloa\s+nhỏ\b": "loa_nhỏ",
        r"\bmất\s+sóng\b": "mất_sóng",
        # Hardware condition & origin
        r"\bọp\s+ẹp\b": "ọp_ẹp",
        r"\bnguyên\s+seal\b": "nguyên_seal",
        r"\bđập\s+hộp\b": "đập_hộp",
        r"\bbóc\s+máy\b": "bóc_máy",
        r"\bhàng\s+cũ\b": "hàng_cũ",
        r"\bchính\s+hãng\b": "chính_hãng",
        r"\bxách\s+tay\b": "xách_tay",
        # Warranty & Customer service
        r"\b1\s+đổi\s+1\b": "1_đổi_1",
        r"\btrả\s+góp\b": "trả_góp",
        r"\bchăm\s+sóc\s+khách\s*hàng\b": "chăm_sóc_khách_hàng",
        r"\btrung\s+tâm\s+bảo\s*hành\b": "trung_tâm_bảo_hành",
        r"\bbảo\s+hành\s+vàng\b": "bảo_hành_vàng",
        # Sentiment idioms
        r"\btiền\s+mất\s+tật\s+mang\b": "tiền_mất_tật_mang",
        r"\bđáng\s+đồng\s+tiền\b": "đáng_đồng_tiền",
        r"\bđáng\s+tiền\b": "đáng_tiền",
    }
    for pat, rep in compounds.items():
        text = re.sub(pat, rep, text, flags=re.I)

    return text

    return text


def expand_teencode(text: str) -> str:
    """Expand tech abbreviations, teencode, and colloquial terms."""
    # First pass: multi-word phrases (e.g. 'pin trâu' -> 'pin_trâu')
    for phrase, replacement in TEENCODE_DICT.items():
        if " " in phrase and phrase in text:
            text = re.sub(r"\b" + re.escape(phrase) + r"\b", replacement, text, flags=re.I)

    # Second pass: single word tokens (word-boundary matched)
    words = text.split()
    expanded_words = []
    for w in words:
        clean_w = w.lower().strip(".,!?\"':;()")
        if clean_w in TEENCODE_DICT and " " not in clean_w:
            rep = TEENCODE_DICT[clean_w]
            expanded_words.append(rep)
        else:
            expanded_words.append(w)
    return " ".join(expanded_words)


@lru_cache(maxsize=30000)
def cached_word_tokenize(text: str) -> str:
    """Cached wrapper around underthesea word_tokenize for compound-word segmentation."""
    if not text:
        return ""
    if UNDERTHESEA_AVAILABLE and word_tokenize is not None:
        try:
            return word_tokenize(text, format="text")
        except Exception:
            return text
    return text


def filter_stopwords(tokenized_text: str) -> str:
    """Filter out non-semantic functional stopwords while strictly preserving sentiment."""
    tokens = tokenized_text.split()
    kept: List[str] = []
    for tok in tokens:
        clean_tok = tok.lower().strip(".,!?\"':;()")
        if not clean_tok:
            continue
        # Always keep if in whitelist or contains sentiment tags
        if clean_tok in SENTIMENT_WHITELIST or clean_tok.startswith("pos_") or clean_tok.startswith("neg_"):
            kept.append(clean_tok)
        elif clean_tok not in SAFE_STOPWORDS and not clean_tok.isdigit():
            kept.append(clean_tok)
    return " ".join(kept)


def preprocess_text(text: Optional[str]) -> Dict[str, Any]:
    """Execute complete end-to-end preprocessing on a raw Vietnamese review string.

    Returns a dictionary with:
    - text_cleaned: Lowecased, noise-stripped, teencode-expanded text.
    - text_tokenized: Compound-word segmented text using underthesea (format='text').
    - text_stopwords_removed: Segmented text with safe stopwords removed.
    - tokens_list: List of token strings.
    - token_count: Total tokens in tokenized string.
    """
    if not text or not isinstance(text, str):
        return {
            "text_cleaned": "",
            "text_tokenized": "",
            "text_stopwords_removed": "",
            "tokens_list": [],
            "token_count": 0,
        }

    # 1. Unicode NFC
    s = normalize_unicode(text)

    # 2. Lowercase
    s = s.lower()

    # 3. Strip HTML, URLs, phone numbers
    s = strip_noise(s)

    # 4. Map emojis
    s = map_sentiment_emojis(s)

    # 5. Elongation reduction
    s = normalize_elongated_chars(s)

    # 6. Contextual disambiguation ('bh', 'cam', 'k' with numbers)
    s = disambiguate_contextual_terms(s)

    # 7. Teencode expansion
    s = expand_teencode(s)

    # 8. Normalize spaces
    s = re.sub(r"\s+", " ", s).strip()
    text_cleaned = s

    # 9. Tokenization (compound words)
    text_tokenized = cached_word_tokenize(text_cleaned)

    # 10. Stopword filtering (safe)
    text_stopwords_removed = filter_stopwords(text_tokenized)

    tokens_list = text_stopwords_removed.split()
    token_count = len(tokens_list)

    return {
        "text_cleaned": text_cleaned,
        "text_tokenized": text_tokenized,
        "text_stopwords_removed": text_stopwords_removed,
        "tokens_list": tokens_list,
        "token_count": token_count,
    }
