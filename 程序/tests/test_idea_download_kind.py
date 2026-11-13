# -*- coding: utf-8 -*-
"""剧本准备「下载」按钮：按当前模型输出归类成设定／大纲／角色卡／剧本。"""
import unittest

import idea_chat


class DownloadKindTests(unittest.TestCase):
    def test_review_documents_are_downloadable_by_title(self):
        self.assertEqual(idea_chat.download_kind('# 项目设定\n题材：都市'), '设定')
        self.assertEqual(idea_chat.download_kind('# 项目大纲\n第1集：相遇'), '大纲')
        self.assertEqual(idea_chat.download_kind('# 角色卡\n林夏：女主'), '角色卡')

    def test_plain_chat_is_not_downloadable(self):
        self.assertEqual(idea_chat.download_kind('好的，我们先聊聊你的想法。'), '')
        self.assertEqual(idea_chat.download_kind(''), '')

    def test_control_prompt_mentioning_type_is_not_a_document(self):
        # REQ-S01-76：回退确认提示等控制消息只是顺带提到「角色卡」等字样，不是文档，不应归档成角色卡。
        notice = ('回退到「项目设定」重新创作，会使已确认的「项目设定」「剧本大纲」「角色卡」失效，需要重新确认。\n'
                  '回复“确认”即从该阶段重写；回复其他内容则保持现状。')
        self.assertEqual(idea_chat.download_kind(notice), '')


if __name__ == '__main__':
    unittest.main()
