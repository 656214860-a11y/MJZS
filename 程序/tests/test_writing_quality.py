"""No-network checks for the shared API/CLI/desktop quality receipt."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import writing_quality as quality


def envelope(body='主角：你先走吧。'):
    reports = {}
    for key, (_, count) in quality.REPORTS.items():
        items = [dict(id=i, evidence='你先走吧', reason='逐项核对', status='pass')
                 for i in range(1, (count or 1) + 1)]
        if key == 'emotion_curve':
            for item in items:item['intensity'] = 10 if item['id'] == 9 else 5
        if key == 'dialogue_speed_check':
            items[0].update(text='你先走吧', seconds=1, rate=4)
        reports[key] = dict(status='pass', items=items, coverage='全部台词')
    return body + '\n' + quality.OPEN + json.dumps(reports, ensure_ascii=False) + quality.CLOSE


def publisher(path, text, validate, index):
    assert validate(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    index(path)


class QualityTests(unittest.TestCase):
    def test_complete_reports_bind_final_body_and_preserve_raw(self):
        with tempfile.TemporaryDirectory() as td:
            result = quality.publish_reports(envelope(), Path(td)/'script.md', Path(td)/'quality', publish=publisher).data
            self.assertTrue(result['quality_passed'])
            folder = Path(result['quality_report_path']).parent
            self.assertEqual((folder/'model_response.txt').read_text(encoding='utf-8'), envelope())
            hashes = set()
            for key in quality.REPORTS:
                value = json.loads((folder/(key+'.json')).read_text(encoding='utf-8'))
                self.assertEqual(value['status'], 'pass')
                hashes.add(value['script_sha256'])
            self.assertEqual(len(hashes), 1)
            changed = quality.publish_reports(envelope('新稿。主角：你先走吧。'), Path(td)/'script.md', Path(td)/'quality', publish=publisher).data
            self.assertNotEqual(result['quality_report_path'], changed['quality_report_path'])

    def test_missing_and_broken_reports_keep_body(self):
        for response in ('剧本正文', '剧本正文'+quality.OPEN+'{',
                         '剧本正文'+quality.OPEN+'{"x":NaN}'+quality.CLOSE,
                         '剧本正文'+quality.OPEN+'{"x":1,"x":2}'+quality.CLOSE):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as td:
                self.assertEqual(quality.split_response(response)[0], '剧本正文')
                result = quality.publish_reports(response, Path(td)/'script.md', Path(td), publish=publisher).data
                self.assertFalse(result['quality_passed'])
                self.assertEqual(len(result['quality_statuses']), 4)

    def test_strip_envelope_removes_residual_envelope_in_all_shapes(self):
        body = '剧本正文'
        cases = {
            'no_envelope': body,
            'closed_envelope': body + quality.OPEN + '{"x":1}' + quality.CLOSE,
            'unclosed_envelope': body + quality.OPEN + '{"x":1',
            'truncated_json': body + quality.OPEN + '{',
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertEqual(quality.strip_envelope(text), body)
        # 只有最后一次 <script_quality> 才是附块起点，之前的同名字样属正文。
        self.assertEqual(quality.strip_envelope('正文提及<script_quality>的字样' + quality.OPEN + '{"x":1}'),
                         '正文提及<script_quality>的字样')

    def test_list_reports_maps_hash_folders_back_to_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = quality.publish_reports(envelope('第一稿。主角：你先走吧。'), root/'第一稿.md', root/'quality', publish=publisher).data
            second = quality.publish_reports(envelope('第二稿。主角：你先走吧。'), root/'第二稿.md', root/'quality', publish=publisher).data
            # 两份报告可能落在同一 mtime 精度刻度内（排序退化为目录序、时红时绿）；
            # 显式拉开时间戳，让「按 mtime 倒序」的断言确定性成立。
            first_md = Path(first['quality_report_path'])
            earlier = first_md.stat().st_mtime - 60
            os.utime(first_md, (earlier, earlier))
            rows = quality.list_reports(root/'quality')
            self.assertEqual(len(rows), 2)
            # 第二稿后写，按 mtime 倒序排在最前。
            self.assertEqual(rows[0]['report_path'], second['quality_report_path'])
            paths = {Path(row['script_path']).name for row in rows}
            self.assertEqual(paths, {'第一稿.md', '第二稿.md'})
            # 报告 md 顶部带「来源剧本」行，供人工识别。
            report_text = Path(second['quality_report_path']).read_text(encoding='utf-8')
            self.assertIn('来源剧本：', report_text)

    def test_list_reports_empty_or_missing_dir(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(quality.list_reports(Path(td)/'none'), [])
            self.assertEqual(quality.list_reports(Path(td)), [])

    def test_invalid_evidence_duplicate_id_peak_and_speed_are_not_passed(self):
        body, reports, _ = quality.split_response(envelope())
        reports['screenplay_gates']['items'][0]['evidence'] = '旧稿才有'
        reports['dialogue_diagnosis']['items'][1]['id'] = 1
        reports['emotion_curve']['items'][8]['intensity'] = 9
        reports['dialogue_speed_check']['items'][0]['rate'] = 10
        for key in reports:
            self.assertNotEqual(quality._validate(key, reports[key], body)[0], 'pass')

    def test_missing_skill_does_not_enable_contract(self):
        self.assertFalse(quality.enabled('dialogue-doctor-7d.md'))
        self.assertTrue(quality.enabled(' '.join(quality.REFERENCES)))

    def test_publication_failure_is_not_reported_as_success(self):
        def fail(*args):raise OSError('disk full')
        with self.assertRaises(OSError):
            quality.publish_reports(envelope(), 'script.md', 'quality', publish=fail)

    def test_api_and_desktop_save_identical_reports_and_clean_prose(self):
        import writing_api
        from stage_execution_service import collect_writing_quality, publish_stage_text
        from contract.stage_path_service import write_dir
        from test_workflow import make_project
        body = '# 自然剧本\n场景：雨夜照相馆\n' + ('主角推开门，握紧相机，说：“你先走吧”。\n' * 40)
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            response = envelope(body)
            result = writing_api._auto_save_script_raw(project, {'ok': True, 'text': response},
                                                       publish=publish_stage_text, quality_required=True)
            self.assertTrue(result['quality_passed'])
            for key in ('script_raw_path', 'natural_script_path'):
                self.assertEqual(Path(result[key]).read_text(encoding='utf-8').strip(), body.strip())
            target = write_dir(project, 'script') / '桌面自然剧本.md'
            target.write_text(response, encoding='utf-8')
            desktop = collect_writing_quality(project, target)
            self.assertEqual(result['quality_statuses'], desktop['quality_statuses'])
            self.assertEqual(target.read_text(encoding='utf-8').strip(), body.strip())
            self.assertNotEqual(result['quality_report_path'], desktop['quality_report_path'])

    def test_missing_reports_notify_without_extra_calls_or_erasing_prose(self):
        import writing_api
        from stage_execution_service import publish_stage_text
        from test_workflow import make_project
        body = '# 自然剧本\n场景：雨夜照相馆\n' + ('主角推开门，说：“你先走吧”。\n' * 80)
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            with patch('model_router.PoolAdapter.chat') as chat:
                result = writing_api._auto_save_script_raw(project, {'ok': True, 'text': body},
                                                           publish=publish_stage_text, quality_required=True)
            chat.assert_not_called()
            self.assertFalse(result['quality_passed'])
            self.assertIn('缺失', result['response_text'])
            self.assertTrue(Path(result['natural_script_path']).is_file())
            self.assertEqual(result['text'], body.strip())

    def test_desktop_watcher_ignores_old_file_and_stops_on_project_change(self):
        from desktop import Desktop
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'script.md'
            target.write_text(envelope(), encoding='utf-8')
            app = SimpleNamespace(root=Path(td), win=Mock())
            with patch('desktop.time.monotonic', return_value=0):
                Desktop.watch_script_quality(app, target)
            poll = app.win.after.call_args.args[1]
            with patch('desktop.time.monotonic', return_value=15), \
                    patch('stage_execution_service.collect_writing_quality') as collect:
                poll()
                collect.assert_not_called()
                app.root = Path(td) / 'different'
                app.win.after.reset_mock()
                poll()
                app.win.after.assert_not_called()

    def test_all_engines_freeze_the_same_quality_contract(self):
        import workflow_settings
        skill = Path(__file__).resolve().parents[1] / 'skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md'
        for engine in ('api', 'claude', 'codex', 'claude-desktop'):
            with self.subTest(engine=engine):
                frozen = workflow_settings.freeze_skills({'engine': engine, 'skills': [str(skill)]})
                instructions = workflow_settings.skill_prompt(frozen, inline=True)
                self.assertTrue(quality.enabled(instructions))
                self.assertEqual(instructions.count('【四项辅助质检交付】'), 1)

    def test_quality_prompt_assigns_each_report_to_one_review_role(self):
        text = quality.prompt()
        for duty in ('编剧角色审核五阶门控', '编辑角色审核 12 个情绪节拍', '演员角色完成台词七维诊断与语速检查'):
            self.assertEqual(text.count(duty), 1, duty)
        for obsolete in ('导演', 'APPROVED', 'REVISE', 'HOLLMWOOD'):
            self.assertNotIn(obsolete, text)

    def test_skill_defines_roles_and_editable_writer_style(self):
        skill = Path(__file__).resolve().parents[1] / 'skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md'
        body = skill.read_text(encoding='utf-8')
        for duty in ('编剧风格', '编剧角色 · 剧本五阶门控', '编辑角色 · 情绪节拍曲线',
                     '演员角色 · 台词七维诊断', '演员角色 · 台词语速自检'):
            self.assertIn(duty, body)
        self.assertNotIn('HOLLMWOOD', body)

    def test_desktop_new_file_receipt_notifies_once_without_scanning(self):
        from desktop import Desktop
        from types import SimpleNamespace
        result = dict(text='正文', quality_summary='四项缺失', quality_report_path='report.md', quality_passed=False)
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'script.md'
            app = SimpleNamespace(root=Path(td), win=Mock(), status=Mock(), show_script_quality=Mock(),
                                  idea_chat_context=Mock(), idea_chat_gateway=Mock(), show_conversation=Mock())
            with patch('desktop.time.monotonic', return_value=0):
                Desktop.watch_script_quality(app, target)
            poll = app.win.after.call_args.args[1]
            target.write_text('完整自然剧本', encoding='utf-8')
            with patch('desktop.time.monotonic', return_value=1):poll()
            with patch('desktop.time.monotonic', return_value=12), \
                    patch('stage_execution_service.collect_writing_quality', return_value=result) as collect, \
                    patch('idea_chat.append') as append:
                poll()
                poll()
                collect.assert_called_once_with(str(app.root), target)
                append.assert_called_once()
                self.assertIn('四项缺失', append.call_args.args[2])
                app.show_script_quality.assert_called_once_with(result)

    def test_incomplete_desktop_envelope_notifies_and_strips_residual_json(self):
        from desktop import Desktop
        from types import SimpleNamespace
        from stage_execution_service import collect_writing_quality
        from contract.stage_path_service import write_dir
        from test_workflow import make_project
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            target = write_dir(project, 'script') / '未完成自然剧本.md'
            target.parent.mkdir(parents=True, exist_ok=True)
            app = SimpleNamespace(root=project, win=Mock(), status=Mock(), show_script_quality=Mock(),
                                  idea_chat_context=Mock(), idea_chat_gateway=Mock(), show_conversation=Mock())
            with patch('desktop.time.monotonic', return_value=0):
                Desktop.watch_script_quality(app, target)
            body = '# 自然剧本\n场景：雨夜照相馆\n' + ('主角推开门，说：“你先走吧”。\n' * 80)
            response = body + quality.OPEN + '{'
            target.write_text(response, encoding='utf-8')
            poll = app.win.after.call_args.args[1]
            with patch('desktop.time.monotonic', return_value=1):poll()
            with patch('desktop.time.monotonic', return_value=12), patch('idea_chat.append') as append:
                poll()
                append.assert_not_called()
            with patch('desktop.time.monotonic', return_value=32), patch('idea_chat.append') as append:
                poll()
                poll()
                append.assert_called_once()
                self.assertIn('格式或证据错误', append.call_args.args[2])
            # 附块未闭合时，正文仍被剥离残留附块写回，文件末尾不再残留 <script_quality>。
            self.assertEqual(target.read_text(encoding='utf-8').strip(), body.strip())
            self.assertNotIn(quality.OPEN, target.read_text(encoding='utf-8'))
            self.assertFalse(app._script_quality_result['quality_passed'])

    def test_desktop_concurrent_write_is_never_marked_collected(self):
        from stage_execution_service import collect_writing_quality
        from contract.stage_path_service import write_dir
        from test_workflow import make_project
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            target = write_dir(project, 'script') / '自然剧本.md'
            target.parent.mkdir(parents=True, exist_ok=True)
            body = '# 自然剧本\n场景：雨夜照相馆\n' + ('主角推开门，说：“你先走吧”。\n' * 80)
            target.write_text(body, encoding='utf-8')
            original = quality.publish_reports
            def changed(*args, **kwargs):
                result = original(*args, **kwargs)
                target.write_text(body + '新写入', encoding='utf-8')
                return result
            with patch('writing_quality.publish_reports', side_effect=changed):
                with self.assertRaisesRegex(ValueError, '正文变化'):
                    collect_writing_quality(project, target)
            self.assertTrue(target.read_text(encoding='utf-8').endswith('新写入'))


if __name__ == '__main__':
    unittest.main()
