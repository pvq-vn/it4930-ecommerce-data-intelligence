"""
Tests cho runner lock của crawler/run_crawler.py (chống concurrent run / race condition).

Không test nào khởi động Scrapy thật hay crawl mạng: subprocess.Popen / crawl_category đều được thay thế.
Mọi lock file đều nằm trong thư mục tạm, không đụng tới data/raw.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from crawler import run_crawler
from crawler.run_crawler import (
    LOCK_CONFLICT_EXIT_CODE,
    CrawlerLockError,
    RunnerLock,
    _query_process,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _dead_pid() -> int:
    """PID của một process vừa kết thúc."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def _write_lock(path: Path, **overrides) -> dict:
    info = {
        "token": "foreign-token",
        "pid": _dead_pid(),
        "process_start": "win:0",
        "hostname": run_crawler.socket.gethostname(),
        "created_at": "2026-10-15T00:00:00",
        "argv": ["crawler/run_crawler.py", "--source", "cellphones", "--category", "all", "--full"],
        "child_pid": None,
        "child_start": None,
    }
    info.update(overrides)
    path.write_text(json.dumps(info), encoding="utf-8")
    return info


class _LockTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.lock_path = self.tmp / "locks" / ".run_crawler.lock"
        self._locks = []

    def tearDown(self):
        for lock in self._locks:
            lock.release()
        self._tmp.cleanup()

    def make_lock(self, **kwargs) -> RunnerLock:
        lock = RunnerLock(self.lock_path, **kwargs)
        self._locks.append(lock)
        return lock


class TestRunnerLockBasics(_LockTestBase):
    def test_acquire_success_creates_lock_with_owner_info(self):
        lock = self.make_lock().acquire()
        self.assertTrue(lock.is_held)
        self.assertTrue(self.lock_path.exists())
        info = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(info["pid"], os.getpid())
        self.assertEqual(info["token"], lock.token)
        self.assertEqual(info["hostname"], run_crawler.socket.gethostname())
        self.assertIsNone(info["child_pid"])

    def test_second_acquire_is_refused_and_does_not_touch_lock(self):
        first = self.make_lock().acquire()
        before = self.lock_path.read_text(encoding="utf-8")

        second = self.make_lock()
        with self.assertRaises(CrawlerLockError) as ctx:
            second.acquire()
        self.assertIn("đang giữ lock", str(ctx.exception))
        self.assertFalse(second.is_held)
        self.assertEqual(self.lock_path.read_text(encoding="utf-8"), before)
        self.assertTrue(first.is_held)

    def test_same_instance_cannot_acquire_twice(self):
        lock = self.make_lock().acquire()
        with self.assertRaises(CrawlerLockError):
            lock.acquire()

    def test_release_allows_next_runner_to_acquire(self):
        first = self.make_lock().acquire()
        first.release()
        self.assertFalse(first.is_held)
        self.assertFalse(self.lock_path.exists(), "Lock file không được tồn tại sau khi release")

        second = self.make_lock().acquire()
        self.assertTrue(second.is_held)
        self.assertNotEqual(second.token, None)

    def test_release_is_idempotent(self):
        lock = self.make_lock().acquire()
        lock.release()
        lock.release()
        self.assertFalse(self.lock_path.exists())

    def test_release_does_not_delete_lock_owned_by_someone_else(self):
        lock = self.make_lock().acquire()
        foreign = _write_lock(self.lock_path, token="other-owner", pid=os.getpid(), process_start=None)
        with redirect_stdout(io.StringIO()):
            lock.release()
        self.assertTrue(self.lock_path.exists())
        self.assertEqual(json.loads(self.lock_path.read_text(encoding="utf-8"))["token"], foreign["token"])

    def test_context_manager_releases_on_exception(self):
        with self.assertRaises(ValueError):
            with self.make_lock():
                self.assertTrue(self.lock_path.exists())
                raise ValueError("boom")
        self.assertFalse(self.lock_path.exists())

    def test_verify_held_fails_without_acquire(self):
        with self.assertRaises(CrawlerLockError):
            self.make_lock().verify_held()

    def test_register_and_clear_child_keep_lock_owned(self):
        lock = self.make_lock().acquire()
        lock.register_child(os.getpid())
        info = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(info["child_pid"], os.getpid())
        self.assertEqual(info["token"], lock.token)
        lock.clear_child()
        info = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertIsNone(info["child_pid"])
        self.assertEqual(info["token"], lock.token)


class TestProcessQuery(unittest.TestCase):
    def test_current_process_is_alive(self):
        alive, start = _query_process(os.getpid())
        self.assertTrue(alive)
        if os.name == "nt":
            self.assertTrue(start and start.startswith("win:"))

    def test_finished_process_is_dead(self):
        alive, _ = _query_process(_dead_pid())
        self.assertFalse(alive)

    def test_invalid_pid_is_dead(self):
        self.assertFalse(_query_process(0)[0])
        self.assertFalse(_query_process(-5)[0])


class TestStaleLock(_LockTestBase):
    def _acquire_quietly(self, lock: RunnerLock) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            lock.acquire()
        return buf.getvalue()

    def test_lock_of_dead_runner_is_reclaimed(self):
        self.lock_path.parent.mkdir(parents=True)
        _write_lock(self.lock_path)
        lock = self.make_lock()
        out = self._acquire_quietly(lock)
        self.assertIn("stale lock", out)
        info = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(info["pid"], os.getpid())
        self.assertEqual(info["token"], lock.token)
        self.assertFalse(lock.breaker_path.exists())

    def test_reused_pid_with_different_start_time_is_stale(self):
        if os.name != "nt":
            self.skipTest("start-time token chỉ được đảm bảo trên Windows")
        self.lock_path.parent.mkdir(parents=True)
        # PID đang sống (chính test process) nhưng start time khác -> PID bị tái sử dụng.
        _write_lock(self.lock_path, pid=os.getpid(), process_start="win:1")
        lock = self.make_lock()
        self._acquire_quietly(lock)
        self.assertTrue(lock.is_held)

    def test_live_runner_lock_is_not_stale(self):
        self.lock_path.parent.mkdir(parents=True)
        _, start = _query_process(os.getpid())
        _write_lock(self.lock_path, pid=os.getpid(), process_start=start)
        with self.assertRaises(CrawlerLockError):
            self.make_lock().acquire()
        self.assertTrue(self.lock_path.exists())

    def test_dead_runner_with_orphan_scrapy_child_still_blocks(self):
        """Runner bị kill nhưng Scrapy child còn chạy -> lock KHÔNG được coi là stale."""
        self.lock_path.parent.mkdir(parents=True)
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            _, child_start = _query_process(child.pid)
            _write_lock(self.lock_path, child_pid=child.pid, child_start=child_start)
            with self.assertRaises(CrawlerLockError) as ctx:
                self.make_lock().acquire()
            self.assertIn("Scrapy child", str(ctx.exception))
        finally:
            child.kill()
            child.wait()
        # Khi child cũng đã chết -> stale -> được thu hồi.
        lock = self.make_lock()
        self._acquire_quietly(lock)
        self.assertTrue(lock.is_held)

    def test_fresh_unreadable_lock_is_not_stale(self):
        self.lock_path.parent.mkdir(parents=True)
        self.lock_path.write_text("", encoding="utf-8")  # holder có thể đang ghi
        with self.assertRaises(CrawlerLockError):
            self.make_lock().acquire()
        self.assertTrue(self.lock_path.exists())

    def test_old_unreadable_lock_is_stale(self):
        self.lock_path.parent.mkdir(parents=True)
        self.lock_path.write_text("{not json", encoding="utf-8")
        old = time.time() - 3600
        os.utime(self.lock_path, (old, old))
        lock = self.make_lock()
        self._acquire_quietly(lock)
        self.assertTrue(lock.is_held)

    def test_lock_from_other_host_is_never_auto_removed(self):
        self.lock_path.parent.mkdir(parents=True)
        _write_lock(self.lock_path, hostname="some-other-machine")
        with self.assertRaises(CrawlerLockError) as ctx:
            self.make_lock().acquire()
        self.assertIn("host khác", str(ctx.exception))
        self.assertTrue(self.lock_path.exists())

    def test_active_breaker_blocks_stale_recovery(self):
        self.lock_path.parent.mkdir(parents=True)
        _write_lock(self.lock_path)
        lock = self.make_lock()
        lock.breaker_path.write_text("12345", encoding="utf-8")
        with self.assertRaises(CrawlerLockError):
            lock.acquire()
        self.assertTrue(self.lock_path.exists())

    def test_abandoned_breaker_is_cleaned_up(self):
        self.lock_path.parent.mkdir(parents=True)
        _write_lock(self.lock_path)
        lock = self.make_lock(breaker_stale_seconds=1)
        lock.breaker_path.write_text("12345", encoding="utf-8")
        old = time.time() - 3600
        os.utime(lock.breaker_path, (old, old))
        self._acquire_quietly(lock)
        self.assertTrue(lock.is_held)
        self.assertFalse(lock.breaker_path.exists())

    def test_stale_recovery_does_not_delete_a_newer_valid_lock(self):
        """Runner B thấy stale lock cũ, nhưng A đã thay bằng lock mới -> B không được xóa lock của A."""
        self.lock_path.parent.mkdir(parents=True)
        stale_info = _write_lock(self.lock_path, token="stale-token")
        runner_a = self.make_lock()
        with redirect_stdout(io.StringIO()):
            runner_a.acquire()  # A thu hồi stale lock và giữ lock mới
        runner_b = self.make_lock()
        runner_b._break_stale_lock(stale_info["token"])  # B hành động dựa trên thông tin cũ
        info = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(info["token"], runner_a.token)


class TestCrossProcessLock(_LockTestBase):
    HOLDER_CODE = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from crawler.run_crawler import RunnerLock\n"
        "lock = RunnerLock(Path(sys.argv[1])).acquire()\n"
        "print('LOCKED', flush=True)\n"
        "time.sleep(float(sys.argv[2]))\n"
        "lock.release()\n"
        "print('RELEASED', flush=True)\n"
    )

    def _start_holder(self, hold_seconds: float) -> subprocess.Popen:
        proc = subprocess.Popen(
            [sys.executable, "-c", self.HOLDER_CODE, str(self.lock_path), str(hold_seconds)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            text=True,
        )
        line = proc.stdout.readline().strip()
        self.assertEqual(line, "LOCKED")
        return proc

    def test_lock_held_by_other_process_is_refused_then_reclaimed_after_kill(self):
        holder = self._start_holder(60)
        try:
            with self.assertRaises(CrawlerLockError):
                self.make_lock().acquire()
        finally:
            holder.kill()  # mô phỏng process chết bất thường (không chạy finally)
            holder.wait()
            holder.stdout.close()
        self.assertTrue(self.lock_path.exists(), "Lock của process bị kill vẫn còn trên đĩa")
        lock = self.make_lock()
        with redirect_stdout(io.StringIO()):
            lock.acquire()
        self.assertTrue(lock.is_held)

    def test_lock_released_by_other_process_can_be_acquired(self):
        holder = self._start_holder(0.5)
        out, _ = holder.communicate(timeout=30)
        self.assertIn("RELEASED", out)
        self.assertFalse(self.lock_path.exists())
        self.assertTrue(self.make_lock().acquire().is_held)

    def test_second_runner_main_exits_before_starting_scrapy(self):
        """Một run_crawler.main() thật ở process khác bị từ chối và không bao giờ gọi Popen."""
        held = self.make_lock().acquire()
        code = (
            "import sys, subprocess\n"
            "from pathlib import Path\n"
            "from crawler import run_crawler\n"
            "run_crawler.LOCK_FILE_PATH = Path(sys.argv[1])\n"
            "def _forbidden(*a, **k):\n"
            "    print('SCRAPY_STARTED', flush=True)\n"
            "    raise SystemExit(99)\n"
            "subprocess.Popen = _forbidden\n"
            "subprocess.run = _forbidden\n"
            "sys.argv = ['run_crawler.py', '--source', 'cellphones', '--category', 'all', '--full']\n"
            "run_crawler.main()\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, str(self.lock_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        self.assertEqual(proc.returncode, LOCK_CONFLICT_EXIT_CODE, proc.stdout + proc.stderr)
        self.assertNotIn("SCRAPY_STARTED", proc.stdout)
        self.assertIn("LOCK", proc.stdout)
        # Lock của runner đầu tiên vẫn nguyên vẹn.
        info = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(info["token"], held.token)


class TestMainHoldsLockForWholeSequence(_LockTestBase):
    def _run_main(self, argv, fake_crawl):
        with mock.patch.object(run_crawler, "LOCK_FILE_PATH", self.lock_path), \
                mock.patch.object(run_crawler, "crawl_category", side_effect=fake_crawl) as m_crawl, \
                mock.patch.object(sys, "argv", ["run_crawler.py"] + argv), \
                redirect_stdout(io.StringIO()):
            try:
                run_crawler.main()
                exit_code = 0
            except SystemExit as exc:
                exit_code = exc.code
        return m_crawl, exit_code

    def _recording_fake(self, calls):
        def fake(category, **kwargs):
            lock = kwargs["run_lock"]
            self.assertTrue(lock.is_held)
            lock.verify_held()
            info = json.loads(self.lock_path.read_text(encoding="utf-8"))
            self.assertEqual(info["pid"], os.getpid())
            # Một runner khác phải bị từ chối tại mọi thời điểm của sequence.
            with self.assertRaises(CrawlerLockError):
                RunnerLock(self.lock_path).acquire()
            calls.append((kwargs["source"], category, info["token"]))
            return 1
        return fake

    def test_source_all_holds_single_lock_across_all_crawls(self):
        calls = []
        m_crawl, code = self._run_main(["--source", "all", "--category", "all", "--limit", "1"],
                                       self._recording_fake(calls))
        self.assertEqual(code, 0)
        self.assertEqual(m_crawl.call_count, 6)
        self.assertEqual(
            [(s, c) for s, c, _ in calls],
            [("tgdd", "laptop"), ("tgdd", "smartphone"),
             ("fptshop", "laptop"), ("fptshop", "smartphone"),
             ("cellphones", "laptop"), ("cellphones", "smartphone")],
        )
        self.assertEqual(len({t for _, _, t in calls}), 1, "Lock bị release/acquire lại giữa các crawl")
        self.assertFalse(self.lock_path.exists(), "Lock phải được release sau khi runner kết thúc")

    def test_cellphones_category_all_is_protected_across_laptop_and_smartphone(self):
        calls = []
        m_crawl, code = self._run_main(["--source", "cellphones", "--category", "all", "--full"],
                                       self._recording_fake(calls))
        self.assertEqual(code, 0)
        self.assertEqual([(s, c) for s, c, _ in calls], [("cellphones", "laptop"), ("cellphones", "smartphone")])
        self.assertEqual(calls[0][2], calls[1][2])
        for call in m_crawl.call_args_list:
            self.assertIsNone(call.kwargs["limit"])
        self.assertFalse(self.lock_path.exists())

    def test_lock_released_when_crawl_fails(self):
        _, code = self._run_main(["--source", "cellphones", "--category", "laptop"], lambda c, **k: 0)
        self.assertEqual(code, 1)
        self.assertFalse(self.lock_path.exists())

    def test_lock_released_when_crawl_raises(self):
        def boom(category, **kwargs):
            raise RuntimeError("subprocess exploded")
        with self.assertRaises(RuntimeError):
            self._run_main(["--source", "tgdd", "--category", "all"], boom)
        self.assertFalse(self.lock_path.exists())

    def test_lock_released_on_file_exists_error(self):
        def exists(category, **kwargs):
            raise FileExistsError("snapshot exists")
        _, code = self._run_main(["--source", "fptshop", "--category", "all"], exists)
        self.assertEqual(code, 1)
        self.assertFalse(self.lock_path.exists())

    def test_second_runner_refused_before_any_crawl(self):
        held = self.make_lock().acquire()
        with mock.patch.object(run_crawler.subprocess, "Popen") as m_popen:
            m_crawl, code = self._run_main(["--source", "cellphones", "--category", "all", "--full"],
                                           lambda c, **k: 1)
        self.assertEqual(code, LOCK_CONFLICT_EXIT_CODE)
        m_crawl.assert_not_called()
        m_popen.assert_not_called()
        self.assertEqual(json.loads(self.lock_path.read_text(encoding="utf-8"))["token"], held.token)

    def test_help_does_not_need_lock(self):
        with mock.patch.object(run_crawler, "LOCK_FILE_PATH", self.lock_path), \
                mock.patch.object(sys, "argv", ["run_crawler.py", "--help"]), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                run_crawler.main()
        self.assertEqual(ctx.exception.code, 0)
        self.assertFalse(self.lock_path.exists())


class _FakePopen:
    """Thay subprocess.Popen: ghi 1 record vào output, kiểm tra lock trong lúc 'Scrapy' chạy."""

    instances = []

    def __init__(self, cmd, cwd=None, returncode=0, lock_path=None, test=None):
        self.cmd = cmd
        self.cwd = cwd
        self.pid = os.getpid()
        self.returncode = returncode
        self._lock_path = lock_path
        self._test = test
        self.killed = False
        _FakePopen.instances.append(self)

    def wait(self, timeout=None):
        info = json.loads(self._lock_path.read_text(encoding="utf-8"))
        self._test.assertEqual(info["child_pid"], self.pid, "Scrapy child PID phải được ghi vào lock")
        out = Path(self.cmd[self.cmd.index("-o") + 1])
        if self.returncode == 0:
            out.write_text('{"id": 1}\n', encoding="utf-8")
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True


class TestCrawlCategoryWithLock(_LockTestBase):
    """Regression: lệnh Scrapy cho TGDĐ/FPTShop/CellphoneS giữ nguyên, chỉ thêm lock."""

    EXPECTED_SPIDERS = {
        ("tgdd", "laptop"): ("tgdd", "tgdd_laptop_spider.py"),
        ("tgdd", "smartphone"): ("tgdd", "tgdd_smartphone_spider.py"),
        ("fptshop", "laptop"): ("fptshop", "fptshop_laptop_spider.py"),
        ("fptshop", "smartphone"): ("fptshop", "fptshop_smartphone_spider.py"),
        ("cellphones", "laptop"): ("cellphoneS", "cellphones_laptop_spider.py"),
        ("cellphones", "smartphone"): ("cellphoneS", "cellphones_smartphone_spider.py"),
    }

    def _popen_factory(self, returncode=0):
        def factory(cmd, cwd=None):
            return _FakePopen(cmd, cwd=cwd, returncode=returncode, lock_path=self.lock_path, test=self)
        return factory

    def test_command_unchanged_for_all_sources_and_lock_tracks_child(self):
        lock = self.make_lock().acquire()
        for (source, category), (folder, spider) in self.EXPECTED_SPIDERS.items():
            with self.subTest(source=source, category=category):
                _FakePopen.instances = []
                out = self.tmp / f"{source}_{category}" / "20261015_000000.jsonl"
                with mock.patch.object(run_crawler.subprocess, "Popen", side_effect=self._popen_factory()), \
                        redirect_stdout(io.StringIO()):
                    count = run_crawler.crawl_category(
                        category, limit=5, output_file=str(out), batch_id="B1", source=source, run_lock=lock
                    )
                self.assertEqual(count, 1)
                proc = _FakePopen.instances[0]
                expected = [
                    sys.executable, "-m", "scrapy", "runspider",
                    str(PROJECT_ROOT / "crawler" / folder / spider),
                    "-a", "batch_id=B1",
                    "-o", str(out),
                    "-a", f"review_output={out.parent / (out.stem + '_reviews.jsonl')}",
                    "-a", "max_products=5",
                ]
                self.assertEqual(proc.cmd, expected)
                self.assertEqual(proc.cwd, str(PROJECT_ROOT))
                info = json.loads(self.lock_path.read_text(encoding="utf-8"))
                self.assertIsNone(info["child_pid"], "child_pid phải được xóa sau khi subprocess kết thúc")
                self.assertEqual(info["token"], lock.token)

    def test_full_mode_passes_max_products_none(self):
        lock = self.make_lock().acquire()
        _FakePopen.instances = []
        out = self.tmp / "full" / "B2.jsonl"
        with mock.patch.object(run_crawler.subprocess, "Popen", side_effect=self._popen_factory()), \
                redirect_stdout(io.StringIO()):
            run_crawler.crawl_category("smartphone", limit=None, output_file=str(out), source="cellphones",
                                       run_lock=lock)
        self.assertEqual(_FakePopen.instances[0].cmd[-2:], ["-a", "max_products=none"])

    def test_nonzero_exit_returns_zero_and_keeps_lock(self):
        lock = self.make_lock().acquire()
        out = self.tmp / "fail" / "B3.jsonl"
        with mock.patch.object(run_crawler.subprocess, "Popen", side_effect=self._popen_factory(returncode=1)), \
                redirect_stdout(io.StringIO()):
            count = run_crawler.crawl_category("laptop", limit=1, output_file=str(out), source="tgdd",
                                               run_lock=lock)
        self.assertEqual(count, 0)
        self.assertTrue(lock.is_held)
        lock.verify_held()

    def test_refuses_to_start_scrapy_with_unheld_lock(self):
        lock = self.make_lock()  # chưa acquire
        out = self.tmp / "nolock" / "B4.jsonl"
        with mock.patch.object(run_crawler.subprocess, "Popen") as m_popen, redirect_stdout(io.StringIO()):
            with self.assertRaises(CrawlerLockError):
                run_crawler.crawl_category("laptop", limit=1, output_file=str(out), source="tgdd", run_lock=lock)
        m_popen.assert_not_called()

    def test_refuses_to_start_scrapy_when_lock_was_lost(self):
        lock = self.make_lock().acquire()
        _write_lock(self.lock_path, token="someone-else", pid=os.getpid(), process_start=None)
        out = self.tmp / "lost" / "B5.jsonl"
        with mock.patch.object(run_crawler.subprocess, "Popen") as m_popen, redirect_stdout(io.StringIO()):
            with self.assertRaises(CrawlerLockError):
                run_crawler.crawl_category("laptop", limit=1, output_file=str(out), source="tgdd", run_lock=lock)
        m_popen.assert_not_called()
        lock.token = None  # tránh release in tearDown (lock không còn của mình)

    def test_without_explicit_lock_acquires_own_and_releases(self):
        out = self.tmp / "own" / "B6.jsonl"
        with mock.patch.object(run_crawler, "LOCK_FILE_PATH", self.lock_path), \
                mock.patch.object(run_crawler.subprocess, "Popen", side_effect=self._popen_factory()), \
                redirect_stdout(io.StringIO()):
            count = run_crawler.crawl_category("laptop", limit=1, output_file=str(out), source="fptshop")
        self.assertEqual(count, 1)
        self.assertFalse(self.lock_path.exists())

    def test_without_explicit_lock_refused_when_other_runner_holds_it(self):
        self.make_lock().acquire()
        out = self.tmp / "own2" / "B7.jsonl"
        with mock.patch.object(run_crawler, "LOCK_FILE_PATH", self.lock_path), \
                mock.patch.object(run_crawler.subprocess, "Popen") as m_popen:
            with self.assertRaises(CrawlerLockError):
                run_crawler.crawl_category("laptop", limit=1, output_file=str(out), source="cellphones")
        m_popen.assert_not_called()

    def test_child_killed_and_lock_cleaned_on_interrupt(self):
        lock = self.make_lock().acquire()
        out = self.tmp / "intr" / "B8.jsonl"

        class InterruptedPopen(_FakePopen):
            def wait(self, timeout=None):
                if self.killed:
                    return -9
                raise KeyboardInterrupt  # mô phỏng Ctrl+C trong lúc Scrapy chạy

            def poll(self):
                return -9 if self.killed else None

        procs = []

        def factory(cmd, cwd=None):
            p = InterruptedPopen(cmd, cwd=cwd, lock_path=self.lock_path, test=self)
            procs.append(p)
            return p

        with mock.patch.object(run_crawler.subprocess, "Popen", side_effect=factory), redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                run_crawler.crawl_category("laptop", limit=1, output_file=str(out), source="tgdd", run_lock=lock)
        self.assertTrue(procs[0].killed)
        info = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertIsNone(info["child_pid"])


if __name__ == "__main__":
    unittest.main()
