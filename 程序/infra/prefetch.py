"""L1 预测性预加载闸门（任务书 I22）。

依据指标中的访问序列，由上层（L4）在窗口可交互后的空闲点调用 ``schedule``
把预取任务投到 ``io`` 池低优先级执行；三道闸门任一不满足即放弃本轮：

- 关闭开关：``data/autotune_disable_prefetch.flag`` 存在则整体停用；
- 内存：``resources.snapshot()`` 可用内存占比低于 ``MEM_MIN_FRACTION``；
- 用户活跃：``active`` 探针返回真（正在操作时让出磁盘带宽）。

调度失败（池满／已关）静默返回 False——预取是可再生优化，失败无损失。
``warm_files`` 是预取任务体：纯文件读取暖 file_cache／系统页缓存，
不触碰 Tk，不递归目录，路径由调用方显式给出（规则 33）。
"""
from pathlib import Path

from contract.infra_errors import QuotaError
from infra import executors, file_cache, resources

__all__ = ['DISABLE_FLAG', 'MEM_MIN_FRACTION', 'enabled', 'schedule', 'warm_files']

PROGRAM = Path(__file__).resolve().parents[1]
DISABLE_FLAG = PROGRAM / 'data' / 'autotune_disable_prefetch.flag'
MEM_MIN_FRACTION = 0.10    # 可用内存占比低于 10% 时暂停预取


def enabled():
    """关闭开关文件存在即停用；I22-3 未改善时放置此文件回滚。"""
    return not DISABLE_FLAG.exists()


def _memory_low(snap):
    mem = snap.get('memory') if isinstance(snap, dict) else None
    if not isinstance(mem, dict):
        return False                          # 'unavailable' 不阻断，宁缺毋滥
    total = mem.get('total') or 0
    available = mem.get('available')
    if not total or available is None:
        return False
    return (available / total) < MEM_MIN_FRACTION


def schedule(fn, *, snapshot=None, active=None, label='prefetch'):
    """三闸过后把 ``fn`` 投到 io 池；任一门不过或池不可用返回 False。

    ``snapshot`` 可为 dict 或返回 dict 的可调用（测试注入资源快照，I22-2）；
    ``active`` 为无参可调用，返回真表示用户正在操作。
    """
    if not enabled():
        return False
    snap = snapshot() if callable(snapshot) else snapshot
    if snap is None:
        snap = resources.snapshot()
    if _memory_low(snap):
        return False
    if callable(active) and active():
        return False
    try:
        executors.submit('io', fn, label=label)
    except QuotaError:
        return False
    return True


def _read_one(path):
    path = Path(path)
    if path.suffix.lower() == '.json':
        file_cache.read_json(path)
    else:
        file_cache.read_text(path, errors='replace')


def warm_files(paths, *, reader=None):
    """预取任务体：逐文件读入缓存（file_cache 暖层＋系统页缓存）。

    二进制／非文本文件按 read_text(errors='replace') 暖系统页缓存；单文件
    失败跳过继续，返回成功预取的个数。不递归，不造路径，调用方给清单。
    """
    read = reader or _read_one
    count = 0
    for path in paths:
        try:
            read(path)
        except (OSError, UnicodeError):
            continue
        count += 1
    return count
