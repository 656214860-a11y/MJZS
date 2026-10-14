# -*- coding: utf-8 -*-
"""剪辑软件交付出口：把成片所用镜头排成 EDL（CMX3600）、FCPXML 与分轨素材清单文本。

只生成文本，不写文件、不调用任何剪辑软件；写盘由 L3 `engine` 经 `agent.core.save_text`
完成。时间码为非丢帧（按整数帧率取整），累计用帧数相加，避免逐镜四舍五入漂移。
剪映草稿格式没有公开稳定规范，不在此臆造；达芬奇／Premiere 等可直接导入 EDL 或 FCPXML。
"""
from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

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
