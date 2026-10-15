"""Conservative IndexTTS limits; this module never imports or starts a model."""
from functools import lru_cache
import os
import re
import signal
import subprocess
import time

GIB = 1024 ** 3
MAX_TEXT = 200
SEGMENT_CHARS = 40
REFERENCE_SECONDS = 8


class IndexResourceError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def physical_memory():
    result = subprocess.run(['/usr/sbin/sysctl', '-n', 'hw.memsize'],
                            capture_output=True, text=True, timeout=2, check=True)
    return int(result.stdout.strip())


def memory_snapshot():
    """macOS's own memory-pressure estimate, not the tiny raw free-page count."""
    result = subprocess.run(['/usr/bin/memory_pressure', '-Q'], capture_output=True,
                            text=True, timeout=2, check=True)
    match = re.search(r'System-wide memory free percentage:\s*(\d+)%', result.stdout)
    if not match:
        raise ValueError('无法解析 macOS 内存压力')
    return dict(total=physical_memory(), free_percent=int(match[1]))


def limits(total):
    return dict(mps=min(10 * GIB, int(total * .30)),
                rss=min(14 * GIB, int(total * .45)))


def ensure_index_ready(text=None):
    if text is not None and len(text) > MAX_TEXT:
        raise ValueError(f'IndexTTS 稳定模式每次最多 {MAX_TEXT} 字，请分批生成或先按句试听。')
    try:
        snapshot = memory_snapshot()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise IndexResourceError('无法读取系统内存状态，暂不启动 IndexTTS。请稍后重试。') from error
    # Keep at least 10 GiB by this estimate, and at least 35% on larger Macs.
    available = snapshot['total'] * snapshot['free_percent'] / 100
    if snapshot['free_percent'] < 35 or available < 10 * GIB:
        raise IndexResourceError(
            f"IndexTTS 内存保护：系统可用内存比例 {snapshot['free_percent']}%，"
            '当前余量不足，已阻止启动。请关闭占内存的应用后再试，或使用 Kokoro / Spark。')
    return snapshot


def process_rss(pid):
    result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'rss='],
                            capture_output=True, text=True, timeout=2)
    return int(result.stdout.strip() or '0') * 1024


def stop_process(process):
    """Only the model's isolated process group; always reap before another job."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def wait_for_index(process, cancelled, timeout=480):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if cancelled():
                stop_process(process)
                return process.returncode
            if time.monotonic() >= deadline:
                raise IndexResourceError('IndexTTS 本次生成超过 8 分钟，已停止。请缩短文案。')
            try:
                snapshot = memory_snapshot()
                rss = process_rss(process.pid)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                raise IndexResourceError('IndexTTS 内存监测中断，为保护系统已停止本次任务。') from error
            if snapshot['free_percent'] <= 15 or rss > limits(snapshot['total'])['rss']:
                raise IndexResourceError(
                    'IndexTTS 内存保护：运行中内存余量过低或进程占用超限，已停止本次任务。'
                    '请关闭占内存的应用、缩短文案或改用轻量模型。')
