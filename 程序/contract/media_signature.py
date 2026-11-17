# -*- coding: utf-8 -*-
"""媒体文件签名的 L0 事实契约（R3246 轮 2 D2-a 从 ``agent.media`` 下沉）。

PNG 魔数与「只读 8 字节文件头」的判定是纯文件格式事实，不依赖 Tk、编排或
FFmpeg 探测；``contract.episode_contract``（L0）与 ``image_agent_runner``（L3）
等各层都可以安全复用。完整探测、尺寸解析与导入校验仍在 ``agent.media``（L1）。
"""

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def is_png(path):
    """只读 8 字节文件头判断 PNG；不要用 read_bytes() 把整帧读进内存。"""
    with open(path, "rb") as handle:
        return handle.read(8) == PNG_SIGNATURE
