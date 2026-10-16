"""正式交付规格与预演预览规格（L0）。

从 `script_contract` 拆出（R1618／Q9）：画幅／分辨率／帧率、等比缩放的输出滤镜、
音量与内嵌说明字幕规则属于"成片交付规格"这一件事，与剧本契约无关。

`script_contract` 仍按原名转发本模块的公开名（兼容既有 `script_contract.resolve_output_spec`
等调用）。
"""
from __future__ import annotations

import re


# O32：正式交付规格与预演预览规格分开。规格来自项目制作锁（brief.production_locks 与统筹
# workflow.lock 同源）；缺省才回落到出厂默认。预演只降分辨率与帧率，画幅仍跟项目，
# 保证竖屏／方屏／宽幅输入都不会被默默压成横屏（等比缩小后居中留边，绝不裁切）。
OUTPUT_SPEC_DEFAULTS = {'aspect_ratio': '16:9', 'resolution': '1920x1080', 'fps': 30}
PREVIEW_SHORT_EDGE = 720
PREVIEW_FPS = 24
LOUDNESS_DEFAULTS = {'i': -16, 'tp': -1.5, 'lra': 11}


def parse_ratio(text):
    """'16:9' -> (16.0, 9.0)；认不出来返回 None。"""
    parts = str(text or '').strip().split(':')
    if len(parts) != 2:
        return None
    try:
        width, height = (float(part) for part in parts)
    except ValueError:
        return None
    return (width, height) if width > 0 and height > 0 else None


def parse_resolution(text):
    """'1920x1080' -> (1920, 1080)；认不出来返回 None。"""
    match = re.fullmatch(r'\s*(\d{2,5})\s*[xX*]\s*(\d{2,5})\s*', str(text or ''))
    if not match:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    return (width, height) if width > 0 and height > 0 else None


def _even(value):
    """H.264 yuv420p 要求宽高是偶数；就近取偶，至少 2。"""
    value = max(2, int(round(float(value))))
    return value if value % 2 == 0 else value + 1


def _fit_ratio(width, height, short_edge):
    """按短边缩放：横屏定高、竖屏定宽、方屏同边。"""
    if width >= height:
        return _even(width * short_edge / height), _even(short_edge)
    return _even(short_edge), _even(height * short_edge / width)


def _fps(value, fallback):
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        number = float(fallback)
    if not 1 <= number <= 120:
        number = float(fallback)
    return int(round(number)) if abs(number - round(number)) < 0.01 else round(number, 3)


def resolve_output_spec(locks=None):
    """正式交付规格：画幅／分辨率／帧率。

    三者都优先取锁里的显式值；分辨率没写就按画幅与 1080 短边推算，保证成片盒子跟项目画幅
    一致。锁里没写帧率时用出厂默认。锁第二层键由统筹定义，本契约不列举，故 resolution／fps
    只是可选覆盖，不影响既有画幅优先级。
    """
    locks = locks if isinstance(locks, dict) else {}
    ratio = parse_ratio(locks.get('aspect_ratio')) or parse_ratio(OUTPUT_SPEC_DEFAULTS['aspect_ratio'])
    declared = parse_resolution(locks.get('resolution'))
    if declared:
        width, height = _even(declared[0]), _even(declared[1])
    else:
        width, height = _fit_ratio(ratio[0], ratio[1], 1080)
    return {'aspect_ratio': '%g:%g' % ratio, 'resolution': '%dx%d' % (width, height),
            'width': width, 'height': height,
            'fps': _fps(locks.get('fps'), OUTPUT_SPEC_DEFAULTS['fps']),
            'loudness': dict(LOUDNESS_DEFAULTS)}


def preview_spec(locks=None):
    """预演预览规格：只把分辨率与帧率降下来，画幅仍跟项目（16:9 仍是 1280x720／24）。"""
    spec = resolve_output_spec(locks)
    width, height = _fit_ratio(*(parse_ratio(spec['aspect_ratio']) or (16, 9)), PREVIEW_SHORT_EDGE)
    return dict(spec, resolution='%dx%d' % (width, height), width=width, height=height, fps=PREVIEW_FPS)


def output_filter(spec):
    """把任意输入等比缩小后居中留边（letterbox）到规格盒子；只留边不裁切。"""
    width, height, fps = spec['width'], spec['height'], spec['fps']
    return ('scale=%d:%d:force_original_aspect_ratio=decrease,'
            'pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=%s,format=yuv420p'
            % (width, height, width, height, fps))


def loudness_filter(spec):
    """音量规则跟着输出规格走，不再散落在编码参数里。"""
    loudness = spec.get('loudness') or LOUDNESS_DEFAULTS
    return 'loudnorm=I=%s:TP=%s:LRA=%s' % (loudness.get('i', -16), loudness.get('tp', -1.5),
                                           loudness.get('lra', 11))


def overlay_metrics(spec):
    """成片内嵌说明字幕的安全边距与字号：随输出高度等比，竖屏不会被裁。"""
    edge = max(8, int(round(spec['height'] * 0.042)))
    return {'fontsize': max(12, int(round(spec['height'] * 0.039))), 'x': edge, 'y': edge}


def describe_output_spec(spec):
    """给界面／报告的一行实际规格。"""
    return '%s · %sfps · %s' % (spec['resolution'], spec['fps'], spec['aspect_ratio'])
