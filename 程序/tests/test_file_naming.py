# -*- coding: utf-8 -*-
"""R3093（任务书 P0）：用户可见文件名唯一命名中心的契约。

覆盖：清洗规则与历史 ``_file_name_part`` 逐字一致；四段式与序号模板按类型生成；
Windows 非法字符／保留名／末尾点空格／超长名一律拒绝并给出可读原因；从既有文件名
解析排序键；历史命名方案可识别（只读兼容，不批量改名）。
"""
import unittest

from contract import file_naming


class SanitizePartTests(unittest.TestCase):
    def test_matches_historical_cleaning(self) -> None:
        """清洗结果与历史实现逐字一致，接入命名中心不改变任何既有文件名。"""
        cases = [('初稿/第二版', '初稿_第二版'), ('a:b*c', 'a_b_c'), ('  前后空格  ', '前后空格'),
                 ('点结尾.', '点结尾'), ('多  空格', '多 空格'), ('', '文件')]
        for raw, expected in cases:
            self.assertEqual(file_naming.sanitize_part(raw), expected, raw)

    def test_long_part_is_truncated(self) -> None:
        self.assertEqual(len(file_naming.sanitize_part('长' * 200)), 80)


class GenerateNameTests(unittest.TestCase):
    def test_script_template_is_four_part(self) -> None:
        """剧本类沿用四段式：项目名_文件类型_文件内容_年月日.md。"""
        name = file_naming.generate_name('剧本', project='漫剧测试', file_type='剧本', content='初稿', date='20261117')
        self.assertEqual(name, '漫剧测试_剧本_初稿_20261117.md')

    def test_sequence_template_is_zero_padded(self) -> None:
        name = file_naming.generate_name('分镜', prefix='EP001', index=7, slug='开场', suffix='.json')
        self.assertEqual(name, 'EP001_007_开场.json')

    def test_plain_template_keeps_stem(self) -> None:
        self.assertEqual(file_naming.generate_name('清单', stem='assets', suffix='.json'), 'assets.json')

    def test_missing_date_falls_back_to_today(self) -> None:
        name = file_naming.generate_name('剧本', project='P', file_type='剧本', content='C')
        self.assertRegex(name, r'^P_剧本_C_\d{8}\.md$')

    def test_unknown_kind_uses_plain_template(self) -> None:
        self.assertEqual(file_naming.generate_name('不存在的类型', stem='x', suffix='.md'), 'x.md')


class ValidateTests(unittest.TestCase):
    def test_accepts_normal_name(self) -> None:
        self.assertEqual(file_naming.validate('正常名字.md'), '正常名字.md')

    def test_rejects_leading_or_trailing_spaces(self) -> None:
        for bad in (' 名字.md', '名字.md '):
            with self.assertRaises(ValueError, msg=bad):
                file_naming.validate(bad)

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            file_naming.validate('   ')

    def test_rejects_illegal_characters(self) -> None:
        for bad in ('a*b.md', 'a?b.md', 'a"b.md', 'a<b.md', 'a|b.md', 'a/b.md', 'a\\b.md', 'a:b.md'):
            with self.assertRaises(ValueError, msg=bad):
                file_naming.validate(bad)

    def test_rejects_windows_reserved_names(self) -> None:
        for bad in ('CON', 'con.txt', 'PRN.md', 'AUX', 'NUL.json', 'COM1.txt', 'LPT9'):
            with self.assertRaises(ValueError, msg=bad):
                file_naming.validate(bad)

    def test_rejects_trailing_dot_or_space(self) -> None:
        for bad in ('名字.', '名字 '):
            with self.assertRaises(ValueError, msg=bad):
                file_naming.validate(bad)

    def test_rejects_over_long_name(self) -> None:
        with self.assertRaises(ValueError):
            file_naming.validate('长' * (file_naming.MAX_NAME + 1))

    def test_reason_is_readable(self) -> None:
        with self.assertRaises(ValueError) as caught:
            file_naming.validate('CON.txt')
        self.assertIn('保留名', str(caught.exception))

    def test_check_path_only_checks_length(self) -> None:
        self.assertEqual(file_naming.check_path('a/b'), 'a/b')
        with self.assertRaises(ValueError):
            file_naming.check_path('a' * (file_naming.MAX_PATH + 1))


class ParseTests(unittest.TestCase):
    def test_episode_order(self) -> None:
        parsed = file_naming.parse('EP012_分镜.json')
        self.assertEqual(parsed['order'], 12)
        self.assertEqual(parsed['ext'], '.json')

    def test_shot_order(self) -> None:
        self.assertEqual(file_naming.parse('SH003_首帧.png')['order'], 3)

    def test_leading_digits_order(self) -> None:
        self.assertEqual(file_naming.parse('007_片段.md')['order'], 7)

    def test_no_number_gives_zero_order(self) -> None:
        self.assertEqual(file_naming.parse('自然剧本.md')['order'], 0)

    def test_title_drops_separators(self) -> None:
        self.assertEqual(file_naming.parse('测试项目_剧本_初稿_20261117.md')['title'],
                         '测试项目 剧本 初稿 20261117')

    def test_kind_guessed_by_suffix(self) -> None:
        self.assertEqual(file_naming.parse('a.png')['kind'], '资产')
        self.assertEqual(file_naming.parse('a.wav')['kind'], '音频')
        self.assertEqual(file_naming.parse('a.json')['kind'], '清单')


class LegacySchemeTests(unittest.TestCase):
    def test_recognizes_script_four_part(self) -> None:
        self.assertEqual(file_naming.legacy_scheme('漫剧_剧本_初稿_20261117.md'), '剧本四段式')

    def test_recognizes_first_frame_hash(self) -> None:
        self.assertEqual(file_naming.legacy_scheme('EP001_SH001_8a7043f5.png'), '首帧')

    def test_recognizes_final_storyboard_directory(self) -> None:
        self.assertEqual(file_naming.legacy_scheme('EP003_分镜定稿_20261117'), '分镜定稿目录')

    def test_recognizes_asset_ids(self) -> None:
        self.assertEqual(file_naming.legacy_scheme('CHAR_001'), '资产编号')

    def test_plain_name_is_not_legacy(self) -> None:
        self.assertIsNone(file_naming.legacy_scheme('storyboard_draft.json'))


if __name__ == '__main__':
    unittest.main()
