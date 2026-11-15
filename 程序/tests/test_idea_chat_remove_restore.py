"""剧本准备聊天单条删除／恢复与「删除全部信息」的落盘顺序（R2364 代码审查修复）。运行：python test_idea_chat_remove_restore.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import idea_chat
import idea_transcript
from project_stages import writing
from stage_execution_service import idea_chat_gateway, project_context


class RemoveRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = project_context(self.tmp.name)
        self.gateway = idea_chat_gateway()

    def texts(self, model):
        return [row['text'] for row in idea_chat.load(self.root, model=model, gateway=self.gateway)]

    def test_restored_message_goes_back_to_its_original_position(self):
        for text in ('第一条', '第二条', '第三条'):
            idea_chat.append(self.root, 'user', text, model='模型甲', gateway=self.gateway)
        middle = idea_chat.load(self.root, model='模型甲', gateway=self.gateway)[1]
        idea_chat.remove_message(self.root, middle, gateway=self.gateway)
        self.assertEqual(self.texts('模型甲'), ['第一条', '第三条'])
        idea_chat.restore_latest_removed(self.root, model='模型甲', gateway=self.gateway)
        self.assertEqual(self.texts('模型甲'), ['第一条', '第二条', '第三条'], '恢复应插回原位置，不是对话最顶部')

    def test_remove_all_without_rows_preserves_other_models_chat_and_trash(self):
        """R2898 契约：统一文件混放所有模型——无行模型的 remove_all 不能误删他人对话与回收站。"""
        idea_chat.append(self.root, 'user', '乙的对话', model='模型乙', gateway=self.gateway)
        idea_chat.append(self.root, 'user', '甲的对话', model='模型甲', gateway=self.gateway)
        idea_chat.append(self.root, 'user', '甲的待删', model='模型甲', gateway=self.gateway)
        idea_chat.remove_message(self.root, idea_chat.load(self.root, model='模型甲', gateway=self.gateway)[1],
                                 gateway=self.gateway)
        trash = idea_transcript.deleted_history_path(self.root, model='模型甲')
        # 模型丙没有任何行：返回 0，统一对话文件与回收站原样保留。
        self.assertEqual(idea_chat.remove_all(self.root, model='模型丙', gateway=self.gateway), 0)
        self.assertEqual(self.texts('模型乙'), ['乙的对话'])
        self.assertEqual(self.texts('模型甲'), ['甲的对话'])
        records = json.loads(trash.read_text(encoding='utf-8'))['messages']
        self.assertEqual([record.get('model') for record in records], ['模型甲'])
        # 模型甲清空：自己的对话行与删除记录移除，模型乙的对话不受影响。
        self.assertEqual(idea_chat.remove_all(self.root, model='模型甲', gateway=self.gateway), 1)
        self.assertEqual(self.texts('模型甲'), [])
        self.assertEqual(self.texts('模型乙'), ['乙的对话'])
        self.assertFalse(trash.exists(), '删除记录全部属于本模型时回收站文件整体回收')

    def test_remove_all_changes_nothing_when_legacy_backup_cannot_be_recycled(self):
        idea_chat.append(self.root, 'user', '本模型会话', model='模型甲', gateway=self.gateway)
        legacy = writing(Path(self.tmp.name)) / '旧Provider' / '旧名' / idea_transcript.FOLDER / idea_transcript.CHAT_NAME
        legacy.parent.mkdir(parents=True, exist_ok=True)
        row = {'role': 'assistant', 'text': '旧版残留', 'model': '模型甲', 'at': '2026-01-01 00:00:00'}
        legacy.write_text(json.dumps({'version': 1, 'messages': [row]}, ensure_ascii=False), encoding='utf-8')
        idea_transcript._history_cache.clear()
        def recycle(_root, paths, _reason=''):
            for path in paths:                    # 会话文件照常移走，只有备份进不了回收站
                if '备份' not in Path(path).name:
                    Path(path).unlink()
        stuck = dict(self.gateway, recycle_paths=recycle)
        with self.assertRaises(OSError):
            idea_chat.remove_all(self.root, model='模型甲', gateway=stuck)
        self.assertIn('本模型会话', self.texts('模型甲'), '备份失败时本模型文件不能先被删掉')
        self.assertIn('旧版残留', legacy.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
