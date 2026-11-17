# -*- coding: utf-8 -*-
"""三虎监控剧本准备阶段顺序确认的唯一判据（设定 → 大纲 → 角色卡 → 剧本）。

覆盖：设定缺失→阻塞于设定；设定已确认、大纲未确认→阻塞于大纲；全部确认→放行；
三虎自动续跑被阻塞时不发完成事件；空项目（无已确认简报）行为不变。
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

import script_contract
import stage_completion_service
import stage_config
import writing_api
from agent.core import save
from contract.stage_path_service import write_dir
from test_preparation_confirmation import confirmed, preparation_folder
from test_writing_api import make_project

RAW = (
    '第 1 集\n'
    '场景 1：夜，旧书店内\n'
    '林小满：把旧怀表交给我。\n'
    '陆时：先离开这里。\n'
    '道具：旧怀表\n'
)


def write_brief(project):
    save(preparation_folder(project) / 'brief_complete.json', script_contract.brief_document({
        'story_summary': '雨夜少年发现会说话的底片。', 'main_characters': '少年和老板',
        'genre': '奇幻', 'length': '单集 60 秒'}))


def write_natural_script(project):
    """落盘一份被采用的自然剧本，让剧本阶段成果可解析。"""
    folder = write_dir(project, 'script')
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / '我的剧本_自然剧本_20260101.md'
    source.write_text(RAW, encoding='utf-8')
    save(script_contract.natural_script_selection_path(project), {
        'path': source.relative_to(project).as_posix(),
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    })
    return source


def write_quality_report(project, source, statuses):
    """按 publish_reports 的定位规则（路径哈希／正文 sha256）落一份采用稿质检报告。"""
    digest = hashlib.sha256(source.read_text(encoding='utf-8').strip().encode('utf-8')).hexdigest()
    identity = hashlib.sha256(str(source.resolve()).encode('utf-8')).hexdigest()[:12]
    folder = write_dir(project, 'script') / 'quality' / identity / digest
    folder.mkdir(parents=True, exist_ok=True)
    for key, status in statuses.items():
        save(folder / (key + '.json'), {'status': status})
    return folder


class PreparationProgressTests(unittest.TestCase):
    """只读判据：按顺序点出卡住的阶段，并区分缺文件／未确认。"""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.project = make_project(td.name)
        stage_config.put(self.project, 'script', model='gpt-4o')
        write_brief(self.project)

    def write_state(self, documents):
        target, state, _ = writing_api._preparation_state(
            self.project, writing_api._complete_brief(self.project))
        target.parent.mkdir(parents=True, exist_ok=True)
        state['documents'] = documents
        save(target, state)
        return target

    def test_setting_missing_blocks_at_setting(self):
        """设定文件缺失（无记录）→ 阻塞于项目设定，且标记为缺文件。"""
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['blocked'], '项目设定')
        self.assertTrue(progress['missing'])
        self.assertEqual(progress['confirmed'], 0)

    def test_setting_confirmed_outline_unconfirmed_blocks_at_outline(self):
        """设定已确认、大纲未确认 → 阻塞于剧本大纲，且标记为未确认。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        outline['confirmed'] = False
        self.write_state([setting, outline])
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['blocked'], '剧本大纲')
        self.assertFalse(progress['missing'])
        self.assertEqual(progress['confirmed'], 1)

    def test_all_confirmed_passes(self):
        """设定、大纲、角色卡全部确认 → 不阻塞，连续已确认数为 3。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        _, card = confirmed(self.project, '角色卡', '角色卡/卡.md', '# 角色卡\n少年\n')
        self.write_state([setting, outline, card])
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['blocked'], '')
        self.assertFalse(progress['missing'])
        self.assertEqual(progress['confirmed'], 3)

    def test_missing_file_after_confirmed_record_blocks_as_missing(self):
        """记录在但文件已被删 → 仍阻塞于该阶段，且标记为缺文件。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        self.write_state([setting, outline])
        Path(preparation_folder(self.project) / '剧本大纲/大纲.md').unlink()
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['blocked'], '剧本大纲')
        self.assertTrue(progress['missing'])

    def test_progress_reports_applicable_script_and_next_actions(self):
        """REQ-S01-84：进入确认流程的项目报 applicable、自然稿采用状态与下一步动作。"""
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertTrue(progress['applicable'])
        self.assertEqual(progress['script'], '待采用')
        self.assertIn('项目设定', progress['next_actions'][0])

    def test_next_actions_distinguish_missing_and_unconfirmed(self):
        """REQ-S01-84：缺文件指向生成并设为定稿，未确认指向确认动作。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        outline['confirmed'] = False
        self.write_state([setting, outline])
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertIn('剧本大纲', progress['next_actions'][0])
        self.assertIn('确认', progress['next_actions'][0])

    def test_next_actions_cover_revoked_and_pending_adoption(self):
        """REQ-S01-84：三阶段齐全后，待采用指向生成采用，失效记录指向重新采用。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        _, card = confirmed(self.project, '角色卡', '角色卡/卡.md', '# 角色卡\n少年\n')
        self.write_state([setting, outline, card])
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['script'], '待采用')
        self.assertIn('自然剧本', progress['next_actions'][0])
        write_natural_script(self.project)
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['script'], '已采用')
        self.assertEqual(progress['next_actions'], ())
        save(script_contract.natural_script_selection_path(self.project), {
            'path': '', 'sha256': '', 'reason': '前置阶段已更新，请重新生成或明确采用自然剧本'})
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['script'], '需重新采用')
        self.assertIn('重新', progress['next_actions'][0])


class CompletionEvidenceMonitorTests(unittest.TestCase):
    """阶段完成核验复用同一判据：准备顺序未完成就不算剧本阶段完成。"""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.project = make_project(td.name)
        stage_config.put(self.project, 'script', model='gpt-4o')
        write_brief(self.project)

    def write_state(self, documents):
        target, state, _ = writing_api._preparation_state(
            self.project, writing_api._complete_brief(self.project))
        target.parent.mkdir(parents=True, exist_ok=True)
        state['documents'] = documents
        save(target, state)
        return target

    def test_completion_evidence_blocks_when_setting_missing(self):
        """设定缺失时，即使已有自然剧本也不判剧本阶段完成，并点明卡点。"""
        write_natural_script(self.project)
        ok, detail = stage_completion_service.completion_evidence(self.project, 'script')
        self.assertFalse(ok)
        self.assertIn('项目设定', detail)
        self.assertIn('文件缺失', detail)

    def test_auto_continue_blocked_does_not_complete(self):
        """三虎自动续跑被阻塞：emit_verified_completion 不发 stage.completed。"""
        events = []

        def emit(kind, **kwargs):
            events.append((kind, kwargs))
            return {'ok': True}

        ok, _detail, payload = stage_completion_service.emit_verified_completion(
            self.project, 'script', '剧本已保存', emit)
        self.assertFalse(ok)
        self.assertIsNone(payload)
        self.assertEqual(events, [])

    def test_all_confirmed_and_script_present_completes(self):
        """设定、大纲、角色卡全部确认且自然剧本被采用 → 阶段完成并发出事件。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        _, card = confirmed(self.project, '角色卡', '角色卡/卡.md', '# 角色卡\n少年\n')
        self.write_state([setting, outline, card])
        write_natural_script(self.project)
        self.assertTrue(stage_completion_service.completion_evidence(self.project, 'script')[0])
        events = []

        def emit(kind, **kwargs):
            events.append((kind, kwargs))
            return {'ok': True}

        ok, _detail, payload = stage_completion_service.emit_verified_completion(
            self.project, 'script', '完成', emit)
        self.assertTrue(ok)
        self.assertEqual([kind for kind, _kwargs in events], ['stage.completed'])

    def _confirmed_three(self):
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        _, card = confirmed(self.project, '角色卡', '角色卡/卡.md', '# 角色卡\n少年\n')
        self.write_state([setting, outline, card])

    def test_failed_quality_report_on_adopted_script_blocks_completion(self):
        """REQ-S01-22：采用稿存在质检报告且含未过项时，阶段完成核验不通过。"""
        self._confirmed_three()
        source = write_natural_script(self.project)
        statuses = {key: 'pass' for key in ('screenplay_gates', 'emotion_curve',
                                            'dialogue_diagnosis', 'dialogue_speed_check')}
        statuses['emotion_curve'] = 'fail'
        write_quality_report(self.project, source, statuses)
        ok, detail = stage_completion_service.completion_evidence(self.project, 'script')
        self.assertFalse(ok)
        self.assertIn('质检', detail)
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['script'], '已采用')
        self.assertEqual(progress['script_quality']['emotion_curve'], 'fail')
        self.assertIn('质检', progress['next_actions'][0])

    def test_passed_quality_report_keeps_completion_and_reports_status(self):
        """REQ-S01-22：采用稿质检全过 → 完成核验通过；无报告的手动采用稿不受限。"""
        self._confirmed_three()
        source = write_natural_script(self.project)
        statuses = {key: 'pass' for key in ('screenplay_gates', 'emotion_curve',
                                            'dialogue_diagnosis', 'dialogue_speed_check')}
        write_quality_report(self.project, source, statuses)
        ok, _detail = stage_completion_service.completion_evidence(self.project, 'script')
        self.assertTrue(ok)
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['script_quality']['screenplay_gates'], 'pass')
        # 手动采用稿没有质检报告：完成核验不受限，script_quality 为 None。
        second = tempfile.TemporaryDirectory()
        self.addCleanup(second.cleanup)
        other = make_project(second.name)
        stage_config.put(other, 'script', model='gpt-4o')
        write_natural_script(other)
        ok, _detail = stage_completion_service.completion_evidence(other, 'script')
        self.assertTrue(ok)
        self.assertIsNone(stage_completion_service.preparation_progress(other)['script_quality'])


class EmptyProjectBehaviorTests(unittest.TestCase):
    """无已确认简报＝未进入四阶段确认流程：前三阶段不设卡，行为不变。"""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.project = make_project(td.name)

    def test_preparation_progress_not_blocked_without_brief(self):
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertEqual(progress['blocked'], '')
        self.assertEqual(progress['confirmed'], len(writing_api.PREPARATION_STAGES))

    def test_applicable_false_distinguishes_not_applicable_from_not_started(self):
        """REQ-S01-84：无简报=门禁不适用（applicable=False），区别于「未开始」（applicable=True、confirmed=0）。"""
        progress = stage_completion_service.preparation_progress(self.project)
        self.assertFalse(progress['applicable'])
        self.assertEqual(progress['script'], '待采用')

    def test_completion_evidence_keeps_natural_script_reason(self):
        """空项目没有自然剧本：仍返回「没有找到…成果」，不冒出准备阶段卡点文案。"""
        ok, detail = stage_completion_service.completion_evidence(self.project, 'script')
        self.assertFalse(ok)
        self.assertNotIn('剧本准备卡在', detail)


if __name__ == '__main__':
    unittest.main(verbosity=2)
