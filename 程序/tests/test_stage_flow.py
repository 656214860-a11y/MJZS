# -*- coding: utf-8 -*-
"""第 54 期附件二／四：手动按钮的状态化 ＋ 三虎自动推进那条链。

附件二第 4／5 条那张表就是这一份的口径：

* 三虎正在跑某一步 → 那颗按钮写「自动执行中」、置灰、不可点；
* 没在跑 → 「手动制作{阶段简称}」、可点；
* 状态只认总线上那四条事件（stage.executing／completed／failed／paused）。

附件四那条链：剧本做完（script.completed）＋ 等级是 semi／auto 才武装，之后按依赖图
一步一步走；暂停／恢复就是 Auto.pause／resume。

运行：python test_stage_flow.py
"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

import stage_flow


class FakeButton:
    """只认 cget／configure 的最小按钮替身。"""

    def __init__(self, text='', state='normal'):
        self.text, self.state = text, state

    def cget(self, key):
        return self.text if key == 'text' else self.state

    def configure(self, **kw):
        if 'text' in kw:
            self.text = kw['text']
        if 'state' in kw:
            self.state = kw['state']


class LabelTests(unittest.TestCase):
    """附件二第 3 条那张对照表，一个字都不能走样。"""

    def test_the_table_matches_the_spec(self):
        self.assertEqual(stage_flow.MANUAL_LABELS, {
            'script': '手动制作剧本', 'script_structure': '手动制作结构剧本',
            'storyboard': '手动制作分镜', 'animatic': '手动制作分镜预演',
            'assets': '手动制作资产',
            'continuity': '手动生成连贯性清单',
            'final': '手动同步资产', 'keyframe': '手动制作首帧', 'previs': '手动制作白模',
            'video': '手动制作视频', 'audio': '手动制作配音', 'edit': '手动制作剪辑',
            'delivery': '手动制作交付'})

    def test_every_stage_is_covered_and_unique(self):
        from pet_bus import STAGES
        self.assertEqual(sorted(stage_flow.MANUAL_LABELS), sorted(STAGES))
        self.assertEqual(len(set(stage_flow.MANUAL_LABELS.values())), len(STAGES))

    def test_the_unknown_stage_falls_back_to_its_stage_name(self):
        self.assertEqual(stage_flow.manual_label('nope'), '手动制作nope')


class RunningTests(unittest.TestCase):
    """附件二第 2／5 条：按钮的文字与可点状态跟着那四条事件走。"""

    def setUp(self):
        stage_flow.reset()
        self.addCleanup(stage_flow.reset)

    def test_idle_offers_the_manual_action(self):
        self.assertEqual(stage_flow.button_text('assets'), '手动制作资产')
        self.assertEqual(stage_flow.button_state('assets'), 'normal')

    def test_an_auto_run_says_auto_and_goes_grey(self):
        stage_flow.mark('assets', 'stage.executing', 'auto')
        self.assertEqual(stage_flow.button_text('assets'), '自动执行中')
        self.assertEqual(stage_flow.button_state('assets'), 'disabled')

    def test_a_manual_run_is_labelled_manual(self):
        stage_flow.mark('assets', 'stage.executing', 'manual')
        self.assertEqual(stage_flow.button_text('assets'), '手动执行中')
        self.assertEqual(stage_flow.button_state('assets'), 'disabled')

    def test_only_this_stage_changes(self):
        stage_flow.mark('assets', 'stage.executing', 'auto')
        self.assertEqual(stage_flow.button_text('video'), '手动制作视频')

    def test_every_finishing_event_restores_the_button(self):
        for kind in ('stage.completed', 'stage.failed', 'stage.paused'):
            with self.subTest(kind=kind):
                stage_flow.reset()
                stage_flow.mark('video', 'stage.executing', 'auto')
                stage_flow.mark('video', kind)
                self.assertFalse(stage_flow.running('video'))
                self.assertEqual(stage_flow.button_text('video'), '手动制作视频')

    def test_an_unregistered_kind_is_ignored(self):
        self.assertFalse(stage_flow.mark('video', 'asset.reference.found'))
        self.assertFalse(stage_flow.running('video'))
        self.assertFalse(stage_flow.mark(None, 'stage.executing'))


class ApplyTextTests(unittest.TestCase):
    """按钮刷新：置灰只认自己按下去的那一次，不和页面上别的闸抢。"""

    def setUp(self):
        stage_flow.reset()
        self.addCleanup(stage_flow.reset)

    def test_a_running_stage_greys_the_button(self):
        button = FakeButton('手动制作资产')
        stage_flow.mark('assets', 'stage.executing', 'auto')
        self.assertTrue(stage_flow.apply_text(button, 'assets'))
        self.assertEqual(button.text, '自动执行中')
        self.assertEqual(button.state, 'disabled')
        self.assertFalse(stage_flow.apply_text(button, 'assets'), "第二次没变化")

    def test_the_button_comes_back_when_the_stage_settles(self):
        button = FakeButton('手动制作资产')
        stage_flow.mark('assets', 'stage.executing', 'auto')
        stage_flow.apply_text(button, 'assets')
        stage_flow.mark('assets', 'stage.completed')
        self.assertTrue(stage_flow.apply_text(button, 'assets'))
        self.assertEqual(button.text, '手动制作资产')
        self.assertEqual(button.state, 'normal')

    def test_someone_elses_disabled_button_is_left_alone(self):
        """资产页「没勾选就不给按」的置灰照旧归它自己，我们不许把它点亮。"""
        button = FakeButton('手动制作资产', state='disabled')
        stage_flow.apply_text(button, 'assets')
        self.assertEqual(button.state, 'disabled')


class ListenTests(unittest.TestCase):
    """附件二第 5 条：状态同步的来源就是总线那四条事件。"""

    def setUp(self):
        import pet_bus
        stage_flow.reset()
        self.addCleanup(stage_flow.reset)
        self.pet_bus = pet_bus

    def test_the_bus_events_drive_the_button(self):
        bus = self.pet_bus.Bus()
        self.assertIsNotNone(stage_flow.listen(bus))
        bus.emit('stage.executing', stage='previs', trigger='auto'); bus.pump()
        self.assertEqual(stage_flow.button_text('previs'), '自动执行中')
        bus.emit('stage.completed', stage='previs'); bus.pump()
        self.assertEqual(stage_flow.button_text('previs'), '手动制作白模')

    def test_the_bus_events_are_registered_in_the_contract(self):
        for kind in ('stage.executing', 'stage.paused'):
            with self.subTest(kind=kind):
                item = self.pet_bus.event(kind, stage='video')
                self.assertEqual(item['kind'], kind)

    def test_a_wrong_stage_is_rejected(self):
        with self.assertRaises(ValueError):
            self.pet_bus.event('stage.executing', stage='nope')

    def test_no_bus_is_not_a_problem(self):
        self.assertIsNone(stage_flow.listen(None))


class SummaryTests(unittest.TestCase):
    """附件三那三行：模型／SKILL 数量／预计（付费还是免费）＋ 依赖警告。"""

    def setUp(self):
        import stage_flow as module
        self.module = module

    @staticmethod
    def project(td, state=None):
        proj = Path(td) / 'p'
        (proj / '工作流任务' / '宠物').mkdir(parents=True)
        if state:
            (proj / '工作流任务' / '宠物' / '阶段状态.json').write_text(
                json.dumps(state, ensure_ascii=False), encoding='utf-8')
        return proj

    @staticmethod
    def desktop(proj):
        subject = type('Stub', (), {})()
        subject.root = proj
        subject.app = HERE
        return subject

    def test_the_lines_are_at_most_four(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            lines = self.module.summary_lines(self.desktop(proj), 'storyboard')
            self.assertLessEqual(len(lines), 4)
            self.assertTrue(lines[0].startswith('模型：'))
            self.assertTrue(lines[1].startswith('SKILL：'))

    def test_the_estimate_counts_the_chosen_skills(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            names = self.module.selected_skills(proj, 'storyboard')
            data = self.module.step_summary(self.desktop(proj), 'storyboard', proj)
            self.assertEqual(data['skills'], len(names))
            self.assertGreater(len(names), 0, '这一阶段默认勾着 SKILL')

    def test_a_failed_dependency_blocks_direct_run(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td, {'stages': {'final': {'state': 'failed'}}})
            self.assertEqual(self.module.blockers(proj, 'keyframe'), ['final'])
            lines = self.module.summary_lines(self.desktop(proj), 'keyframe')
            self.assertIn('依赖：分镜定稿未完成', lines[-1])
            self.assertLessEqual(len(lines), 4)

    def test_a_pending_dependency_does_not_block(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td, {'stages': {'final': {'state': 'pending'}}})
            self.assertEqual(self.module.blockers(proj, 'keyframe'), [])

    def test_no_state_file_at_all_does_not_block(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            for stage in ('storyboard', 'assets', 'final', 'keyframe'):
                expected = ['animatic'] if stage == 'assets' else []
                self.assertEqual(self.module.blockers(proj, stage), expected)
            self.assertEqual(self.module.blockers(proj, 'animatic'), ['storyboard'])

    def test_the_graph_starts_at_the_script(self):
        self.assertEqual(self.module.DEPENDS['script'], ())
        self.assertEqual(self.module.DEPENDS['script_structure'], ('script',))
        self.assertEqual(self.module.DEPENDS['storyboard'], ('script_structure',))
        self.assertEqual(self.module.DEPENDS['delivery'], ('edit',))


class AutoTests(unittest.TestCase):
    """附件四：剧本做完之后按依赖图推进，暂停／恢复可用。"""

    def test_the_chain_walks_the_twelve_stages_in_order(self):
        from pet_bus import STAGES
        auto = stage_flow.Auto()
        self.assertTrue(auto.script_done('semi'))
        self.assertEqual(auto.pending(), list(STAGES))
        self.assertEqual(auto.next_stage(), 'script')
        auto.done('script')
        self.assertEqual(auto.next_stage(), 'script_structure')

    def test_only_semi_and_auto_arm_the_chain(self):
        auto = stage_flow.Auto()
        self.assertFalse(auto.script_done('hint'), '只提醒档不自动跑全流程')
        self.assertEqual(auto.pending(), [])
        self.assertIsNone(auto.next_stage())

    def test_pause_stops_and_resume_continues(self):
        auto = stage_flow.Auto()
        auto.script_done('auto')
        auto.next_stage()
        auto.pause()
        self.assertIsNone(auto.next_stage(), '暂停时不再往下推')
        auto.resume()
        self.assertIsNone(auto.next_stage(), '恢复后仍须等待已派发的剧本阶段收场')
        auto.done('script')
        self.assertEqual(auto.next_stage(), 'script_structure', '收场后从下一阶段接着走')

    def test_the_chain_ends(self):
        auto = stage_flow.Auto()
        auto.script_done('auto')
        seen = []
        while True:
            stage = auto.next_stage()
            if stage is None:
                break
            seen.append(stage)
            auto.done(stage)
        from pet_bus import STAGES
        self.assertEqual(seen, list(STAGES))
        self.assertIsNone(auto.next_stage())

    def test_finishing_a_later_stage_skips_ahead(self):
        auto = stage_flow.Auto()
        auto.script_done('auto')
        auto.done('storyboard')
        self.assertEqual(auto.next_stage(), 'animatic', '初稿之后先进行分镜预演')
        auto.done('animatic')
        self.assertEqual(auto.next_stage(), 'assets', '预演确认之后才进入资产管理')

    def test_a_failure_blocks_the_chain_at_the_same_stage(self):
        auto = stage_flow.Auto()
        auto.script_done('auto')
        self.assertEqual(auto.next_stage(), 'script')
        auto.done('script', False)
        self.assertIsNone(auto.next_stage())
        self.assertEqual(auto.pending()[0], 'script')
        self.assertEqual(auto.state()['blocked'], 'script')
        self.assertEqual(auto.history[-1][1], False)

    def test_the_state_snapshot_reads_clean(self):
        auto = stage_flow.Auto()
        auto.script_done('semi')
        state = auto.state()
        self.assertTrue(state['armed'])
        self.assertFalse(state['paused'])
        self.assertEqual(state['index'], 0)


class PetWiringTests(unittest.TestCase):
    """pet_ui 那一头的接缝：自动链优先、暂停把正在跑的那一步放回按钮。"""

    def setUp(self):
        import pet_bus, pet_ui
        stage_flow.reset()
        self.addCleanup(stage_flow.reset)
        self.pet_bus, self.pet_ui = pet_bus, pet_ui

    def pet(self):
        # agent 与 bus 在 Pet 上是只读属性，用子类把它们换成替身（只盯这一处接缝）。
        class Stub(self.pet_ui.Pet):
            agent = type('Agent', (), {'advance': lambda self: 'fallback'})()
            bus = None
        pet = object.__new__(Stub)
        pet.errors = []
        pet.auto = stage_flow.Auto()
        return pet

    def test_the_armed_chain_wins_over_the_state_machine(self):
        pet = self.pet()
        pet.auto.script_done('semi')
        self.assertEqual(pet.auto_stage(), 'script')

    def test_the_state_machine_still_drives_when_the_chain_is_idle(self):
        pet = self.pet()
        self.assertEqual(pet.auto_stage(), 'fallback')

    def test_paused_falls_back_to_the_state_machine(self):
        pet = self.pet()
        pet.auto.script_done('semi')
        pet.auto.pause()
        self.assertEqual(pet.auto_stage(), 'fallback')

    def test_pausing_restores_the_running_stage_button(self):
        pet = self.pet()
        bus = self.pet_bus.Bus()
        stage_flow.listen(bus)
        type(pet).bus = bus
        stage_flow.mark('video', 'stage.executing', 'auto')
        self.assertEqual(pet.pause_running_stage(), ['video'])
        bus.pump()
        self.assertEqual(stage_flow.button_text('video'), '手动制作视频')

    def test_pausing_with_nothing_running_is_a_no_op(self):
        pet = self.pet()
        type(pet).bus = self.pet_bus.Bus()
        self.assertEqual(pet.pause_running_stage(), [])



class _FakeSkill:
    """一个不碰任何文件、也不调工具的假 SKILL（只用来盯「谁发起」这条事件）。"""

    name = 'demo-skill'
    displayName = '演示'
    paid = False
    parallelizable = False
    tools = ()
    dependsOn = ()
    conflictsWith = ()

    def __init__(self, stage='previs'):
        self.stage = stage


class _FakeRegistry:
    def __init__(self, stage='previs'):
        self.stage = stage

    def getById(self, sid):
        return _FakeSkill(self.stage) if str(sid) == 'demo-skill' else None

    def getByStage(self, stage):
        return [_FakeSkill(stage)] if stage == self.stage else []

    def getAll(self):
        return [_FakeSkill(self.stage)]


class OrchestratorTriggerTests(unittest.TestCase):
    """附件二第 6 条：手动与自动共用同一台编排器，只有 trigger 不同（事件里看得见）。"""

    def setUp(self):
        import pet_bus, skill_orchestrator
        stage_flow.reset()
        self.addCleanup(stage_flow.reset)
        self.bus_module, self.orchestrator = pet_bus, skill_orchestrator

    def orchestrator_for(self, trigger='manual', stage='previs'):
        bus = self.bus_module.Bus()
        stage_flow.listen(bus)
        return bus, self.orchestrator.Orchestrator(registry=_FakeRegistry(stage), bus=bus,
                                                   trigger=trigger)

    def test_the_default_is_manual(self):
        self.assertEqual(self.orchestrator.Orchestrator().trigger, 'manual')

    def test_an_unknown_trigger_falls_back_to_manual(self):
        self.assertEqual(self.orchestrator.Orchestrator(trigger='nope').trigger, 'manual')

    def test_running_a_skill_announces_who_started_it(self):
        for trigger in ('auto', 'manual'):
            with self.subTest(trigger=trigger):
                stage_flow.reset()
                bus, orch = self.orchestrator_for(trigger)
                seen = []
                bus.subscribe('stage.executing', seen.append)
                orch.execute('demo-skill', {'project': HERE, 'stage': 'previs'})
                bus.pump()
                self.assertEqual([item['stage'] for item in seen], ['previs'])
                self.assertEqual([item.get('trigger') for item in seen], [trigger])
                self.assertFalse(stage_flow.running('previs'), '收场之后按钮就恢复可点')

    def test_run_can_override_the_trigger(self):
        bus, orch = self.orchestrator_for('manual')
        seen = []
        bus.subscribe('stage.executing', seen.append)
        orch.run(['demo-skill'], {'project': HERE, 'stage': 'previs'}, trigger='auto')
        bus.pump()
        self.assertEqual([item.get('trigger') for item in seen], ['auto'])

    def test_completing_the_script_announces_the_chain_start(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'project'
            writing = project / 'writing'
            writing.mkdir(parents=True)
            (writing / 'script_raw.md').write_text('# 自然剧本\n正文', encoding='utf-8')
            bus, orch = self.orchestrator_for('auto', stage='script')
            seen = []
            bus.subscribe('script.completed', seen.append)
            orch.execute('demo-skill', {'project': project, 'stage': 'script'})
            bus.pump()
            self.assertEqual([item['stage'] for item in seen], ['script'],
                             '剧本那一步做完就发 script.completed（自动推进的起点）')

    def test_script_cannot_complete_without_a_saved_natural_script(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'project'
            project.mkdir()
            bus, orch = self.orchestrator_for('auto', stage='script')
            completed, failed = [], []
            bus.subscribe('script.completed', completed.append)
            bus.subscribe('stage.failed', failed.append)
            result = orch.execute('demo-skill', {'project': project, 'stage': 'script'})
            bus.pump()
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(completed, '没有落盘原稿不得启动三虎自动链')
            self.assertIn('未保存可读取的自然剧本', failed[0]['error'])


class ArmFromTests(unittest.TestCase):
    """第 67 期任务 5：不必等 script.completed 那条事件，按项目现状直接武装。

    用户在一个早就做完剧本的项目里切到自动档时，那条事件永远不再来——不补这一下，
    自动档会一直什么都不开始。
    """

    def states(self, **done):
        table = {stage: 'pending' for stage in stage_flow.OWN_ORDER}
        table.update(done)
        return table

    def test_it_arms_and_skips_what_is_already_done(self):
        auto = stage_flow.Auto()
        self.assertTrue(auto.arm_from('auto', self.states(script='success', storyboard='skipped')))
        self.assertEqual(auto.pending()[0], 'script_structure', '收场的那几步跳过，从第一个没做完的接手')

    def test_a_failed_structure_stage_is_never_skipped_by_later_states(self):
        """损坏的旧状态即使误标了下游完成，也必须回到第一个失败阶段修复。"""
        auto = stage_flow.Auto()
        self.assertTrue(auto.arm_from('auto', self.states(
            script='success', script_structure='failed', storyboard='success')))
        self.assertEqual(auto.next_stage(), 'script_structure')

    def test_it_walks_from_the_start_when_nothing_is_done(self):
        auto = stage_flow.Auto()
        self.assertTrue(auto.arm_from('semi', self.states()))
        self.assertEqual(auto.pending()[0], 'script')

    def test_the_hint_level_never_arms(self):
        auto = stage_flow.Auto()
        self.assertFalse(auto.arm_from('hint', self.states(script='success')))
        self.assertEqual(auto.pending(), [])

    def test_without_states_it_falls_back_to_the_old_rule(self):
        auto = stage_flow.Auto()
        self.assertTrue(auto.arm_from('auto', None))
        self.assertEqual(auto.pending()[0], 'script', '状态给不出来就从头走')


if __name__ == '__main__':
    unittest.main(verbosity=2)
