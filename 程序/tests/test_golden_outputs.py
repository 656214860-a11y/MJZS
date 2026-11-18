# -*- coding: utf-8 -*-
"""黄金文件断言（T8.2）：prompt 渲染、字幕导出（SRT/ASS）、分镜提示词的整份输出
逐字节对照 ``tests/fixtures/golden/`` 下的基线文件。

定向断言（assertIn／assertEqual）只钉住被点名的那几个词，模板顺序、分隔符、
页眉页脚、空段省略这类「整体长什么样」的回归只有整份对照才抓得到。

更新黄金文件：改动渲染输出后运行 ``set GOLDEN_UPDATE=1``（PowerShell:
``$env:GOLDEN_UPDATE='1'``）重跑本文件，黄金文件会被重写；**每次更新必须在
对应轮次结果文件里写明原因**（任务书 T8.2 要求），不允许顺手刷新掩盖回归。
行尾统一按 ``\\n`` 比较，检出行尾差异不算失败。
"""
import json
import os
import unittest
from pathlib import Path

import asset_prompt_rules
from contract import prompt_templates as pt
from contract import shot_batches
from contract import storyboard_contract
from domain import subtitle_timing

GOLDEN_DIR = Path(__file__).resolve().parent / 'fixtures' / 'golden'
UPDATE = os.environ.get('GOLDEN_UPDATE') == '1'
# asset_prompt_rules.COMMON 内嵌本机绝对路径（asset_manifest.schema.json 位置），
# 跨机器黄金对照前归一成占位符。
_PROGRAM_DIR = str(Path(__file__).resolve().parents[1])

CHARACTER = {"name": "林小满", "character_anchor": "黑短发、杏眼、米色针织衫",
             "state_variants": [{"state_id": "CST-01", "name": "日常装",
                                 "override": "米色针织衫"}]}
SCENE = {"name": "咖啡馆", "lighting_direction": "右侧落地窗自然光 5600K",
         "spatial_anchors": [{"object": "壁灯", "position": "左侧墙面 1.5 米处"}],
         "scale_reference": "吧台高约 1.1 米"}
SHOT = {"id": "SH001", "character_refs": ["@图片1", "@图片2"],
        "reference_roles": {"@图片1": {"responsibility": "五官与发型",
                                     "exclude": "服装与场景"},
                            "@图片2": {"responsibility": "服装状态",
                                     "exclude": "五官与背景"}}}

# 字幕用固定剧集：两镜有对白（dict 与纯文本两种写法）、一镜无对白。
SUBTITLE_EPISODE = {"episode_id": "EP001", "shots": [
    {"id": "SH001", "duration": 8, "dialogue": [
        {"speaker": "林小满", "text": "你终于来了"},
        {"speaker": "陈默", "text": "嗯，等了你半小时"}]},
    {"id": "SH002", "duration": 6, "dialogue": ["旁白：午后的咖啡馆很安静"]},
    {"id": "SH003", "duration": 5, "dialogue": []},
]}
# 带真实音频时长的校准输入：与上面 entries 逐句对齐。
SUBTITLE_AUDIO = [1.5, 2.5, 3.0]

# 分镜定稿文档用固定剧集：两个三元组 → 两个批次。
FINAL_EPISODE = {"episode_id": "EP001", "shots": [
    {"shot_id": "SH001", "scene_id": "SC-咖啡馆", "character_ids": ["CHAR-01"],
     "costume_id": "CST-01", "duration": 6},
    {"shot_id": "SH002", "scene_id": "SC-咖啡馆", "character_ids": ["CHAR-01"],
     "costume_id": "CST-01", "duration": 8},
    {"shot_id": "SH003", "scene_id": "SC-天台", "character_ids": ["CHAR-02"],
     "costume_id": "CST-02", "duration": 5},
]}

# 批次切分用例：三元组变化与时长上限各触发一次切批。
BATCH_SHOTS = [
    {"id": "S01", "scene_id": "SC-A", "character_ids": ["CHAR-01"],
     "costume_id": "CST-01", "duration": 10},
    {"id": "S02", "scene_id": "SC-A", "character_ids": ["CHAR-01"],
     "costume_id": "CST-01", "duration": 10},
    {"id": "S03", "scene_id": "SC-A", "character_ids": ["CHAR-01", "CHAR-02"],
     "costume_id": "CST-01", "duration": 10},
    {"id": "S04", "scene_id": "SC-A", "character_ids": ["CHAR-01", "CHAR-02"],
     "costume_id": "CST-01", "duration": 10},
]


def _norm(text):
    return (str(text).replace('\r\n', '\n').replace('\r', '\n')
            .replace(_PROGRAM_DIR, '<PROGRAM>'))


def _golden(name, text):
    path = GOLDEN_DIR / name
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_norm(text), encoding='utf-8', newline='\n')
        return
    if not path.is_file():
        raise AssertionError('缺少黄金文件 %s；先以 GOLDEN_UPDATE=1 生成并在结果文件说明' % path)
    expected = _norm(path.read_text(encoding='utf-8'))
    actual = _norm(text)
    if actual != expected:
        import difflib
        diff = ''.join(difflib.unified_diff(
            expected.splitlines(True), actual.splitlines(True),
            fromfile='golden/' + name, tofile='actual'))
        raise AssertionError('黄金文件 %s 不一致（若为有意变更，用 GOLDEN_UPDATE=1 重建'
                             '并在结果文件说明原因）：\n%s' % (name, diff[:4000]))


class PromptTemplateGoldenTests(unittest.TestCase):
    """prompt_templates：图片／视频／职责／契约句整份输出。"""

    def test_image_prompt_with_costume(self):
        _golden('prompt_image_cst01.txt',
                pt.image_prompt(CHARACTER, SCENE, costume_id='CST-01') + '\n')

    def test_video_prompt_and_roles(self):
        body = '\n'.join([
            pt.video_prompt('林小满推门进入', '轻微推进', '门把手转动'),
            '',
            '职责声明：',
            *[line for _ref, line in pt.role_lines(SHOT)],
        ])
        _golden('prompt_video_roles.txt', body + '\n')

    def test_contract_and_common_lines(self):
        _golden('prompt_contract_lines.txt',
                '\n'.join(pt.contract_lines() + pt.common_lines()) + '\n')

    def test_template_rows_table(self):
        rows = pt.rows()
        _golden('prompt_rows.txt',
                '\n'.join('%s｜%s｜%s' % row for row in rows) + '\n')

    def test_asset_stage_rules(self):
        _golden('asset_rules_writing.txt', asset_prompt_rules.rules('writing'))
        _golden('asset_rules_storyboard.txt', asset_prompt_rules.rules('storyboard'))


class SubtitleGoldenTests(unittest.TestCase):
    """subtitle_timing：SRT 条目、ASS 全文、校准报告整份输出。"""

    def test_srt_document_estimated(self):
        rows, estimated = subtitle_timing.srt_rows(SUBTITLE_EPISODE)
        self.assertTrue(estimated)
        _golden('srt_estimated.srt', ''.join(rows))

    def test_srt_document_audio_calibrated(self):
        rows, estimated = subtitle_timing.srt_rows(SUBTITLE_EPISODE, audio=SUBTITLE_AUDIO)
        self.assertFalse(estimated)
        _golden('srt_calibrated.srt', ''.join(rows))

    def test_ass_document(self):
        entries, _report = subtitle_timing.calibrate_entries(
            SUBTITLE_EPISODE, audio=SUBTITLE_AUDIO)
        _golden('ass_full.ass', subtitle_timing.ass_text(entries))

    def test_calibrate_report(self):
        _entries, report = subtitle_timing.calibrate_entries(
            SUBTITLE_EPISODE, audio=SUBTITLE_AUDIO)
        _golden('calibrate_report.json',
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


class StoryboardPromptGoldenTests(unittest.TestCase):
    """分镜提示词侧的确定性文本：契约提示词句、批次划分说明、镜头表。"""

    def test_storyboard_contract_prompt_lines(self):
        _golden('storyboard_contract_prompt_lines.txt',
                storyboard_contract.prompt_lines() + '\n')

    def test_storyboard_contract_rules_prompt(self):
        # 轮 6C·D7：rules() 改由契约事实表渲染字段枚举，输出须与改动前逐字一致。
        _golden('storyboard_contract_rules.txt', storyboard_contract.rules() + '\n')

    def test_batch_plan_markdown(self):
        from orchestrator import storyboard_final
        _golden('storyboard_batch_plan.md',
                storyboard_final._batch_plan_markdown(FINAL_EPISODE))

    def test_shot_table_markdown(self):
        from orchestrator import storyboard_final
        _golden('storyboard_shot_table.md',
                storyboard_final._shot_table_markdown(FINAL_EPISODE))

    def test_batch_grouping_layout(self):
        grouped = shot_batches.batches(BATCH_SHOTS)
        lines = []
        for name, items in grouped.items():
            ids = '、'.join(str(item.get('id')) for item in items)
            lines.append('%s: %s' % (name, ids))
        _golden('shot_batches_grouping.txt', '\n'.join(lines) + '\n')


if __name__ == '__main__':
    unittest.main()
