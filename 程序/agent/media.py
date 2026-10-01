"""Media probing and technical QC helpers."""
import json
import os
import struct
from .core import command

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def is_png(path):
    """只读 8 字节文件头判断 PNG；不要用 read_bytes() 把整帧读进内存。"""
    with open(path, "rb") as handle:
        return handle.read(8) == PNG_SIGNATURE


def png_complete(path):
    """只读头 8 字节与尾 8 字节，判断 PNG 是否已完整落盘。

    首帧批次每 1.5 秒就会把每个待导入的图检查一遍；整图读进内存既慢又占内存。
    """
    try:
        if os.path.getsize(path) < 33: return False
        with open(path, "rb") as handle:
            if handle.read(8) != PNG_SIGNATURE: return False
            handle.seek(-8, os.SEEK_END)
            return handle.read(4) == b"IEND"
    except OSError:
        return False


def png_size(path):
    """读 24 字节 PNG 文件头拿宽高，顺手校验签名与尺寸。"""
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != PNG_SIGNATURE:
        raise ValueError("首帧必须是PNG图片")
    if len(header) < 24:
        raise ValueError("首帧尺寸无效")
    width, height = struct.unpack(">II", header[16:24])
    if not width or not height:
        raise ValueError("首帧尺寸无效")
    return width, height


def probe(path, cfg):
    return json.loads(command([cfg["ffprobe"], "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))


def check(path, duration, cfg, strict=False):
    p = probe(path, cfg)
    videos = [s for s in p["streams"] if s["codec_type"] == "video"]
    audios = [s for s in p["streams"] if s["codec_type"] == "audio"]
    errors = []
    actual = float(p.get("format", {}).get("duration", 0))
    if not videos:
        errors.append("无视频流")
    if not audios and cfg.get("require_audio", True):
        errors.append("无音轨：必须重新获取有声视频或人工修复")
    if abs(actual - duration) > (0.3 if strict else 0.8):
        errors.append(f"时长 {actual:.2f} 秒，目标 {duration} 秒；先人工修剪/修改镜头，禁止强行补长")
    if strict and videos:
        v = videos[0]
        if (v["width"], v["height"]) != (cfg["width"], cfg["height"]):
            errors.append("分辨率不符")
        numerator, denominator = map(int, v["avg_frame_rate"].split("/"))
        if not denominator or abs(numerator / denominator - cfg["fps"]) > 0.01:
            errors.append("帧率不符")
    return {"duration": actual, "errors": errors}
