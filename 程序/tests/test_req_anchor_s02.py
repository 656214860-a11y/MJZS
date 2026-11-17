# -*- coding: utf-8 -*-
"""REQ-S02-01/03/10/11/12/13/14/20/21/22/24：剧本结构阶段的唯一输入、依赖与重试、
本地规则提取、六步流程、四区档案字段、只认原稿事实、校验重提取与矛盾停止、原子发布与
血缘、结构剧本判定与原稿删除隐藏、完成证据、新稿位置与旧目录只读。

这些编号原登记在 `维护记录/需求锚定基线.json` 的 `untested_done`，本轮补上落在真实代码
行为上的锚点。全部断言针对 `script_contract`／`stage_flow`／`stage_parallel`／
`stage_exec`／`stage_completion_service`／`skill_templates` 的真实函数与常量，未 mock 被测
事实、未改产品代码；需要落盘时一律在 `tempfile.TemporaryDirectory()` 隔离目录内进行。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_contract
from orchestrator import skill_orchestrator
from orchestrator import skill_templates
import stage_completion_service
import stage_exec
import stage_execution_service
import stage_flow
import stage_parallel

GOOD_RAW = (
    '第 1 集\n'
    '场景 1：夜，旧书店内\n'
    '林小满：把旧怀表交给我。\n'
    '陆时：先离开这里。\n'
    '道具：旧怀表\n'
    '林小满愤怒地望向门口，身上穿着蓝色连衣裙，黑发齐刘海。\n'
)
RICH_RAW = '林小满又名小满。\n\n' + GOOD_RAW
BARE_RAW = '第 1 集\n场景 1：夜，旧书店内\n林小满：把怀表交给我。\n'
CONFLICT_RAW = (
    '第 1 集\n'
    '场景 1：夜，旧书店内\n'
    '林小满：把旧怀表交给我。\n'
    '道具：旧怀表（直径 5 厘米）\n'
    '道具：旧怀表（直径 8 厘米）\n'
)
STEP_ACTIONS = ('read_script_raw', 'writer_extract_structure', 'editor_review_structure',
                'writer_revise_structure', 'editor_final_review', 'write_structured_script')


def _script_dir(root):
    from contract.stage_path_service import write_dir
    return write_dir(root, 'script')


def _natural_script(root, text=GOOD_RAW, name='我的剧本_自然剧本_20260101.md'):
    folder = _script_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding='utf-8')
    return path


def _desktop(root):
    subject = type('Stub', (), {})()
    subject.root = root
    return subject


class ScriptStructureRequirementAnchorTests(unittest.TestCase):
    def test_req_s02_01_only_adopted_natural_script_is_the_input(self):
        """REQ-S02-01：唯一输入是 S01 被采用的自然剧本；找不到就报错停止、不产出；设定／大纲／角色卡不入本阶段。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertIsNone(script_contract.resolve_script_source(root))
            with self.assertRaises(ValueError):
                script_contract.write_structured_script(root)
            self.assertFalse(script_contract.canonical_structured_script_path(root).exists())
        with tempfile.TemporaryDirectory() as td:
            # 只有 S01 的设定／大纲／角色卡，不构成结构阶段的输入。
            root = Path(td)
            folder = _script_dir(root)
            folder.mkdir(parents=True)
            for name in ('P_项目大纲_故事梗概_20260101.md', 'P_项目设定_世界观_20260101.md',
                         'P_角色卡_林小满_20260101.md'):
                (folder / name).write_text(GOOD_RAW, encoding='utf-8')
            self.assertEqual(script_contract.natural_script_paths(root), ())
            self.assertIsNone(script_contract.resolve_script_source(root))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            self.assertEqual(script_contract.resolve_script_source(root), source)

    def test_req_s02_03_depends_on_s01_retries_twice_then_blocks_and_never_skips(self):
        """REQ-S02-03：依赖 S01 完成；自动链上 S02 失败不跳过；单 Agent 串行，失败重试 2 次后阻塞。"""
        self.assertEqual(stage_flow.DEPENDS['script_structure'], ('script',))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / '工作流任务' / '宠物' / '阶段状态.json'
            state_file.parent.mkdir(parents=True)
            state_file.write_text(json.dumps({'stages': {'script': {'state': 'failed'}}}),
                                  encoding='utf-8')
            self.assertEqual(stage_flow.blockers(root, 'script_structure'), ['script'])
            state_file.write_text(json.dumps({'stages': {'script': {'state': 'success'}}}),
                                  encoding='utf-8')
            self.assertEqual(stage_flow.blockers(root, 'script_structure'), [])
        # 串行（单 Agent、并行度 1）＋ 重试 2 次后 block。
        config = stage_parallel.config('script_structure')
        self.assertEqual(config['unit'], stage_parallel.NONE)
        self.assertEqual(stage_parallel.degree('script_structure'), (1, 1))
        self.assertEqual(stage_parallel.concurrency_limit('script_structure'), 1)
        self.assertFalse(stage_parallel.serial_within('script_structure'))
        self.assertEqual(stage_parallel.retry_attempts('script_structure'), 2)
        self.assertEqual(stage_parallel.on_exhaust('script_structure'), stage_parallel.ON_BLOCK)
        # 自动链：即使下游被误标为完成，失败的结构阶段仍是要先修的那一步，不跳过。
        auto = stage_flow.Auto()
        states = {stage: 'pending' for stage in stage_flow.OWN_ORDER}
        states.update(script='success', script_structure='failed', storyboard='success')
        self.assertTrue(auto.arm_from('auto', states))
        self.assertEqual(auto.next_stage(), 'script_structure')

    def test_req_s02_10_local_rules_mark_and_never_call_model(self):
        """REQ-S02-10：默认路径是本地规则整理，不调用模型，并在正稿中标明「本地规则提取」。"""
        with patch('pet_llm.Client.ask', side_effect=AssertionError('本地规则不应调用模型')) as ask:
            text = script_contract.structure_script(GOOD_RAW)
        ask.assert_not_called()
        self.assertIn('本地规则提取', text)
        self.assertIn('未调用模型', text)
        self.assertIn('# 结构化剧本', text)
        # 同一输入两遍一致（本地规则、确定性），不是模型输出。
        self.assertEqual(script_contract.structure_script(GOOD_RAW), text)

    def test_req_s02_11_six_steps_in_order_and_manual_run_confirms_them(self):
        """REQ-S02-11：流程固定六步（读原稿→提取→校验→按反馈重提取→复审→写入）；点手动制作即确认六步、不再逐步问。"""
        template = skill_templates.load_template('script_structure')
        self.assertEqual(tuple(step.action for step in template.steps), STEP_ACTIONS)
        self.assertTrue(all(not step.needs_confirmation for step in template.steps))
        with tempfile.TemporaryDirectory() as td:
            actions = []
            orchestrator = skill_orchestrator.Orchestrator(project=td)
            run = orchestrator.run_stage_with_template(
                'script_structure', mode='auto', names=[],
                wait_for_user=lambda question: self.fail('手动入口不应再逐步询问：' + str(question)),
                execute_action=lambda action, context: (actions.append(action), {'ok': True, 'summary': action})[1])
            self.assertTrue(run['ok'])
            self.assertEqual(tuple(actions), STEP_ACTIONS)

    def test_req_s02_12_four_archives_and_fields(self):
        """REQ-S02-12：结构剧本含角色／场景／道具档案与分场剧本四区，各区字段齐全。"""
        text = script_contract.structure_script(RICH_RAW)
        for heading in ('## 角色档案', '## 场景档案', '## 道具档案', '## 分场剧本'):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)
        for field in ('- 别名：', '- 跨集 ID：', '- 物理特征：', '- 默认服装：', '- 换装需求：',
                      '- 空间锚点：', '- 光照方向：', '- 尺度参考：',
                      '- 出场角色：', '- 情绪基调：', '- 起始状态：', '- 结束状态：', '- 正文：'):
            with self.subTest(field=field):
                self.assertIn(field, text)

    def test_req_s02_13_only_facts_from_the_raw_and_unknown_marked_for_confirmation(self):
        """REQ-S02-13：只认原稿写出的事实；原稿没写的一律标「待确认」，不编造。"""
        text = script_contract.structure_script(RICH_RAW)
        self.assertIn('- 别名：小满（来源：原稿声明）', text)  # 原稿明确声明的别名逐字采用
        bare = script_contract.structure_script(BARE_RAW)
        self.assertNotIn('陆时', bare)  # 原稿没有的角色程序不补
        for field in ('- 别名：待确认', '- 换装需求：待确认', '- 尺度参考：待确认',
                      '- 起始状态：待确认', '- 结束状态：待确认'):
            with self.subTest(field=field):
                self.assertIn(field, bare)

    def test_req_s02_14_failed_review_revises_and_source_contradiction_stops(self):
        """REQ-S02-14：校验不通过按反馈重提取；复审不过不写入；原稿自相矛盾不静默修补，停止并提示先改原稿。"""
        structured = script_contract.structure_script(GOOD_RAW)
        review = script_contract.review_structured_script(GOOD_RAW, structured)
        self.assertTrue(review['approved'])
        self.assertEqual(review['feedback'], ())
        # 缺区块时给出可展示的反馈。
        broken = script_contract.review_structured_script(GOOD_RAW, '# 结构化剧本\n本地规则提取\n')
        self.assertFalse(broken['approved'])
        self.assertTrue(any('缺少' in note for note in broken['feedback']))
        # 原稿同一道具多种尺寸：不修补、不臆造，抛错让用户先改原稿。
        conflict_review = script_contract.review_structured_script(
            CONFLICT_RAW, script_contract.structure_script(CONFLICT_RAW))
        self.assertFalse(conflict_review['approved'])
        self.assertTrue(any('互相矛盾的尺寸' in note for note in conflict_review['feedback']))
        self.assertTrue(any('script_raw.md' in note for note in conflict_review['feedback']))
        with self.assertRaisesRegex(ValueError, '互相矛盾的尺寸'):
            script_contract.revise_structured_script(CONFLICT_RAW, conflict_review['feedback'])
        # 端到端：矛盾原稿在真实六步链上停在重提取，绝不写出结构剧本。
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _natural_script(root, CONFLICT_RAW)
            with patch.object(stage_execution_service, 'build_orchestrator',
                              lambda desktop, project: skill_orchestrator.Orchestrator(project=project)):
                with patch.object(stage_execution_service, 'stage_context', lambda *a, **k: {}):
                    run = stage_exec._run_script_structure(_desktop(root), root, [], 'manual')
            self.assertFalse(run['ok'])
            self.assertTrue(any('互相矛盾的尺寸' in str(error) for error in run['errors']))
            self.assertFalse(script_contract.canonical_structured_script_path(root).exists())

    def test_req_s02_20_publish_is_atomic_raw_unchanged_and_lineage_recorded(self):
        """REQ-S02-20：结构剧本只能经 write_structured_script 原子发布；空正文拒绝；原稿不变；发布同时记来源血缘。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            target = script_contract.canonical_structured_script_path(root)
            with self.assertRaisesRegex(ValueError, '不能为空'):
                script_contract.write_structured_script(root, content='  \n', source=source)
            self.assertFalse(target.exists())
            self.assertEqual(source.read_text(encoding='utf-8'), GOOD_RAW)  # 原稿保持不变
            # 注入发布器时只由发布器落盘：script_contract 自己不写目标。
            published = []
            script_contract.write_structured_script(
                root, content='# 结构化剧本\n## 角色档案\n## 分场剧本\n', source=source,
                publisher=lambda path, text, validate, update: published.append((path, text)))
            self.assertEqual(len(published), 1)
            self.assertFalse(target.exists())
            # 正常发布：经真实发布器落盘并留下来源血缘（原稿路径与摘要）。
            script_contract.write_structured_script(root, content=None, source=source)
            self.assertTrue(target.is_file())
            self.assertEqual(source.read_text(encoding='utf-8'), GOOD_RAW)
            ledger = target.parent / '产物来源关系.json'
            entries = json.loads(ledger.read_text(encoding='utf-8'))['entries']
            entry = next(row for row in entries if row['artifact'].endswith(target.name))
            self.assertEqual(entry['source'], '01剧本准备/' + source.name)
            self.assertTrue(entry['source_sha256'])

    def test_req_s02_21_qualified_structure_script_and_hidden_when_raw_deleted(self):
        """REQ-S02-21：需标题「# 结构化剧本」＋档案区且来源不是大纲／梗概；记录的原稿删除后不再显示、文件不删。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / '有档案.md'
            good.write_text('# 结构化剧本\n## 角色档案\n> 来源：`b_自然剧本_20260101.md`\n', encoding='utf-8')
            self.assertTrue(script_contract.is_structured_script(good))
            outline = root / '大纲稿.md'
            outline.write_text('# 结构化剧本\n## 角色档案\n> 来源：`b_项目大纲_20260101.md`\n', encoding='utf-8')
            self.assertFalse(script_contract.is_structured_script(outline))
            bare = root / '无标题.md'
            bare.write_text('正文\n', encoding='utf-8')
            self.assertFalse(script_contract.is_structured_script(bare))
            self.assertFalse(script_contract.is_structured_script(u'缺少档案.md'))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            target = script_contract.write_structured_script(root, source=source)
            self.assertIn(target, script_contract.structured_script_paths(root))
            source.unlink()
            self.assertEqual(script_contract.structured_script_paths(root), ())
            self.assertTrue(target.is_file())  # 只隐藏，不删文件

    def test_req_s02_22_completion_evidence_is_the_structure_script_not_hints(self):
        """REQ-S02-22：阶段完成＝能解析到合格结构剧本；文件／清单存在与界面文字都不算证据。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(stage_completion_service.completion_evidence(root, 'script_structure')[0], False)
            # 只有三份 manifest、没有结构剧本：不算完成。
            script_contract.write_structure_manifests(root, script_contract.structure_script(GOOD_RAW))
            self.assertFalse(stage_completion_service.completion_evidence(root, 'script_structure')[0])
            events = []
            emit = lambda *args, **kwargs: (events.append((args, kwargs)), {'ok': True})[1]
            ok, _detail, _emitted = stage_completion_service.emit_verified_completion(
                root, 'script_structure', '模型说做完了', emit)
            self.assertFalse(ok)
            self.assertEqual(events, [])
            # 出现合格结构剧本后才有证据，事件才发出。
            source = _natural_script(root)
            script_contract.write_structured_script(root, source=source)
            ok, _detail, _emitted = stage_completion_service.emit_verified_completion(
                root, 'script_structure', '完成', emit)
            self.assertTrue(ok)
            self.assertEqual([args[0] for args, _kwargs in events], ['stage.completed'])
            self.assertEqual(events[0][1]['stage'], 'script_structure')

    def test_req_s02_24_new_script_lands_in_stage_dir_and_legacy_is_read_only(self):
        """REQ-S02-24：新结构剧本写入 02剧本结构/结构剧本/；旧 writing/ 只读兼容，不再写回。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canonical = script_contract.canonical_structured_script_path(root)
            self.assertEqual(canonical.parent.name, '结构剧本')
            self.assertEqual(canonical.parent.parent.name, '02剧本结构')
            legacy_dir = root / 'writing' / '结构剧本'
            legacy_dir.mkdir(parents=True)
            legacy = legacy_dir / '旧结构.md'
            legacy.write_text('# 结构化剧本\n## 分场剧本\n旧正文\n', encoding='utf-8')
            self.assertIn(legacy, script_contract.structured_script_paths(root))
            source = _natural_script(root)
            written = script_contract.write_structured_script(root, source=source)
            self.assertEqual(written, canonical)
            self.assertNotIn('writing', written.parts)
            self.assertEqual(legacy.read_text(encoding='utf-8'), '# 结构化剧本\n## 分场剧本\n旧正文\n')
            self.assertFalse((root / 'writing' / 'script.md').exists())


if __name__ == '__main__':
    unittest.main()
