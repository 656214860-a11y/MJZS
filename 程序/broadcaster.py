"""三虎的统一进度播报与文本日志。"""
import os
import re
from datetime import datetime

from contract.pet_bus import STAGES


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
