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


if __name__ == '__main__':
    unittest.main()
