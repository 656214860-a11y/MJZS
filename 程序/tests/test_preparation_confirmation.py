"""把磁盘上的当前文件登记为阶段确认输出（右键入口）的行为契约。"""
import hashlib
import tempfile
import unittest

from agent.core import save
import project_stages
import script_contract
import stage_config
import writing_api
from stage_execution_service import publish_stage_text
from test_writing_api import make_project


def preparation_folder(project):
    return project_stages.writing(project)


def confirmed(project, stage, name, text):
    """写入一份真实文件并返回可直接放进 documents 的记录。"""
    path = preparation_folder(project) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path, {'stage': stage, 'path': name, 'confirmed': True,
                  'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}


class ConfirmPreparationDocumentTests(unittest.TestCase):
    """用户改过正文后，把现有文件重新登记为确认输出。"""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.project = make_project(td.name)
        stage_config.put(self.project, 'script', model='gpt-4o')
        save(preparation_folder(self.project) / 'brief_complete.json', script_contract.brief_document({
            'story_summary': '雨夜少年发现会说话的底片。', 'main_characters': '少年和老板',
            'genre': '奇幻', 'length': '单集 60 秒'}))
        self.brief = writing_api._complete_brief(self.project)
        self.assertIsNotNone(self.brief)

    def write_state(self, documents):
        target, state, _ = writing_api._preparation_state(self.project, self.brief)
        target.parent.mkdir(parents=True, exist_ok=True)
        state['documents'] = documents
        save(target, state)
        return target

    def test_confirm_registers_current_file_so_guard_stops_failing(self):
        """记录指向已搬走的旧稿时，确认现有文件后校验必须恢复通过。"""
        self.write_state([{'stage': '项目设定', 'path': '项目设定/搬走了.md',
                           'sha256': 'deadbeef', 'confirmed': True}])
        with self.assertRaises(ValueError):
            writing_api._preparation_state(self.project, self.brief)
        path, _ = confirmed(self.project, '项目设定', '项目设定/改过的设定.md',
                            '# 项目设定\n雨夜照相馆，少年握紧相机。\n')
        self.assertEqual(writing_api.confirm_preparation_document(
            self.project, '项目设定', path, publish=publish_stage_text), ())
        _, state, texts = writing_api._preparation_state(self.project, self.brief)
        self.assertEqual(texts, ['# 项目设定\n雨夜照相馆，少年握紧相机。\n'])
        self.assertEqual(state['documents'][0]['path'], '项目设定/改过的设定.md')
        self.assertEqual(state['documents'][0]['sha256'],
                         hashlib.sha256(texts[0].encode('utf-8')).hexdigest())

    def test_confirm_reports_invalidated_downstream_stages(self):
        """重新确认靠前阶段会使其后已确认阶段失效，并由返回值告知。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/定稿.md', '# 项目设定\n旧设定\n')
        _, outline = confirmed(self.project, '剧本大纲', '剧本大纲/大纲.md', '# 剧本大纲\n三幕\n')
        self.write_state([setting, outline])
        path, _ = confirmed(self.project, '项目设定', '项目设定/再审.md', '# 项目设定\n新设定\n')
        invalidated = writing_api.confirm_preparation_document(
            self.project, '项目设定', path, publish=publish_stage_text)
        self.assertEqual(invalidated, ('剧本大纲',))
        _, after, texts = writing_api._preparation_state(self.project, self.brief)
        self.assertEqual(len(after['documents']), 1)
        self.assertEqual(texts, ['# 项目设定\n新设定\n'])

    def test_confirm_refuses_when_previous_stage_unconfirmed(self):
        """不能跳过前置阶段：上一阶段未确认时拒绝登记。"""
        _, setting = confirmed(self.project, '项目设定', '项目设定/待确认.md', '# 项目设定\n草稿\n')
        setting['confirmed'] = False
        self.write_state([setting])
        path, _ = confirmed(self.project, '角色卡', '角色卡/角色卡.md', '# 角色卡\n少年\n')
        with self.assertRaisesRegex(ValueError, '请先确认所选阶段之前的文件'):
            writing_api.confirm_preparation_document(
                self.project, '角色卡', path, publish=publish_stage_text)

    def test_confirm_rejects_file_outside_preparation_folder(self):
        """只能登记剧本准备目录内的文件，避免把外部文件当成本阶段成果。"""
        self.write_state([])
        outside = preparation_folder(self.project).parent / '项目设定_外部.md'
        outside.write_text('# 项目设定\n外部\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '确认文件必须位于当前剧本准备目录内'):
            writing_api.confirm_preparation_document(
                self.project, '项目设定', outside, publish=publish_stage_text)

    def test_confirm_rejects_empty_file(self):
        """空白文件不能当确认输出。"""
        self.write_state([])
        path, _ = confirmed(self.project, '项目设定', '项目设定/空.md', '   \n')
        with self.assertRaisesRegex(ValueError, '文件内容为空'):
            writing_api.confirm_preparation_document(
                self.project, '项目设定', path, publish=publish_stage_text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
