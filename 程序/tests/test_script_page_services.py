"""剧本页服务可独立注入，不依赖 Desktop 全局宿主。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from desktop_script_pages import ScriptPagesMixin, ScriptPageServices


class ScriptPageServicesTests(unittest.TestCase):
    def page(self, root, opened):
        class Page(ScriptPagesMixin):
            pass
        page = Page()
        page.root = root
        page.notifier = SimpleNamespace(info=Mock())
        page.script_page_services = ScriptPageServices(opened.append, Mock(), Mock())
        return page

    def test_reports_use_instance_services_without_desktop_or_global_host(self):
        """REQ-S01-76：「质检报告」合并原「查看质检报告」与「质检目录」：有报告开报告，没有开质检目录。"""
        import project_stages
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / 'report.md'
            report.write_text('quality', encoding='utf-8')
            quality = project_stages.writing(root) / 'quality'
            quality.mkdir(parents=True)
            left, right = [], []
            first, second = self.page(root, left), self.page(root, right)
            first._script_quality_report = (str(root), str(report))
            first.open_script_quality()
            second.open_script_quality()
            self.assertEqual(left, [str(report)])
            self.assertEqual(right, [quality])
            first.notifier.info.assert_not_called()
            second.notifier.info.assert_not_called()

    def test_old_project_report_is_not_opened_in_new_project(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / 'old.md'
            report.write_text('old', encoding='utf-8')
            opened = []
            page = self.page(root, opened)
            page._script_quality_report = ('another-project', str(report))
            page.open_script_quality()
            self.assertEqual(opened, [])
            page.notifier.info.assert_called_once()

    def test_fallback_opens_latest_report_matching_current_project(self):
        """REQ-S01-76：内存无记录（重启后）时，按剧本路径从质检目录定位历史报告，而非只开 hash 目录。"""
        import writing_quality
        from test_writing_quality import publisher, envelope
        import project_stages
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            quality = project_stages.writing(root) / 'quality'
            script = project_stages.writing(root) / '自然剧本.md'
            result = writing_quality.publish_reports(
                envelope('主角：你先走吧。'), script, quality, publish=publisher).data
            opened = []
            page = self.page(root, opened)
            # 无内存记录，模拟重启后点击「质检报告」。
            page._script_quality_report = ('', '')
            page.open_script_quality()
            self.assertEqual(opened, [result['quality_report_path']])
            page.notifier.info.assert_not_called()
