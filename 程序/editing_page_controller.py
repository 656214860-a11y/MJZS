"""无 Tk 的后期页状态与自动粗剪结果编排。"""
from __future__ import annotations

from pathlib import Path


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
        skipped = self.assemble_report.get('skipped') or []
        if not skipped:
            return ''
        return '已跳过 ' + str(len(skipped)) + ' 个未就绪镜头：' + '；'.join(skipped) + '；成片：' + str(path)

    def output_spec_text(self):
        """本页要显示的实际输出规格；拿不到就留空，页面照常可用。"""
        getter = getattr(self.studio, 'output_spec_text', None)
        if not callable(getter):
            return ''
        try:
            return str(getter() or '')
        except (OSError, ValueError):
            return ''
