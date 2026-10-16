import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Lock toàn cục cho runner: chỉ một run_crawler.py được chạy crawl tại một thời điểm.
LOCK_FILE_PATH = PROJECT_ROOT / "data" / "raw" / ".run_crawler.lock"
# Lock file rỗng/hỏng chỉ được coi là stale khi đã cũ hơn ngưỡng này (tránh xóa lock đang được ghi).
LOCK_UNREADABLE_GRACE_SECONDS = 60.0
# File "breaker" (khóa phụ khi dọn stale lock) bị coi là bỏ rơi sau ngưỡng này.
LOCK_BREAKER_STALE_SECONDS = 30.0
LOCK_CONFLICT_EXIT_CODE = 3

# Reconfigure stdout/stderr to UTF-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# Registry đăng ký các nguồn crawler (extensible architecture)
SOURCE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "tgdd": {
        "name": "Thế Giới Di Động",
        "implemented": True,
        "raw_folder": "tgdd",
        "spiders": {
            "laptop": PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_laptop_spider.py",
            "smartphone": PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_smartphone_spider.py",
        },
    },
    "fptshop": {
        "name": "FPT Shop",
        "implemented": True,
        "raw_folder": "fptshop",
        "spiders": {
            "laptop": PROJECT_ROOT / "crawler" / "fptshop" / "fptshop_laptop_spider.py",
            "smartphone": PROJECT_ROOT / "crawler" / "fptshop" / "fptshop_smartphone_spider.py",
        },
    },
    "cellphones": {
        "name": "CellphoneS",
        "implemented": True,
        "raw_folder": "cellphoneS",
        "spiders": {
            "laptop": PROJECT_ROOT / "crawler" / "cellphoneS" / "cellphones_laptop_spider.py",
            "smartphone": PROJECT_ROOT / "crawler" / "cellphoneS" / "cellphones_smartphone_spider.py",
        },
    },
    "viettelstore": {
        "name": "Viettel Store",
        "implemented": False,
        "raw_folder": "viettelstore",
        "spiders": {},
    },
    "hoanghamobile": {
        "name": "Hoàng Hà Mobile",
        "implemented": False,
        "raw_folder": "hoanghamobile",
        "spiders": {},
    },
}


def generate_batch_id(dt: Optional[datetime] = None) -> str:
    """Tạo batch_id từ timestamp (mặc định là datetime hiện tại)."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")


def get_snapshot_path(category: str, batch_id: str, base_dir: Optional[Path] = None, source: str = "tgdd") -> Path:
    """
    Tạo đường dẫn snapshot bất biến (immutable raw snapshot) cho sản phẩm/biến thể.
    Bảo toàn snapshot cũ, không thực hiện overwrite.
    """
    if base_dir is None:
        src_key = source.lower()
        if src_key in SOURCE_REGISTRY:
            source_folder = SOURCE_REGISTRY[src_key]["raw_folder"]
        else:
            source_folder = "cellphoneS" if src_key == "cellphones" else source
        base_dir = PROJECT_ROOT / "data" / "raw" / source_folder
    return base_dir / category / f"{batch_id}.jsonl"


def get_review_snapshot_path(category: str, batch_id: str, base_dir: Optional[Path] = None, source: str = "tgdd") -> Path:
    """
    Tạo đường dẫn snapshot bất biến (immutable raw snapshot) cho review/comment.
    Bảo toàn snapshot cũ, không thực hiện overwrite.
    """
    if base_dir is None:
        src_key = source.lower()
        if src_key in SOURCE_REGISTRY:
            source_folder = SOURCE_REGISTRY[src_key]["raw_folder"]
        else:
            source_folder = "cellphoneS" if src_key == "cellphones" else source
        base_dir = PROJECT_ROOT / "data" / "raw" / source_folder
    return base_dir / f"{category}_reviews" / f"{batch_id}.jsonl"



def ensure_output_path_available(output_path: Path) -> None:
    """
    Đảm bảo output path chưa tồn tại.

    Raw snapshot phải immutable:
    - Không overwrite
    - Không append vào snapshot cũ
    """
    if output_path.exists():
        raise FileExistsError(
            f"Output snapshot đã tồn tại: {output_path}. "
            "Không được overwrite/append vào raw snapshot cũ."
        )


# ---------------------------------------------------------------------------
# Runner lock (chống concurrent run / race condition)
# ---------------------------------------------------------------------------


class CrawlerLockError(RuntimeError):
    """Không thể lấy / xác minh runner lock (đã có runner khác đang chạy)."""


def _query_process(pid: int) -> Tuple[bool, Optional[str]]:
    """
    Trả về (alive, start_token) cho một PID.
    start_token là định danh thời điểm khởi động process, dùng để phát hiện PID bị tái sử dụng.
    Khi không xác định được chắc chắn, ưu tiên coi process là CÒN SỐNG (an toàn).
    """
    if not isinstance(pid, int) or pid <= 0:
        return False, None

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        ERROR_ACCESS_DENIED = 5

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # ACCESS_DENIED nghĩa là process tồn tại nhưng không đủ quyền truy vấn.
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED, None
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True, None
            if exit_code.value != STILL_ACTIVE:
                return False, None
            creation, exit_t, kernel_t, user_t = (wintypes.FILETIME() for _ in range(4))
            if kernel32.GetProcessTimes(
                handle, ctypes.byref(creation), ctypes.byref(exit_t), ctypes.byref(kernel_t), ctypes.byref(user_t)
            ):
                ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
                return True, f"win:{ticks}"
            return True, None
        finally:
            kernel32.CloseHandle(handle)

    # POSIX
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, None
    except PermissionError:
        return True, None
    except OSError:
        return True, None
    start_token = None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        fields = stat[stat.rindex(")") + 2:].split()
        start_token = f"linux:{fields[19]}"
    except (OSError, ValueError, IndexError):
        pass
    return True, start_token


def _process_matches(pid: Any, expected_start: Optional[str]) -> bool:
    """True nếu PID còn sống và (nếu có start token) đúng là process đã ghi vào lock."""
    if not isinstance(pid, int):
        return False
    alive, start_token = _query_process(pid)
    if not alive:
        return False
    if expected_start and start_token and expected_start != start_token:
        return False  # PID đã bị tái sử dụng bởi process khác
    return True


class RunnerLock:
    """
    Lock độc quyền giữa các tiến trình run_crawler.py.

    - Acquire bằng os.open(O_CREAT | O_EXCL): atomic trên NTFS và POSIX, không có check-then-create.
    - Nội dung lock ghi token, pid, start time của runner và PID của Scrapy child đang chạy.
    - Stale lock: runner và child (nếu có) đều đã chết hoặc PID bị tái sử dụng; lock rỗng/hỏng và cũ
      hơn LOCK_UNREADABLE_GRACE_SECONDS. Lock của host khác không bao giờ bị tự động xóa.
    - Việc xóa stale lock được tuần tự hóa qua file breaker (O_EXCL) và kiểm tra lại token trước khi xóa,
      để hai runner cùng phát hiện stale không thể xóa nhầm lock mới của nhau.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        unreadable_grace_seconds: Optional[float] = None,
        breaker_stale_seconds: Optional[float] = None,
    ) -> None:
        self.path = Path(path) if path is not None else LOCK_FILE_PATH
        self.breaker_path = self.path.with_name(self.path.name + ".break")
        self.unreadable_grace_seconds = (
            LOCK_UNREADABLE_GRACE_SECONDS if unreadable_grace_seconds is None else unreadable_grace_seconds
        )
        self.breaker_stale_seconds = (
            LOCK_BREAKER_STALE_SECONDS if breaker_stale_seconds is None else breaker_stale_seconds
        )
        self.token: Optional[str] = None
        self._info: Dict[str, Any] = {}

    # -- trạng thái -----------------------------------------------------------
    @property
    def is_held(self) -> bool:
        return self.token is not None

    def __enter__(self) -> "RunnerLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    # -- đọc / đánh giá lock hiện có ------------------------------------------
    def _read_info(self) -> Optional[Dict[str, Any]]:
        """Đọc nội dung lock. None nếu rỗng/hỏng. Raise FileNotFoundError nếu không tồn tại."""
        with open(self.path, "r", encoding="utf-8") as f:
            raw = f.read()
        try:
            info = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(info, dict) or not isinstance(info.get("pid"), int) or not info.get("token"):
            return None
        return info

    def _lock_age_seconds(self) -> float:
        return max(0.0, time.time() - self.path.stat().st_mtime)

    def _evaluate_stale(self, info: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
        if info is None:
            age = self._lock_age_seconds()
            if age > self.unreadable_grace_seconds:
                return True, f"lock file rỗng/hỏng và đã cũ {age:.0f}s"
            return False, f"lock file rỗng/hỏng nhưng mới tạo {age:.0f}s (có thể đang được ghi)"

        host = info.get("hostname")
        if host and host != socket.gethostname():
            return False, f"lock thuộc host khác ({host}); không thể xác minh, cần xử lý thủ công"

        if _process_matches(info.get("pid"), info.get("process_start")):
            return False, f"runner PID {info.get('pid')} vẫn đang chạy"
        if info.get("child_pid") is not None and _process_matches(info.get("child_pid"), info.get("child_start")):
            return False, f"Scrapy child PID {info.get('child_pid')} của runner cũ vẫn đang chạy"
        return True, f"runner PID {info.get('pid')} (và Scrapy child nếu có) không còn chạy"

    # -- breaker (khóa phụ khi xóa stale lock) --------------------------------
    def _acquire_breaker(self) -> bool:
        for _ in range(2):
            try:
                fd = os.open(str(self.breaker_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = max(0.0, time.time() - self.breaker_path.stat().st_mtime)
                except FileNotFoundError:
                    continue
                if age > self.breaker_stale_seconds:
                    self._unlink_quietly(self.breaker_path)
                    continue
                return False
            else:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
                return True
        return False

    @staticmethod
    def _unlink_quietly(path: Path, attempts: int = 5) -> bool:
        for i in range(attempts):
            try:
                os.unlink(path)
                return True
            except FileNotFoundError:
                return True
            except PermissionError:
                # Windows: file đang được process khác mở để đọc -> thử lại
                time.sleep(0.05 * (i + 1))
        return False

    def _break_stale_lock(self, expected_token: Optional[str]) -> None:
        if not self._acquire_breaker():
            raise CrawlerLockError(
                f"Một runner khác đang dọn stale lock ({self.breaker_path}). Hãy thử lại sau."
            )
        try:
            # Kiểm tra lại dưới breaker: lock có thể đã bị runner khác thay bằng lock mới hợp lệ.
            try:
                current = self._read_info()
                current_token = current.get("token") if current else None
                if current_token != expected_token:
                    return  # lock đã đổi chủ -> vòng acquire sẽ đánh giá lại
                stale, _ = self._evaluate_stale(current)
            except FileNotFoundError:
                return
            if not stale:
                return
            print(f"[LOCK] Phát hiện stale lock, tiến hành thu hồi: {self.path} ({current})")
            if not self._unlink_quietly(self.path):
                raise CrawlerLockError(f"Không thể xóa stale lock: {self.path}")
        finally:
            self._unlink_quietly(self.breaker_path)

    # -- ghi lock -----------------------------------------------------------
    def _rewrite_info(self) -> None:
        """Ghi đè nội dung lock tại chỗ (không xóa file, nên lock luôn tồn tại trong lúc cập nhật)."""
        with open(self.path, "r+", encoding="utf-8") as f:
            f.seek(0)
            f.truncate()
            f.write(json.dumps(self._info, ensure_ascii=False))
            f.flush()
            os.fsync(f.fileno())

    def acquire(self, max_attempts: int = 5) -> "RunnerLock":
        if self.is_held:
            raise CrawlerLockError(f"Lock {self.path} đã được giữ bởi chính instance này.")
        self.path.parent.mkdir(parents=True, exist_ok=True)

        last_reason = ""
        for _ in range(max_attempts):
            try:
                fd = os.open(
                    str(self.path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
                )
            except FileExistsError:
                try:
                    info = self._read_info()
                    stale, last_reason = self._evaluate_stale(info)
                except FileNotFoundError:
                    continue  # holder vừa release -> thử tạo lại ngay
                except PermissionError:
                    # Windows: lock đang ở trạng thái delete-pending -> chờ rồi thử lại
                    last_reason = "lock file tạm thời không truy cập được"
                    time.sleep(0.1)
                    continue
                if not stale:
                    raise CrawlerLockError(self._format_conflict(info, last_reason))
                self._break_stale_lock(info.get("token") if info else None)
                continue

            token = uuid.uuid4().hex
            _, start_token = _query_process(os.getpid())
            info = {
                "token": token,
                "pid": os.getpid(),
                "process_start": start_token,
                "hostname": socket.gethostname(),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "argv": list(sys.argv),
                "child_pid": None,
                "child_start": None,
            }
            try:
                os.write(fd, json.dumps(info, ensure_ascii=False).encode("utf-8"))
                os.fsync(fd)
            except BaseException:
                os.close(fd)
                self._unlink_quietly(self.path)
                raise
            os.close(fd)
            self.token = token
            self._info = info
            return self

        raise CrawlerLockError(
            f"Không thể lấy runner lock {self.path} sau {max_attempts} lần thử ({last_reason})."
        )

    def _format_conflict(self, info: Optional[Dict[str, Any]], reason: str) -> str:
        holder = "không đọc được thông tin"
        if info:
            holder = (
                f"pid={info.get('pid')}, host={info.get('hostname')}, "
                f"created_at={info.get('created_at')}, child_pid={info.get('child_pid')}, "
                f"argv={' '.join(map(str, info.get('argv') or []))}"
            )
        return (
            f"Đã có một run_crawler.py khác đang giữ lock {self.path} ({reason}). "
            f"Holder: {holder}. Từ chối chạy để tránh hai tiến trình Scrapy cùng ghi một snapshot. "
            "Nếu chắc chắn không còn crawler nào chạy, hãy dừng tiến trình đó hoặc xóa lock file thủ công."
        )

    # -- kiểm tra / cập nhật khi đang giữ lock ---------------------------------
    def verify_held(self) -> None:
        """Xác minh lock trên đĩa vẫn thuộc về instance này (gọi trước khi start subprocess)."""
        if not self.is_held:
            raise CrawlerLockError("Runner lock chưa được acquire; không được khởi động crawl subprocess.")
        try:
            info = self._read_info()
        except FileNotFoundError:
            info = None
        if not info or info.get("token") != self.token:
            raise CrawlerLockError(f"Runner lock {self.path} đã bị mất hoặc đổi chủ; dừng crawl.")

    def register_child(self, pid: int) -> None:
        """Ghi PID của Scrapy child vào lock để runner sau không coi lock là stale khi child mồ côi còn chạy."""
        self.verify_held()
        _, start_token = _query_process(pid)
        self._info["child_pid"] = pid
        self._info["child_start"] = start_token
        self._rewrite_info()

    def clear_child(self) -> None:
        if not self.is_held:
            return
        self._info["child_pid"] = None
        self._info["child_start"] = None
        try:
            self.verify_held()
            self._rewrite_info()
        except (CrawlerLockError, OSError) as exc:
            print(f"[LOCK][CẢNH BÁO] Không thể cập nhật lock sau khi subprocess kết thúc: {exc}")

    def release(self) -> None:
        """Giải phóng lock (idempotent). Chỉ xóa file nếu token trên đĩa vẫn là của instance này."""
        if not self.is_held:
            return
        token = self.token
        self.token = None
        self._info = {}
        try:
            info = self._read_info()
        except FileNotFoundError:
            return
        if info is None or info.get("token") != token:
            print(f"[LOCK][CẢNH BÁO] Lock {self.path} không còn thuộc runner này; không xóa.")
            return
        if not self._unlink_quietly(self.path):
            print(f"[LOCK][CẢNH BÁO] Không thể xóa lock file {self.path}.")


def crawl_category(
    category: str,
    limit: Optional[int] = 50,
    output_file: Optional[str] = None,
    batch_id: Optional[str] = None,
    source: str = "tgdd",
    run_lock: Optional[RunnerLock] = None,
) -> int:
    """
    Chạy spider tương ứng qua subprocess để đảm bảo tiến trình Scrapy / Twisted sạch sẽ.
    Mặc định tạo file immutable raw snapshot dạng <batch_id>.jsonl, bảo toàn snapshot cũ.
    limit=None biểu diễn chế độ FULL CRAWL (unlimited).

    run_lock: runner lock đang được giữ. Nếu None, hàm tự acquire lock cho riêng lần crawl này,
    nên không có đường nào khởi động Scrapy mà không giữ lock.
    """
    if run_lock is None:
        with RunnerLock() as own_lock:
            return crawl_category(
                category,
                limit=limit,
                output_file=output_file,
                batch_id=batch_id,
                source=source,
                run_lock=own_lock,
            )

    src_key = source.lower()
    if src_key not in SOURCE_REGISTRY:
        raise ValueError(f"Không hỗ trợ source: '{source}'. Các source hợp lệ: {list(SOURCE_REGISTRY.keys())}")

    src_config = SOURCE_REGISTRY[src_key]
    if not src_config["implemented"]:
        raise NotImplementedError(
            f"Source '{source}' ({src_config['name']}) đã được đăng ký nhưng crawler chưa được implement."
        )

    spiders = src_config.get("spiders", {})
    if category not in spiders:
        raise ValueError(f"Source '{source}' không hỗ trợ category '{category}'. Hỗ trợ: {list(spiders.keys())}")

    spider_file = spiders[category]
    if not spider_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file spider cho source '{source}', category '{category}': {spider_file}")


    # Xác định batch_id và output paths (product và review riêng biệt)
    actual_batch_id = batch_id or generate_batch_id()
    if output_file:
        target_out = Path(output_file)
        if batch_id is None:
            actual_batch_id = target_out.stem
        review_out = target_out.parent / f"{target_out.stem}_reviews.jsonl"
    else:
        target_out = get_snapshot_path(category, actual_batch_id, source=source)
        review_out = get_review_snapshot_path(category, actual_batch_id, source=source)

    target_out.parent.mkdir(parents=True, exist_ok=True)
    review_out.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_available(target_out)
    ensure_output_path_available(review_out)

    limit_desc = f"giới hạn ~{limit} sản phẩm" if limit is not None else "FULL CRAWL (không giới hạn)"
    print("\n========================================================")
    print(f"BẮT ĐẦU CRAWL: [{source.upper()}] category={category.upper()} ({limit_desc})")
    print(f"Spider: {spider_file.name}")
    print(f"Batch ID: {actual_batch_id}")
    print(f"Product Output: {target_out}")
    print(f"Review Output:  {review_out}")
    print("========================================================\n")

    cmd = [
        sys.executable,
        "-m",
        "scrapy",
        "runspider",
        str(spider_file),
        "-a",
        f"batch_id={actual_batch_id}",
        "-o",
        str(target_out),
        "-a",
        f"review_output={str(review_out)}",
    ]
    if limit is not None:
        cmd.extend(["-a", f"max_products={limit}"])
    else:
        cmd.extend(["-a", "max_products=none"])

    # Xác minh vẫn giữ lock ngay trước khi khởi động Scrapy.
    run_lock.verify_held()
    process = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
    try:
        try:
            run_lock.register_child(process.pid)
        except (CrawlerLockError, OSError):
            process.kill()
            process.wait()
            raise
        returncode = process.wait()
    except BaseException:
        # Giống subprocess.run: không để Scrapy child sống sót khi runner bị gián đoạn (Ctrl+C, lỗi...).
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        run_lock.clear_child()

    if returncode != 0:
        print(f"\n[LỖI] Tiến trình crawl [{source.upper()}] {category.upper()} thoát với mã lỗi: {returncode}")
        return 0

    record_count = 0
    if target_out.exists():
        with open(target_out, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record_count += 1

    review_count = 0
    if review_out.exists():
        with open(review_out, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    review_count += 1

    if record_count > 0:
        print(f"\n[KẾT QUẢ] [{source.upper()}] {category.upper()}: Thu thập thành công {record_count} product/variant records vào {target_out}")
        print(f"                                   và {review_count} review records vào {review_out}\n")
    else:
        print(f"\n[CẢNH BÁO] [{source.upper()}] {category.upper()}: Tiến trình hoàn tất nhưng không có record nào được ghi vào {target_out}\n")

    return record_count


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TV1 - Multi-Source Tech E-Commerce Crawler Runner")
    parser.add_argument(
        "--source",
        choices=list(SOURCE_REGISTRY.keys()) + ["all"],
        default="tgdd",
        help=f"Sàn thương mại điện tử cần crawl ({', '.join(SOURCE_REGISTRY.keys())}, all - mặc định tgdd)",
    )
    parser.add_argument(
        "--category",
        choices=["laptop", "smartphone", "all"],
        default="all",
        help="Danh mục cần crawl (laptop, smartphone, all)",
    )

    # Nhóm mutually exclusive giữa --limit và --full
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Số lượng sản phẩm mục tiêu (mặc định 50 trong chế độ pilot)",
    )
    mode_group.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Thu thập toàn bộ sản phẩm trong danh mục (unlimited, không giới hạn)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="File đầu ra tùy chỉnh (chỉ dùng khi chọn 1 source và 1 category)",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Batch ID tùy chỉnh (mặc định tự động sinh theo timestamp)",
    )
    return parser


def main():
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.full and args.limit is not None:
        parser.error(
            "Không được chỉ định đồng thời cả --full và --limit. "
            "Chọn --full để crawl toàn bộ hoặc --limit <N> để đặt số lượng cụ thể."
        )

    if args.output and (args.category == "all" or args.source == "all"):
        parser.error("Tùy chọn --output chỉ có thể dùng khi crawl 1 source và 1 category cụ thể.")

    if args.source != "all":
        src_key = args.source.lower()
        if src_key not in SOURCE_REGISTRY:
            parser.error(f"Source không hợp lệ: {args.source}")
        if not SOURCE_REGISTRY[src_key]["implemented"]:
            print(
                f"\n[LỖI] Source '{args.source}' ({SOURCE_REGISTRY[src_key]['name']}) "
                "đã được ghi nhận nhưng crawler chưa được implement.\n"
            )
            sys.exit(1)
        sources = [src_key]
    else:
        sources = [s for s, meta in SOURCE_REGISTRY.items() if meta["implemented"]]

    if args.full:
        effective_limit = None
    elif args.limit is not None:
        effective_limit = args.limit
    else:
        effective_limit = 50

    categories = ["laptop", "smartphone"] if args.category == "all" else [args.category]

    # Acquire lock TRƯỚC mọi crawl subprocess, giữ suốt toàn bộ chuỗi source/category
    # (không release giữa Smartphone và Laptop), release trong finally.
    run_lock = RunnerLock(LOCK_FILE_PATH)
    try:
        run_lock.acquire()
    except CrawlerLockError as exc:
        print(f"\n[LỖI][LOCK] {exc}\n")
        sys.exit(LOCK_CONFLICT_EXIT_CODE)

    try:
        start_time = datetime.now()
        results = {}

        try:
            for src in sources:
                for cat in categories:
                    key = f"{src}_{cat}"
                    count = crawl_category(
                        cat,
                        limit=effective_limit,
                        output_file=args.output if len(sources) == 1 and len(categories) == 1 else None,
                        batch_id=args.batch_id,
                        source=src,
                        run_lock=run_lock,
                    )
                    results[key] = count
        except FileExistsError as exc:
            print(f"\n[LỖI] {exc}\n")
            sys.exit(1)
        except NotImplementedError as exc:
            print(f"\n[LỖI] {exc}\n")
            sys.exit(1)
        except CrawlerLockError as exc:
            print(f"\n[LỖI][LOCK] {exc}\n")
            sys.exit(LOCK_CONFLICT_EXIT_CODE)

        duration = datetime.now() - start_time
        mode_label = "FULL CRAWL" if effective_limit is None else f"PILOT CRAWL (limit={effective_limit})"
        print("========================================================")
        print(f"TỔNG HỢP KẾT QUẢ {mode_label}:")
        for key, cnt in results.items():
            status_label = f"{cnt} records" if cnt > 0 else "THẤT BẠI / 0 records"
            print(f"  - {key.upper()}: {status_label}")
        print(f"Thời gian thực hiện: {duration.total_seconds():.1f}s")
        print("========================================================")

        if any(cnt == 0 for cnt in results.values()):
            sys.exit(1)
    finally:
        run_lock.release()


if __name__ == "__main__":
    main()
