"""Media probing and technical QC helpers."""
import json
import os
import struct
import math
from .core import command
# R3246 轮 2 D2-a：PNG 签名事实下沉 L0 contract.media_signature；
# 这里保留再导出，既有 ``agent.media.is_png``／``PNG_SIGNATURE`` 消费面不变。
from contract.media_signature import PNG_SIGNATURE, is_png  # noqa: F401


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


def image_content_ok(path):
    """导入候选按内容验真：后缀合法但内容不是对应格式的完整图片时返回 False。

    PNG 看签名＋IHDR＋IEND，JPG 看 SOI＋EOI，WEBP 看 RIFF＋WEBP；
    只读头 16 字节与尾 8 字节，不把整图读进内存。
    """
    suffix = os.path.splitext(str(path))[1].lower()
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            head = handle.read(16)
            handle.seek(max(0, size - 8))
            tail = handle.read(8)
    except OSError:
        return False
    if suffix == ".png":
        return (size >= 33 and head.startswith(PNG_SIGNATURE)
                and head[12:16] == b"IHDR" and tail[:4] == b"IEND")
    if suffix in (".jpg", ".jpeg"):
        return size >= 4 and head.startswith(b"\xff\xd8") and tail[-2:] == b"\xff\xd9"
    if suffix == ".webp":
        return size >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
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


def _media_tool(cfg, name):
    """ffmpeg/ffprobe 读取时统一解析：显式有效配置 > 随包 > PATH（R3154）。"""
    from contract.platform_tools import tool_path
    return tool_path(name, configured=(cfg or {}).get(name))


def probe(path, cfg):
    ffprobe = _media_tool(cfg, 'ffprobe')
    if not ffprobe:
        raise ValueError('未找到 FFprobe：请安装 FFmpeg 或在配置中指定路径')
    return json.loads(command([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))


class MediaValidationError(ValueError):
    """输入媒体不符合可导入契约，可向页面展示修复提示。"""


def media_facts(kind, data):
    """实际流类型、有限正时长和画面尺寸的公共技术口径。"""
    if kind not in ('audio', 'video'):
        raise ValueError('不支持的媒体类型')
    if not isinstance(data, dict) or not isinstance(data.get('format'), dict) or not isinstance(data.get('streams'), list):
        raise MediaValidationError('媒体探测结果不完整')
    matching = [item for item in data['streams'] if isinstance(item, dict) and item.get('codec_type') == kind
                and not (kind == 'video' and (item.get('disposition') or {}).get('attached_pic'))]
    try:
        duration = float(data['format'].get('duration', 0))
        sized = kind == 'audio' or any(int(item.get('width', 0)) > 0 and int(item.get('height', 0)) > 0 for item in matching)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MediaValidationError('媒体时长或画面尺寸无效') from exc
    if not matching or not math.isfinite(duration) or duration <= 0 or not sized:
        raise MediaValidationError('媒体缺少有效%s流、时长或画面尺寸' % ('音频' if kind == 'audio' else '视频'))
    return {'kind': kind, 'duration': duration, 'passed': True}


def validate_import(path, cfg, kind):
    """导入时探测并完整解码一次；不将截断文件发布为正式成果。"""
    ffmpeg = _media_tool(cfg, 'ffmpeg')
    ffprobe = _media_tool(cfg, 'ffprobe')
    if not ffprobe or not ffmpeg:
        raise MediaValidationError('请先配置 FFmpeg 和 FFprobe，再导入媒体文件；'
                                   '在项目 config.json 填写「ffmpeg」「ffprobe」路径，'
                                   '「设置 → 开发信息 → 环境自检」可核对')
    try:
        data = probe(path, {'ffprobe': ffprobe})
        facts = media_facts(kind, data)
        if kind == 'video' and cfg.get('require_audio', True) and not any(
                item.get('codec_type') == 'audio' for item in data['streams'] if isinstance(item, dict)):
            raise MediaValidationError('成片缺少必要音轨；无声项目请先将 require_audio 配置为 false')
        maps = ['-map', '0:a'] if kind == 'audio' else ['-map', '0:v', '-map', '0:a?']
        command([ffmpeg, '-nostdin', '-v', 'error', '-xerror', '-err_detect', 'explode',
                 '-i', path, *maps, '-f', 'null', '-'])
        return dict(facts, decoded=True)
    except MediaValidationError:
        raise
    except (RuntimeError, OSError, ValueError) as exc:
        raise MediaValidationError('媒体无法完整解码，请检查文件是否损坏或工具配置是否有效') from exc


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
