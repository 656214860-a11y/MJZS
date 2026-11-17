# -*- coding: utf-8 -*-
"""REQ-S06-01/10/12/13/14/15/17/21/31：连贯性清单阶段的输入降级、本地计算、锚点逐字、冲突裁决、
三元组、跨批次与 flags、不改不生成、问题闭环登记、SKILL 工具登记。

这些编号原登记在 `维护记录/需求锚定基线.json` 的 `untested_done`，本轮补上落在真实代码行为上的锚点。
全部断言针对 `continuity_ledger`／`skill_tools` 的真实函数与常量，未 mock 被测事实、未改产品代码。
"""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import infra.continuity_ledger as continuity_ledger
import skill_tools
from agent.core import save


def _assets():
    """一集资产清单：角色（含状态覆盖）、场景（光源＋空间锚点＋尺度）、道具（材质＋尺度）。"""
    return {
        'CHAR_001': {
            'character_anchor': '黑发齐刘海',
            'state_variants': [{'state_id': 'CST-01', 'override': '穿红裙'}],
        },
        'LOC_001': {
            'lighting_direction': '左上',
            'spatial_anchors': [
                {'object': '门', 'position': '左侧', 'material': '木'},
                {'object': '窗', 'position': '右侧', 'material': ''},
            ],
            'scale_reference': '人身高 1.7m',
        },
        'PROP_001': {'material': '银', 'scale': '一掌大小'},
    }


def _shot(**extra):
    base = {'shot_id': 'S01', 'location': 'LOC_001', 'characters': ['CHAR_001'],
            'costume_id': 'CST-01', 'props': ['PROP_001']}
    base.update(extra)
    return base


class ContinuityRequirementAnchorTests(unittest.TestCase):
    def test_req_s06_01_empty_inputs_build_without_error(self):
        """REQ-S06-01：读不到分镜／资产时按空分镜／空资产计算，不报错。"""
        for shots, assets in (([], {}), ([], None), (None, None)):
            ledger = continuity_ledger.build(shots, assets)
            self.assertEqual(ledger['version'], 1)
            self.assertEqual(ledger['summary'],
                             {'batches': 0, 'shots': 0, 'ok': True, 'problems': []})

    def test_req_s06_10_build_is_local_and_never_calls_model(self):
        """REQ-S06-10：台账由 continuity_ledger.build 按规则现场计算，不调用模型。"""
        shots = [_shot(), _shot(shot_id='S02', costume_id='CST-01')]
        with patch('pet_llm.Client.ask', side_effect=AssertionError('build 不应调用模型')) as ask:
            ledger = continuity_ledger.build(shots, _assets())
        ask.assert_not_called()
        # 现场计算的结果确定、完整（非模型输出），且两遍一致。
        self.assertEqual(ledger['prompt'], continuity_ledger.PROMPT)
        self.assertEqual(ledger['summary']['shots'], 2)
        self.assertEqual(continuity_ledger.build(shots, _assets()), ledger)

    def test_req_s06_12_anchors_are_verbatim_from_assets(self):
        """REQ-S06-12：冻结锚点逐字取自资产——角色含服装状态覆盖、场景拼光源／空间锚点／尺度、道具拼材质／尺度。"""
        anchors = continuity_ledger.anchors_of(_shot(), _assets())
        by_kind = {(a['kind'], a['id']): a for a in anchors}
        self.assertEqual(by_kind[('character', 'CHAR_001')]['anchor'],
                         '黑发齐刘海；状态覆盖：穿红裙')
        self.assertEqual(by_kind[('character', 'CHAR_001')]['state'], 'CST-01')
        self.assertEqual(by_kind[('scene', 'LOC_001')]['anchor'],
                         '光源：左上；门@左侧（木）；窗@右侧；尺度：人身高 1.7m')
        self.assertEqual(by_kind[('prop', 'PROP_001')]['anchor'], '银；一掌大小')

    def test_req_s06_12_missing_asset_fields_add_nothing(self):
        """REQ-S06-12：资产里没有的字段不补、不改写——没有锚点就不生成对应冻结项。"""
        assets = {'CHAR_002': {'name': '无锚点角色'}, 'PROP_002': {'material': '', 'scale': ''}}
        anchors = continuity_ledger.anchors_of(
            {'id': 'S01', 'location': 'LOC_002', 'characters': ['CHAR_002'], 'props': ['PROP_002']},
            assets)
        self.assertEqual(anchors, ())

    def test_req_s06_13_conflict_kinds_and_adjudication(self):
        """REQ-S06-13：参考图冲突两类（职责自相矛盾／多图抢同一件事）；先出现的负责身份，其余只补风格与光影。"""
        self_contradict = continuity_ledger.conflicts([{
            'id': 'S01', 'location': 'LOC_001', 'characters': ['CHAR_001'],
            'character_refs': ['@图片1'],
            'reference_roles': {'@图片1': {'responsibility': '面部、发型、服装、场景', 'exclude': ''}},
        }])
        self.assertEqual(self_contradict[0]['kind'], '职责自相矛盾')
        self.assertEqual(self_contradict[0]['detail'],
                         '@图片1 的职责里写了场景，但排除项没写它——一张参考图不能既管身份又管它')

        grab = continuity_ledger.conflicts([{
            'id': 'S02', 'location': 'LOC_001', 'characters': ['CHAR_001'],
            'character_refs': ['@图片1', '@图片2'],
            'reference_roles': {
                '@图片1': {'responsibility': '面部、发型', 'exclude': '场景、动作、镜头'},
                '@图片2': {'responsibility': '面部、发型', 'exclude': '场景、动作、镜头'},
            },
        }])
        self.assertEqual(grab[0]['kind'], '多图抢同一件事')

        decided = continuity_ledger.adjudicate(self_contradict + grab)
        self.assertEqual(decided[0]['priority'], ['@图片1'])
        self.assertEqual(decided[1]['priority'], ['@图片1', '@图片2'])
        self.assertIn('只补风格与光影', decided[1]['resolution'])

    def test_req_s06_14_triplets_one_row_per_batch_and_does_not_resplit(self):
        """REQ-S06-14：三元组每批一行；同批内三元组出现多种即不通过、提示重切批次；本阶段不改批次划分。"""
        shots = [_shot(batch_id='B01'), _shot(shot_id='S02', costume_id='CST-02', batch_id='B01')]
        rows = continuity_ledger.triplets(shots)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['batch_id'], 'B01')
        self.assertFalse(rows[0]['ok'])
        self.assertIn('重切批次', rows[0]['detail'])
        continuity_ledger.build(shots, {})
        self.assertEqual([s['batch_id'] for s in shots], ['B01', 'B01'])  # 未改写批次划分

    def test_req_s06_14_consistent_triplet_passes(self):
        """REQ-S06-14：同批内 scene_id＋character_ids＋costume_id 一致时通过。"""
        shots = [_shot(), _shot(shot_id='S02')]
        rows = continuity_ledger.triplets(shots)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['ok'])
        self.assertEqual(rows[0]['detail'], '一致')

    def test_req_s06_15_cross_batch_consistency_and_flags(self):
        """REQ-S06-15：同一锚点（类型＋编号＋状态）跨批次字符串一致即通过；continuity_flags 记为「全程必须保住」。"""
        shots = [_shot(batch_id='B01', continuity_flags=['主角耳环始终佩戴']),
                 _shot(shot_id='S02', batch_id='B02')]
        rows = continuity_ledger.cross_batch(shots, _assets())
        by_key = {(r['kind'], r['id'], r['state']): r for r in rows}
        char = by_key[('character', 'CHAR_001', 'CST-01')]
        self.assertTrue(char['ok'])
        self.assertIn('锚点一致', char['detail'])
        flags = [r for r in rows if r['kind'] == 'flag']
        self.assertIn('全程必须保住：主角耳环始终佩戴', [r['detail'] for r in flags])

    def test_req_s06_17_build_does_not_mutate_or_regenerate(self):
        """REQ-S06-17：本阶段不改分镜、不改资产、不重新描述锚点（锚点逐字取自资产原文）。"""
        shots = [_shot()]
        assets = _assets()
        shots_before, assets_before = deepcopy(shots), deepcopy(assets)
        ledger = continuity_ledger.build(shots, assets)
        self.assertEqual(shots, shots_before)
        self.assertEqual(assets, assets_before)
        anchors = [a['anchor'] for a in ledger['batches'][0]['frozen_anchors']]
        self.assertIn('黑发齐刘海；状态覆盖：穿红裙', anchors)
        self.assertIn('光源：左上；门@左侧（木）；窗@右侧；尺度：人身高 1.7m', anchors)
        self.assertIn('银；一掌大小', anchors)

    def test_req_s06_21_issues_have_stable_ids_and_states(self):
        """REQ-S06-21：问题编号稳定 CI-<类型>-<范围>，状态待处理／已忽略／已解除，修好自动解除。"""
        ledger = continuity_ledger.build([{
            'id': 'S01', 'location': 'LOC_001', 'characters': ['CHAR_001'],
            'character_refs': ['@图片1'],
            'reference_roles': {'@图片1': {'responsibility': '面部、发型、服装、场景', 'exclude': ''}},
        }], {})
        found = continuity_ledger.issues(ledger)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['id'], 'CI-conflict-S01')
        self.assertEqual(found[0]['severity'], '高')
        self.assertEqual(found[0]['kind_label'], '职责自相矛盾')
        # 同一份台账算出来编号稳定。
        self.assertEqual(continuity_ledger.issues(ledger)[0]['id'], 'CI-conflict-S01')
        # 修好（本轮不再出现）自动解除。
        register, _ = continuity_ledger.merge_issues({}, found, now='t1')
        self.assertEqual(register['CI-conflict-S01']['state'], 'open')
        register2, _ = continuity_ledger.merge_issues(register, [], now='t2')
        self.assertEqual(register2['CI-conflict-S01']['state'], 'resolved')

    def test_req_s06_21_ignore_requires_reason_and_reopens_on_evidence_change(self):
        """REQ-S06-21：忽略必须写理由并记证据摘要；证据变化或问题复现则重开。"""
        ledger = continuity_ledger.build([{
            'id': 'S01', 'location': 'LOC_001', 'characters': ['CHAR_001'],
            'character_refs': ['@图片1'],
            'reference_roles': {'@图片1': {'responsibility': '面部、发型、服装、场景', 'exclude': ''}},
        }], {})
        issue = continuity_ledger.issues(ledger)[0]
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            publish = lambda path, data: save(path, data)
            continuity_ledger.sync_issues(project, ledger, publish=publish)
            with self.assertRaisesRegex(ValueError, '必须写明理由'):
                continuity_ledger.decide_issue(project, issue['id'], 'ignored', '', publish=publish)
            continuity_ledger.decide_issue(project, issue['id'], 'ignored', '观众视角不重要', publish=publish)
            row = continuity_ledger.read_issues(project)[issue['id']]
            self.assertEqual(row['state'], 'ignored')
            self.assertEqual(row['decision']['reason'], '观众视角不重要')
            self.assertTrue(row['decision']['digest'])  # 记下当时那版证据摘要
        # 忽略时证据变了 → 重开；证据没变 → 保持忽略。
        register, _ = continuity_ledger.merge_issues({}, [issue], now='t1')
        ignored = dict(register[issue['id']]); ignored['state'] = 'ignored'
        ignored['decision'] = {'reason': 'x', 'digest': issue['digest']}
        register[issue['id']] = ignored
        same, _ = continuity_ledger.merge_issues(register, [issue], now='t2')
        self.assertEqual(same[issue['id']]['state'], 'ignored')
        changed = dict(issue); changed['digest'] = '0' * 12
        reopened, _ = continuity_ledger.merge_issues(register, [changed], now='t3')
        self.assertEqual(reopened[issue['id']]['state'], 'open')

    def test_req_s06_21_sync_only_writes_when_publish_injected(self):
        """REQ-S06-21：只有 L3 注入发布器才落盘 continuity_issues.json，否则只读预览。"""
        ledger = continuity_ledger.build([{
            'id': 'S01', 'location': 'LOC_001', 'characters': ['CHAR_001'],
            'character_refs': ['@图片1'],
            'reference_roles': {'@图片1': {'responsibility': '面部、发型、服装、场景', 'exclude': ''}},
        }], {})
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            rows = continuity_ledger.sync_issues(project, ledger)  # 未注入 publish
            self.assertEqual(len(rows), 1)
            self.assertFalse(continuity_ledger.issues_path(project).is_file())
            continuity_ledger.sync_issues(project, ledger, publish=lambda p, d: save(p, d))
            self.assertTrue(continuity_ledger.issues_path(project).is_file())

    def test_req_s06_31_tools_registered_and_build_ledger_writes(self):
        """REQ-S06-31：continuity.* 工具在 skill_tools 登记；continuity.buildLedger 调 build/write 本地落盘，其余对应页面裁决／校验表。"""
        self.assertIn('continuity.buildLedger', skill_tools.READY)
        self.assertEqual(skill_tools.status_of('continuity.buildLedger'), 'ready')
        for tool in ('continuity.resolveConflict', 'continuity.freezeAnchors',
                     'continuity.checkCrossBatch', 'continuity.checkTriplets',
                     'continuity.auditDrift', 'continuity.audit', 'continuity.validate'):
            with self.subTest(tool=tool):
                self.assertIn(tool, skill_tools.PAGES)
                self.assertEqual(skill_tools.status_of(tool), 'page')
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            result = skill_tools.call('continuity.buildLedger',
                                      {'project': str(project), 'episode': {'shots': [_shot()]}})
            self.assertTrue(result['ok'])
            self.assertTrue(Path(result['ledger']).is_file())


if __name__ == '__main__':
    unittest.main()
