"""无 Tk 的后期页状态与自动粗剪结果编排。"""
from __future__ import annotations

from pathlib import Path


def duration_text(seconds):
    """给界面看的总时长：不喊小数，60 秒以上说「X分YY秒」。"""
    total = int(round(float(seconds or 0)))
    if total >= 60:
        return '%d分%02d秒' % (total // 60, total % 60)
    return '%d秒' % total


class EditingPageController:
    """保存后期页的可用性判断和自动粗剪报告；页面只负责呈现。"""

    def __init__(self, project, studio):
        self.project = Path(project).resolve()
        self.studio = studio
        self.assemble_report = {}

    def has_downloaded_video(self):
        state = self.studio.state()
        return any(
            version.get('file') and (self.project / version['file']).is_file()
            for shot in self.studio.episode['shots']
            for version in state['shots'].get(shot['id'], [])
        )

    def assemble(self):
        self.assemble_report.clear()
        return self.studio.assemble(skip_unready=True, report=self.assemble_report)

    def assembled_message(self, path):
        """粗剪完成后的状态：说清包含／缺了哪些镜头、共多长，别让部分粗剪冒充完整成片。

        ``assemble`` 会往报告里写 ``included``／``expected``／``duration``；老调用方只给了 ``skipped``
        时退回原来的短路提示，不改变既有行为。
        """
        report = self.assemble_report
        skipped = report.get('skipped') or []
        included = report.get('included')
        expected = report.get('expected')
        parts = []
        if included is not None and expected:
            parts.append('已包含 %d/%d 镜' % (len(included), expected))
        duration = report.get('duration')
        if duration is not None:
            parts.append('总时长 ' + duration_text(duration))
        if skipped:
            parts.append('已跳过 ' + str(len(skipped)) + ' 个未就绪镜头：' + '；'.join(skipped))
        elif included is not None:
            parts.append('全部镜头已包含')
        message = '；'.join(parts)
        if not message:
            return ''
        return message + '；成片：' + str(path)

    def output_spec_text(self):
        """本页要显示的实际输出规格；拿不到就留空，页面照常可用。"""
        getter = getattr(self.studio, 'output_spec_text', None)
        if not callable(getter):
            return ''
        try:
            return str(getter() or '')
        except (OSError, ValueError):
            return ''
