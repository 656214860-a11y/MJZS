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
