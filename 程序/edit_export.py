# -*- coding: utf-8 -*-
"""剪辑软件交付出口：把成片所用镜头排成 EDL（CMX3600）、FCPXML 与分轨素材清单文本。

只生成文本，不写文件、不调用任何剪辑软件；写盘由 L3 `engine` 经 `agent.core.save_text`
完成。时间码为非丢帧（按整数帧率取整），累计用帧数相加，避免逐镜四舍五入漂移。
剪映草稿格式没有公开稳定规范，不在此臆造；达芬奇／Premiere 等可直接导入 EDL 或 FCPXML。
"""
from __future__ import annotations



def escape(text):
    """XML 文本转义。随附的精简解释器没有 xml.sax，所以不用 saxutils。"""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def quoteattr(text):
    """XML 属性值转义并加双引号，换行与制表符转成字符引用，与 saxutils.quoteattr 行为一致。"""
    value = escape(text).replace('"', '&quot;')
    return '"' + value.replace('\n', '&#10;').replace('\r', '&#13;').replace('\t', '&#9;') + '"'

EDL_NAME = '剪辑清单.edl'
FCPXML_NAME = '剪辑清单.fcpxml'
TRACKS_NAME = '分轨素材清单.json'


def nominal_fps(fps):
    try:
        value = int(round(float(fps)))
    except (TypeError, ValueError):
        value = 24
    return value if value > 0 else 24


def frames_of(seconds, fps):
    try:
        return max(1, int(round(float(seconds) * nominal_fps(fps))))
    except (TypeError, ValueError):
        raise ValueError('镜头时长不是有效数字：%r' % (seconds,))


def timecode(frames, fps):
    base = nominal_fps(fps)
    frames = int(frames)
    return '%02d:%02d:%02d:%02d' % (frames // (base * 3600), frames // (base * 60) % 60,
                                    frames // base % 60, frames % base)


def layout(clips, fps):
    """给每个片段算出时间线起止帧；clips 为 [{'shot','file','duration',...}]。"""
    rows, cursor = [], 0
    for clip in clips:
        length = frames_of(clip.get('duration'), fps)
        rows.append(dict(clip, start=cursor, frames=length, end=cursor + length))
        cursor += length
    return rows


def build_edl(title, clips, fps):
    rows = layout(clips, fps)
    lines = ['TITLE: ' + str(title or '成片'), 'FCM: NON-DROP FRAME', '']
    for index, row in enumerate(rows, 1):
        lines.append('%03d  AX       AA/V  C        %s %s %s %s' % (
            index, timecode(0, fps), timecode(row['frames'], fps),
            timecode(row['start'], fps), timecode(row['end'], fps)))
        lines.append('* FROM CLIP NAME: ' + str(row['file']))
        lines.append('* COMMENT: ' + str(row['shot']))
        lines.append('')
    return '\n'.join(lines)


def build_fcpxml(title, clips, spec):
    fps = nominal_fps(spec.get('fps'))
    rows = layout(clips, fps)
    total = rows[-1]['end'] if rows else 0
    width, height = int(spec.get('width') or 1920), int(spec.get('height') or 1080)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<fcpxml version="1.9">', '  <resources>',
           '    <format id="r1" name="FFVideoFormat%dx%dp%d" frameDuration="1/%ds" width="%d" height="%d"/>'
           % (width, height, fps, fps, width, height)]
    for index, row in enumerate(rows, 2):
        out.append('    <asset id="r%d" name=%s start="0s" duration="%d/%ds" hasVideo="1" hasAudio="1" format="r1">'
                   % (index, quoteattr(str(row['shot'])), row['frames'], fps))
        out.append('      <media-rep kind="original-media" src=%s/>' % quoteattr(str(row['file'])))
        out.append('    </asset>')
    out += ['  </resources>', '  <library>', '    <event name=%s>' % quoteattr(str(title or '成片')),
            '      <project name=%s>' % quoteattr(str(title or '成片')),
            '        <sequence format="r1" duration="%d/%ds" tcStart="0s" tcFormat="NDF">' % (total, fps),
            '          <spine>']
    for index, row in enumerate(rows, 2):
        out.append('            <asset-clip ref="r%d" name=%s offset="%d/%ds" start="0s" duration="%d/%ds"/>'
                   % (index, quoteattr(str(row['shot'])), row['start'], fps, row['frames'], fps))
    out += ['          </spine>', '        </sequence>', '      </project>', '    </event>', '  </library>',
            '</fcpxml>', '']
    return '\n'.join(out)


def build_tracks(clips, fps, sources=None):
    """分轨素材清单：每个片段的镜头、文件、时间线位置与来源版本摘要。"""
    sources = sources or {}
    rows = layout(clips, fps)
    return {'fps': nominal_fps(fps), 'total_frames': rows[-1]['end'] if rows else 0,
            'clips': [{'shot': row['shot'], 'file': row['file'], 'start': timecode(row['start'], fps),
                       'end': timecode(row['end'], fps), 'frames': row['frames'],
                       'source_version': (sources.get(row['shot']) or {}).get('version'),
                       'source_sha256': (sources.get(row['shot']) or {}).get('sha256')} for row in rows]}


def export_texts(title, clips, spec, sources=None):
    """返回 {文件名: 文本}；clips 为空时抛错，调用方负责写盘。"""
    if not clips:
        raise ValueError('没有可导出的片段')
    return {EDL_NAME: build_edl(title, clips, spec.get('fps')),
            FCPXML_NAME: build_fcpxml(title, clips, spec),
            TRACKS_NAME: build_tracks(clips, spec.get('fps'), sources)}


EDITS_NAME = 'edits.json'
TRANSITIONS = {'none': '无转场', 'fade': '淡入淡出', 'dissolve': '叠化', 'wipeleft': '向左擦除',
               'slideleft': '向左滑动'}
DEFAULT_TRANSITION_SECONDS = 0.5
MAX_TRANSITION_SECONDS = 2.0
DEFAULT_MUSIC_VOLUME = 0.25


def _number(value, fallback, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number or not low <= number <= high:
        return fallback
    return round(number, 3)


def normalize_edits(raw):
    """用户设置（转场／配乐）归一：未知转场退回无转场，音量与时长越界退回默认。"""
    raw = raw if isinstance(raw, dict) else {}
    transition = raw.get('transition') if isinstance(raw.get('transition'), dict) else {}
    music = raw.get('music') if isinstance(raw.get('music'), dict) else {}
    kind = transition.get('kind')
    return {'transition': {'kind': kind if kind in TRANSITIONS else 'none',
                           'seconds': _number(transition.get('seconds'), DEFAULT_TRANSITION_SECONDS,
                                              0.1, MAX_TRANSITION_SECONDS)},
            'music': {'file': str(music.get('file') or ''),
                      'volume': _number(music.get('volume'), DEFAULT_MUSIC_VOLUME, 0.0, 1.0)}}


def transition_seconds(durations, kind, seconds):
    """实际生效的转场时长：不超过最短镜头的一半，保证相邻两次转场不重叠；无转场返回 0。"""
    if kind not in TRANSITIONS or kind == 'none' or len(durations) < 2:
        return 0.0
    return max(0.0, min(float(seconds), min(durations) / 2))


def transition_filter(durations, kind, seconds):
    """相邻镜头间的 xfade／acrossfade 滤镜链，输出标签 [v][a]；不足两镜或无转场返回 None。

    偏移按「已累计时长－已吃掉的重叠」算。
    """
    seconds = transition_seconds(durations, kind, seconds)
    if seconds <= 0:
        return None
    video, audio, elapsed = '[0:v]', '[0:a]', 0.0
    parts = []
    for index in range(1, len(durations)):
        elapsed += durations[index - 1]
        offset = round(elapsed - seconds * index, 3)
        last = index == len(durations) - 1
        out_v, out_a = ('[v]', '[a]') if last else ('[v%d]' % index, '[a%d]' % index)
        parts.append('%s[%d:v]xfade=transition=%s:duration=%s:offset=%s%s'
                     % (video, index, kind, seconds, offset, out_v))
        parts.append('%s[%d:a]acrossfade=d=%s%s' % (audio, index, seconds, out_a))
        video, audio = out_v, out_a
    return ';'.join(parts)


def music_filter(volume):
    """成片音轨(0:a)与循环背景音乐(1:a)混合；背景音乐压低，成片时长为准。"""
    return ('[1:a]volume=%s[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]'
            % volume)


PLATFORMS = {
    'douyin': {'label': '抖音', 'width': 1080, 'height': 1920, 'fps': 30, 'bitrate': '8M', 'aspect': '9:16'},
    'bilibili': {'label': 'B站', 'width': 1920, 'height': 1080, 'fps': 30, 'bitrate': '12M', 'aspect': '16:9'},
    'youtube': {'label': 'YouTube', 'width': 3840, 'height': 2160, 'fps': 30, 'bitrate': '45M', 'aspect': '16:9'},
}


def platform_spec(name):
    """平台导出规范表：后期页的真实转码与 SKILL 工具共用这一份（custom 取 B 站规格再由调用方覆盖）。"""
    key = str(name or '').strip().lower()
    if key == 'custom':
        return dict(PLATFORMS['bilibili'], label='自定义', key='custom')
    if key in PLATFORMS:
        return dict(PLATFORMS[key], key=key)
    raise ValueError('没登记的平台：' + str(name))
