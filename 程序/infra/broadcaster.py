"""三虎的统一进度播报与文本日志。"""
import logging
import os
import re

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
        # 日志写盘走标准库 logging 的文件处理器：自带线程锁，8 路并行播报不会交错；
        # 同一日志路径的多个 Broadcaster 共享同一个 logger，不会重复挂处理器。
        self._logger = logging.getLogger("broadcaster.%s" % os.path.abspath(log_path))
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        if not self._logger.handlers:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
            self._logger.addHandler(handler)

    def broadcast(self, msg):
        """验证三虎前缀后，输出到调用端并写入日志。"""
        message = str(msg)
        if not any(pattern.match(message) for pattern in PREFIX_PATTERNS):
            raise ValueError("三虎播报必须使用规定前缀")
        print(message)
        self._logger.info(message)
        return message

    def close(self):
        """释放日志文件句柄（测试与退出路径用）；调用后再次 broadcast 会静默只打印。"""
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            import contextlib
            with contextlib.suppress(Exception):
                import infra.app_logging as app_logging
                app_logging.swallowed('Broadcaster.__del__')

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
