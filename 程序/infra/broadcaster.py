"""三虎的统一进度播报与文本日志。"""
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from contract.pet_bus import STAGES

_PROGRAM_LOGS = Path(__file__).resolve().parents[1] / 'logs' / 'sanhu_progress.log'
_WARNED = set()
_WARN_LOCK = threading.Lock()


PREFIX_PATTERNS = (
    re.compile(r"^【阶段 [1-9][0-9]*/[1-9][0-9]*】"),
    re.compile(r"^【步骤 [1-9][0-9]*/[1-9][0-9]*】"),
    re.compile(r"^【(?:门禁|警告|阻塞|完成|恢复|下一阶段|模式)】"),
)


class Broadcaster:
    """将阶段消息输出到调用端，并追加写入 UTF-8 日志。"""

    def __init__(self, log_path="logs/sanhu_progress.log"):
        self.log_path = log_path
        directory = os.path.dirname(log_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def broadcast(self, msg):
        """验证三虎前缀后，输出到调用端并写入日志。"""
        message = str(msg)
        if not any(pattern.match(message) for pattern in PREFIX_PATTERNS):
            raise ValueError("三虎播报必须使用规定前缀")
        print(message)
        with open(self.log_path, "a", encoding="utf-8") as handle:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            handle.write(f"{timestamp} {message}\n")
        return message

    @staticmethod
    def stage(current, title):
        """构造阶段播报。"""
        if not 1 <= int(current) <= len(STAGES):
            raise ValueError("阶段序号必须在 1 到 %d 之间" % len(STAGES))
        return f"【阶段 {int(current)}/{len(STAGES)}】{title}"

    @staticmethod
    def step(current, total, title):
        """构造步骤播报。"""
        if not 1 <= int(current) <= int(total):
            raise ValueError("步骤序号必须在有效范围内")
        return f"【步骤 {int(current)}/{int(total)}】{title}"


def warn_once(key, text):
    """同 ``key`` 进程内只发一次 ``【警告】``（产物拒写等需提醒但不弹窗的场景）。

    直接向 ``logs/sanhu_progress.log`` 追加一行（绝对路径，不依赖调用方工作目录），
    不走 ``Broadcaster`` 类——事件总线边界只允许 desktop/pet_ui 实例化它做用户可见
    播报；本函数是属主写路径的内部告警通道，前缀仍取自本模块 ``PREFIX_PATTERNS``。
    任何一步失败都静默返回 False，绝不把写路径带崩。返回是否实际发出。
    """
    try:
        with _WARN_LOCK:
            if key in _WARNED:
                return False
            _WARNED.add(key)
        message = '【警告】' + str(text)
        _PROGRAM_LOGS.parent.mkdir(parents=True, exist_ok=True)
        with open(_PROGRAM_LOGS, 'a', encoding='utf-8') as handle:
            handle.write('%s %s\n' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message))
        return True
    except Exception:
        return False
