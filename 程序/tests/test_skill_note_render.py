"""R1685 技能说明栏：Markdown 解析成 Text 标签，并验证真实 SKILL 与畸形输入。"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

import skill_note_render as render


MARKDOWN = """---
name: demo-skill
description: demo
---
# 一级标题
正文 **粗体**、`行内代码` 与 [链接文字](https://example.test)。

## 二级标题
- 第一项
1. 第二项

> 引用段落

```python
print('hello')
```

| 列1 | 列2 |
| --- | --- |
| 甲 | 乙 |

---
<!-- 整行注释不应显示 -->
"""


def _joined(fragments):
    return ''.join(text for text, _tags in fragments)


def _tags(fragments):
    return {tag for _text, tags in fragments for tag in tags}


class ParseTests(unittest.TestCase):
    def test_markdown_is_rendered_without_raw_markers(self):
        fragments = render.parse(MARKDOWN)
        plain = _joined(fragments)
        for marker in ('#', '**', '```', ']('):
            self.assertNotIn(marker, plain)
        self.assertNotIn('name:', plain)
        self.assertNotIn('---', plain)
        self.assertNotIn('整行注释', plain)
        self.assertIn('链接文字', plain)
        self.assertIn('列1 \uff5c 列2', plain)
        self.assertIn('print(\'hello\')', plain)

    def test_heading_and_inline_tags_are_exposed(self):
        fragments = render.parse(MARKDOWN)
        headings = [(text, tags) for text, tags in fragments
                    if any(tag.startswith('heading') for tag in tags)]
        self.assertEqual(headings[0][0], '一级标题')
        self.assertIn('heading1', headings[0][1])
        self.assertIn('heading2', headings[1][1])
        self.assertIn('bold', _tags(fragments))
        self.assertIn('inline_code', _tags(fragments))
        self.assertIn('code_block', _tags(fragments))
        self.assertIn('quote', _tags(fragments))
        self.assertIn('table', _tags(fragments))
        self.assertIn('separator', _tags(fragments))

    def test_list_items_use_bullet_and_hanging_tag(self):
        bullets = [text for text, tags in render.parse(MARKDOWN) if 'list' in tags]
        self.assertEqual([text[:2] for text in bullets], ['\u2022 ', '\u2022 '])
        self.assertTrue(all(text.startswith('\u2022 ') for text in bullets))

    def test_four_heading_levels_and_unknown_syntax_are_safe(self):
        fragments = render.parse('#### 四级\n未知 [残缺 与 **未闭合')
        self.assertIn('heading4', _tags(fragments))
        plain = _joined(fragments)
        self.assertIn('四级', plain)
        self.assertIn('未知 [残缺', plain)
        self.assertIn('**未闭合', plain)

    def test_hash_inside_heading_and_code_block_content_are_preserved(self):
        fragments = render.parse('# C# 与 F#\n```html\n<!-- keep -->\n\nx\n```')
        headings = [text for text, tags in fragments if 'heading1' in tags]
        self.assertEqual(headings, ['C# 与 F#'])
        code = ''.join(text for text, tags in fragments if 'code_block' in tags)
        self.assertIn('<!-- keep -->', code)
        self.assertIn('\n    \n', code)


class TkRenderTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.widget = tk.Text(self.root, wrap='word', state='disabled')

    def test_apply_configures_tags_and_keeps_widget_read_only(self):
        render.apply(self.widget, MARKDOWN)
        names = set(self.widget.tag_names())
        for tag in ('heading1', 'heading2', 'bold', 'inline_code', 'code_block',
                    'list', 'quote', 'table', 'separator'):
            self.assertIn(tag, names)
        content = self.widget.get('1.0', 'end')
        for marker in ('#', '**', '```', ']('):
            self.assertNotIn(marker, content)
        self.assertEqual(str(self.widget.cget('state')), 'disabled')
        self.assertTrue(self.widget.tag_ranges('heading1'))
        self.assertTrue(self.widget.tag_ranges('list'))

    def test_translation_hint_uses_hint_tag(self):
        render.apply(self.widget, '正在生成中文说明…\n\n# 标题\n正文')
        self.assertIn('hint', set(self.widget.tag_names()))
        self.assertTrue(self.widget.get('1.0', 'end').startswith('正在生成中文说明'))

    def test_panel_render_note_uses_markdown_renderer(self):
        import skill_panel
        host = SimpleNamespace(note_text=self.widget)
        skill_panel.Panel.render_note(host, MARKDOWN)
        content = self.widget.get('1.0', 'end')
        self.assertIn('一级标题', content)
        self.assertNotIn('**', content)
        self.assertIn('heading1', set(self.widget.tag_names()))

    def test_real_skill_files_render_non_empty(self):
        program = Path(__file__).resolve().parents[1]
        files = sorted((program / 'skills').rglob('*.skill.md'))[:3]
        self.assertEqual(len(files), 3)
        for path in files:
            with self.subTest(path=path.name):
                markdown = path.read_text(encoding='utf-8-sig')
                render.apply(self.widget, markdown)
                self.assertTrue(self.widget.get('1.0', 'end').strip())

    def test_malformed_inputs_do_not_raise(self):
        cases = ('未闭合 **粗体', '```python\nprint(1)', '', '超长行' + 'x' * 20000,
                 '| 残缺表格\n---\n> 未闭合引用')
        for markdown in cases:
            with self.subTest(length=len(markdown)):
                render.apply(self.widget, markdown)
                self.assertIsInstance(self.widget.get('1.0', 'end'), str)


if __name__ == '__main__':
    unittest.main()
