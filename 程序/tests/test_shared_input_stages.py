"""R2898 轮 4：13 阶段共享输入框接入、发送分流与单一创意对话目录（契约变更测试）。"""
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import desktop_shared_send as shared_send
import desktop_shared_input as shared_input
import idea_chat
import orchestrator.stage_flow as stage_flow
from contract import pet_bus
from desktop_page_nav import PageNavMixin
from ui.desktop_pet_bridge import PetBridgeMixin
from stage_execution_service import idea_chat_gateway, project_context
from tests.ui_edges_support import make_minimal_project


class StageMappingTests(unittest.TestCase):
    def test_stage_for_index_covers_only_13_stage_pages(self):
        self.assertEqual(shared_send.stage_for_index(0), 'script')
        self.assertEqual(shared_send.stage_for_index(6), 'final')
        self.assertEqual(shared_send.stage_for_index(12), 'delivery')
        for index in (13, 14, -1, None, 'x'):
            self.assertEqual(shared_send.stage_for_index(index), '')

    def test_flow_map_is_subset_of_pet_stages(self):
        self.assertTrue(set(shared_send.FLOW_FOR_STAGE) <= set(pet_bus.STAGES))
        self.assertEqual(set(shared_send.FLOW_FOR_STAGE),
                         {'script', 'storyboard', 'assets', 'keyframe',
                          'previs', 'video', 'audio'})


class _Desktop:
    """最小桌面替身：只实现分流真正调用到的入口。"""

    def __init__(self, win, root, **kwargs):
        self.win = win
        self.root = root
        self.status = tk.StringVar(master=win, value='')
        self.page_index = 0
        self.projects = SimpleNamespace(info={'projects': []})
        self.opened = []
        self.open_flow_agent = lambda *args, **kw: self.opened.append(args)
        self.sync_stage_placeholder = lambda box, stage: shared_send.sync_stage_placeholder(box, stage)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def safe(self, fn):
        return fn()

    def show_stage(self, stage):
        self.navigated = getattr(self, 'navigated', []) + [stage]
        self.page_index = pet_bus.STAGES.index(stage)


class SendDispatchTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()

    def _desktop(self, **kwargs):
        return _Desktop(self.win, self.root, **kwargs)

    def test_script_free_text_goes_through_send_message(self):
        sent = Mock()
        desktop = self._desktop(send_message=sent, draft_text=lambda: '')
        self.assertTrue(shared_send.send(desktop, 'script', '我的新创意', None))
        sent.assert_called_once_with()

    def test_script_early_return_keeps_input(self):
        # 简报缺项等早退路径不清空草稿：send_message 没消费输入 → 受理返回 False。
        desktop = self._desktop(send_message=Mock(), draft_text=lambda: '未发送的字')
        self.assertFalse(shared_send.send(desktop, 'script', '我的新创意', None))

    def test_storyboard_free_text_goes_through_send_storyboard(self):
        """REQ-S03-54：初步分镜自由文本走 send_storyboard，不直接 _open_flow。"""
        calls = []
        desktop = self._desktop(page_index=2)
        with unittest.mock.patch.object(
                shared_send, 'send_storyboard',
                side_effect=lambda d, text='', **kw: calls.append((d, text, kw)) or True):
            self.assertTrue(shared_send.send(desktop, 'storyboard', '按这个节奏分镜', None))
        self.assertEqual(calls, [(desktop, '按这个节奏分镜', {})])
        self.assertEqual(desktop.opened, [])

    def test_non_flow_stage_gets_hint_not_chat(self):
        """非对话制作阶段走直连 API 文件输出；未配 API 模型时提示选模型，不再报「暂无对话入口」。"""
        desktop = self._desktop(page_index=pet_bus.STAGES.index('edit'))
        calls = []
        with unittest.mock.patch.object(
                shared_send, 'send_stage_file',
                side_effect=lambda d, stage, text='', **kw: calls.append((stage, text, kw)) or True):
            self.assertTrue(shared_send.send(desktop, 'edit', '压缩节奏', None))
        self.assertEqual(calls, [('edit', '压缩节奏', {})])
        self.assertEqual(desktop.opened, [])
        with unittest.mock.patch('infra.model_pool.pool', return_value={}):
            self.assertFalse(shared_send.send(desktop, 'edit', '随便聊聊', None))
        self.assertNotIn('暂无对话入口', desktop.status.get())
        self.assertIn('API 模型', desktop.status.get())
        self.assertEqual(desktop.opened, [])

    def test_stage_command_navigates_then_sends_rest(self):
        desktop = self._desktop(page_index=0)
        desktop.open_flow_agent = Mock(side_effect=lambda *a, **k: desktop.opened.append(a))
        parsed = {'kind': 'stage', 'name': 'storyboard', 'stage': 'storyboard', 'rest': '出分镜'}
        with unittest.mock.patch.object(
                shared_send, 'send_storyboard',
                side_effect=lambda d, text='', **kw: desktop.opened.append(
                    ('storyboard', '初步分镜', text)) or True):
            self.assertTrue(shared_send.send(desktop, 'script', '/分镜 出分镜', parsed))
        self.assertEqual(desktop.navigated, ['storyboard'])
        self.assertEqual(desktop.opened[0][0], 'storyboard')

    def test_skill_command_dispatches_with_skill_prompt(self):
        # DOC-D8-7（用户决定 2026-11-22）：技能属于别的阶段也不换页，交给当前页的入口执行。
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self._desktop(page_index=0,
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'skill', 'name': '分镜技法', 'stage': 'script', 'rest': '做三版'}
        self.assertTrue(shared_send.send(desktop, 'script', '/分镜技法 做三版', parsed))
        self.assertEqual(getattr(desktop, 'navigated', []), [])
        self.assertEqual(desktop.page_index, 0)
        self.assertEqual(desktop.opened[0][:2], ('writing', '剧本准备'))
        prompt = desktop.opened[0][2]
        self.assertIn('分镜技法', prompt)
        self.assertIn('做三版', prompt)

    def test_skill_command_on_script_prefers_in_app_skill_request(self):
        """REQ-S01-118：剧本页 /技能名 先交 send_skill_request 应用内请求；受理则不开 Agent 窗口。"""
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self._desktop(page_index=0,
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'skill', 'name': '分镜技法', 'stage': 'script', 'rest': '做三版'}
        with unittest.mock.patch.object(shared_send, 'send_skill_request', return_value=True) as accepted:
            self.assertTrue(shared_send.send(desktop, 'script', '/分镜技法 做三版', parsed))
        accepted.assert_called_once_with(desktop, '分镜技法', skill.path, '做三版')
        self.assertEqual(desktop.opened, [])

    def test_skill_command_on_script_falls_back_when_in_app_declines(self):
        """REQ-S01-118：send_skill_request 返回 False（非接口模型）时仍走 _open_flow。"""
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self._desktop(page_index=0,
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'skill', 'name': '分镜技法', 'stage': 'script', 'rest': '做三版'}
        with unittest.mock.patch.object(shared_send, 'send_skill_request', return_value=False):
            self.assertTrue(shared_send.send(desktop, 'script', '/分镜技法 做三版', parsed))
        self.assertEqual(desktop.opened[0][:2], ('writing', '剧本准备'))
        self.assertIn('请完整读取并严格遵循本地技能文件', desktop.opened[0][2])

    def test_cross_stage_skill_on_page_without_entry_stays_and_hints(self):
        """剧本结构页用任意技能发送均留在当前页直连 API 输出阶段文件；无可用 API 模型时给选模型提示。"""
        here = pet_bus.STAGES.index('script_structure')
        skill = SimpleNamespace(name='短剧总控', stage='script',
                                path=Path('skills') / 'x' / 'SKILL.md')
        desktop = self._desktop(page_index=here,
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'engine', 'name': '短剧总控', 'stage': 'script_structure',
                  'rest': '整理结构'}
        calls = []
        with unittest.mock.patch.object(
                shared_send, 'send_stage_file',
                side_effect=lambda d, stage, text='', **kw: calls.append((stage, text, kw.get('only'))) or True):
            self.assertTrue(shared_send.send(desktop, 'script_structure', '/短剧总控 整理结构', parsed))
        self.assertEqual(calls, [('script_structure', '整理结构', ['短剧总控'])])
        self.assertEqual(getattr(desktop, 'navigated', []), [])
        self.assertEqual(desktop.page_index, here)
        self.assertEqual(desktop.opened, [])
        with unittest.mock.patch('infra.model_pool.pool', return_value={}):
            self.assertFalse(shared_send.send(desktop, 'script_structure', '/短剧总控 整理结构', parsed))
        hint = desktop.status.get()
        self.assertNotIn('暂无对话入口', hint)
        self.assertIn('API 模型', hint)
        self.assertIn('/短剧总控', hint)

    def test_same_stage_skill_without_entry_keeps_page_hint(self):
        """剧本结构页本阶段技能：有 API 模型直连输出，无模型提示选模型，不换页、不开 Agent。"""
        here = pet_bus.STAGES.index('script_structure')
        skill = SimpleNamespace(name='结构整理', stage='script_structure',
                                path=Path('skills') / 'x' / '结构整理.skill.md')
        desktop = self._desktop(page_index=here,
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'skill', 'name': '结构整理', 'stage': 'script_structure', 'rest': ''}
        calls = []
        with unittest.mock.patch.object(
                shared_send, 'send_stage_file',
                side_effect=lambda d, stage, text='', **kw: calls.append((stage, kw.get('only'))) or True):
            self.assertTrue(shared_send.send(desktop, 'script_structure', '/结构整理', parsed))
        self.assertEqual(calls, [('script_structure', ['结构整理'])])
        with unittest.mock.patch('infra.model_pool.pool', return_value={}):
            self.assertFalse(shared_send.send(desktop, 'script_structure', '/结构整理', parsed))
        self.assertEqual(getattr(desktop, 'navigated', []), [])
        self.assertEqual(desktop.opened, [])
        self.assertNotIn('暂无 Agent 入口', desktop.status.get())
        self.assertIn('API 模型', desktop.status.get())

    def test_explicit_stage_command_still_navigates_before_skill(self):
        """只有用户明确写 /阶段名 才换页：换页后技能在那个阶段的入口里执行。"""
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self._desktop(page_index=0,
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'stage', 'name': 'storyboard', 'stage': 'storyboard',
                  'rest': '/分镜技法 做三版'}
        named = []
        with unittest.mock.patch.object(
                shared_send, 'send_storyboard',
                side_effect=lambda d, text='', **kw: named.append((text, kw.get('only'))) or True):
            self.assertTrue(shared_send.send(desktop, 'script', '/初步分镜 /分镜技法 做三版', parsed))
        self.assertEqual(desktop.navigated, ['storyboard'])
        self.assertEqual(named, [('做三版', ['分镜技法'])])

    def test_skill_command_outside_stage_pages_asks_for_a_stage(self):
        """不在制作阶段页面时不替用户挑阶段：提示先打开一个制作阶段页面。"""
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self._desktop(page_index=len(pet_bus.STAGES),
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'skill', 'name': '分镜技法', 'stage': '', 'rest': '做三版'}
        self.assertFalse(shared_send.send(desktop, '', '/分镜技法 做三版', parsed))
        self.assertEqual(getattr(desktop, 'navigated', []), [])
        self.assertEqual(desktop.opened, [])
        self.assertIn('请先打开一个制作阶段页面', desktop.status.get())

    def test_unknown_skill_is_rejected_with_hint(self):
        desktop = self._desktop(page_index=0,
                                shared_input=SimpleNamespace(skill_items=lambda: []))
        parsed = {'kind': 'skill', 'name': '不存在', 'stage': 'script', 'rest': ''}
        self.assertFalse(shared_send.send(desktop, 'script', '/不存在', parsed))
        self.assertIn('没有这个技能', desktop.status.get())

    def test_account_gate_blocks_paid_stage(self):
        desktop = self._desktop(page_index=2,
                                account=SimpleNamespace(stage_gate=lambda stage: '需要会员'))
        self.assertFalse(shared_send.send(desktop, 'storyboard', '文本', None))
        self.assertEqual(desktop.opened, [])
        self.assertIn('需要会员', desktop.status.get())

    def test_storyboard_send_failure_keeps_draft(self):
        """初步分镜发送被拒时返回 False，由宿主保留输入框原文。"""
        desktop = self._desktop(page_index=2)
        with unittest.mock.patch.object(shared_send, 'send_storyboard', return_value=False):
            self.assertFalse(shared_send.send(desktop, 'storyboard', '文本', None))
        self.assertEqual(desktop.opened, [])

    def test_storyboard_named_skill_ignores_checked_list(self):
        """补充：勾选 [A,B] 发 /C → 只启动 C；不改 stage_config。"""
        skill_c = SimpleNamespace(name='C', stage='storyboard',
                                  path=Path('skills') / 'C.skill.md')
        desktop = self._desktop(
            page_index=2,
            shared_input=SimpleNamespace(skill_items=lambda: [skill_c]))
        calls = []
        writes = []
        with unittest.mock.patch.object(
                shared_send, 'send_storyboard',
                side_effect=lambda d, text='', **kw: calls.append((text, kw.get('only'))) or True), \
             unittest.mock.patch('orchestrator.stage_config.save',
                                 side_effect=lambda *a, **k: writes.append(a)):
            parsed = {'kind': 'skill', 'name': 'C', 'stage': 'storyboard', 'rest': ''}
            self.assertTrue(shared_send.send(desktop, 'storyboard', '/C', parsed))
        self.assertEqual(calls, [('', ['C'])])
        self.assertEqual(writes, [])

    def test_storyboard_named_same_as_checked_still_only_once(self):
        """补充：勾选 [A] 发 /A → 只启动 A 一次。"""
        skill_a = SimpleNamespace(name='A', stage='storyboard',
                                  path=Path('skills') / 'A.skill.md')
        desktop = self._desktop(
            page_index=2,
            shared_input=SimpleNamespace(skill_items=lambda: [skill_a]))
        calls = []
        with unittest.mock.patch.object(
                shared_send, 'send_storyboard',
                side_effect=lambda d, text='', **kw: calls.append(kw.get('only')) or True):
            parsed = {'kind': 'skill', 'name': 'A', 'stage': 'storyboard', 'rest': ''}
            self.assertTrue(shared_send.send(desktop, 'storyboard', '/A', parsed))
        self.assertEqual(calls, [['A']])

    def test_storyboard_empty_send_uses_checked_not_named(self):
        """补充：空发送 only=None，由批量链按勾选顺序跑；不写 stage_config。"""
        desktop = self._desktop(page_index=2)
        seen = []
        writes = []
        with unittest.mock.patch.object(
                shared_send, '_start_storyboard_batch',
                side_effect=lambda d, project, text, named, snap: seen.append(named) or False), \
             unittest.mock.patch('orchestrator.stage_config.save',
                                 side_effect=lambda *a, **k: writes.append(a)):
            self.assertFalse(shared_send.send_storyboard(desktop, ''))
        self.assertEqual(seen, [None])
        self.assertEqual(writes, [])


class _Status:
    def __init__(self):
        self.text = ''

    def set(self, text):
        self.text = str(text)

    def get(self):
        return self.text


class _Tasks:
    def __init__(self):
        self.active = set()

    def accepts(self, ticket):
        return ticket in self.active

    def cancel(self, ticket):
        return self.active.discard(ticket) is None


class _SendDesktop(PetBridgeMixin):
    """真实发送链的最小宿主：保留 L4 适配器与异步准备生命周期。"""

    def __init__(self, root):
        self.root = root
        self.status = _Status()
        self.win = SimpleNamespace(winfo_exists=lambda: True)
        self.worker = False
        self.shutting_down = False
        self.account = None
        self.pet = SimpleNamespace(bus=SimpleNamespace(begin_run=lambda stage: None))
        self.background_tasks = _Tasks()
        self.jobs = []
        self.opened = []
        self.skills = []
        self.shared_input = SimpleNamespace(
            request_model=None, skill_items=lambda: list(self.skills))

    def safe(self, fn):
        return fn()

    def async_(self, work, finish):
        ticket = len(self.jobs) + 1
        self.jobs.append((work, finish))
        self.background_tasks.active.add(ticket)
        self.worker = True
        return ticket

    def open_storyboard_skill(self, key=None, **kwargs):
        return shared_send.open_storyboard_skill(self, key, **kwargs)

    def present_stage(self, presentation, text):
        import desktop
        return desktop._present_stage(self, presentation, text)

    def open_flow_agent(self, stage, label, prompt, followup=None, **kwargs):
        self.opened.append((stage, label, prompt, followup, kwargs))


class StoryboardSendChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project'
        self.project.mkdir()
        self.script = self.project / 'writing' / '第01集.md'
        self.plan = {'scripts': [self.script], 'todo': [self.script], 'revise': []}

    def desktop(self):
        return _SendDesktop(self.project)

    def finish(self, desktop, index=-1):
        ticket = index + 1 if index >= 0 else len(desktop.jobs)
        work, done = desktop.jobs[index]
        payload = work()
        done(payload)
        desktop.worker = False
        desktop.background_tasks.active.discard(ticket)
        return payload

    def registry_patches(self, plan=None):
        return (
            unittest.mock.patch('orchestrator.stage_handler_registry._workflow_lock_error',
                                return_value=''),
            unittest.mock.patch('orchestrator.stage_handler_registry.storyboard_work_plan',
                                return_value=self.plan if plan is None else plan),
        )

    def selection_patches(self):
        return (
            unittest.mock.patch('orchestrator.storyboard_selection.selected_many',
                                side_effect=lambda project, kind: [self.script] if kind == 'script' else []),
            unittest.mock.patch('stage_execution_service.storyboard_produced_scripts',
                                return_value=set()),
            unittest.mock.patch('orchestrator.workflow_tasks.storyboard_batch_prompt',
                                return_value=('原始规则', '后续规则')),
        )

    def test_named_unchecked_skill_runs_only_it_without_rewriting_config(self):
        desktop = self.desktop()
        skills = [SimpleNamespace(name=name, stage='storyboard', path=Path('skills') / (name + '.md'))
                  for name in ('A', 'B', 'C')]
        desktop.skills = skills
        registry = Mock()
        registry.getById.side_effect = lambda name: next(
            (item for item in skills if item.name == name), None)
        registry.getAll.return_value = skills
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        with lock, plan, selected, produced, prompt, \
                unittest.mock.patch('orchestrator.skill_registry.default_registry', return_value=registry), \
                unittest.mock.patch('orchestrator.workflow_settings.current',
                                    return_value={'skills': ['A', 'B'], 'stage_skills': ['a', 'b']}), \
                unittest.mock.patch('orchestrator.stage_config.save') as save:
            parsed = {'kind': 'skill', 'name': 'C', 'stage': 'storyboard', 'rest': ''}
            self.assertTrue(shared_send.send(desktop, 'storyboard', '/C', parsed))
            self.finish(desktop)
        self.assertEqual(len(desktop.opened), 1)
        config = desktop.opened[0][4]['_config']
        self.assertEqual(config['stage_skills'], [str(skills[2].path)])
        self.assertEqual(config['skills'], [])
        self.assertTrue(config['named_execution'])
        self.assertEqual(config['named_skills'], ['C'])
        self.assertIn('点名执行：C', desktop.status.get())
        save.assert_not_called()

    def test_named_checked_skill_runs_once_without_rewriting_config(self):
        desktop = self.desktop()
        skill = SimpleNamespace(name='A', stage='storyboard', path=Path('skills') / 'A.md')
        desktop.skills = [skill]
        registry = Mock()
        registry.getById.return_value = skill
        registry.getAll.return_value = [skill]
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        with lock, plan, selected, produced, prompt, \
                unittest.mock.patch('orchestrator.skill_registry.default_registry', return_value=registry), \
                unittest.mock.patch('orchestrator.workflow_settings.current',
                                    return_value={'skills': ['A'], 'stage_skills': ['a']}), \
                unittest.mock.patch('orchestrator.stage_config.save') as save:
            parsed = {'kind': 'skill', 'name': 'A', 'stage': 'storyboard', 'rest': ''}
            self.assertTrue(shared_send.send(desktop, 'storyboard', '/A', parsed))
            self.finish(desktop)
        self.assertEqual(len(desktop.opened), 1)
        self.assertEqual(desktop.opened[0][4]['_config']['named_skills'], ['A'])
        save.assert_not_called()

    def test_named_skill_keeps_model_snapshot_without_rewriting_config(self):
        desktop = self.desktop()
        skill = SimpleNamespace(name='A', stage='storyboard', path=Path('skills') / 'A.md')
        desktop.skills = [skill]
        snapshot = ('snapshot', {'context_length': 8192})
        desktop.shared_input.request_model = snapshot
        registry = Mock()
        registry.getById.return_value = skill
        registry.getAll.return_value = [skill]
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        with lock, plan, selected, produced, prompt, \
                unittest.mock.patch('orchestrator.skill_registry.default_registry', return_value=registry), \
                unittest.mock.patch('orchestrator.workflow_settings.current',
                                    return_value={'model': 'snapshot', 'skills': ['A'],
                                                  'stage_skills': ['a']}) as current, \
                unittest.mock.patch('orchestrator.stage_config.save') as save:
            parsed = {'kind': 'skill', 'name': 'A', 'stage': 'storyboard', 'rest': ''}
            self.assertTrue(shared_send.send(desktop, 'storyboard', '/A', parsed))
            self.finish(desktop)
        current.assert_called_once_with(self.project, 'storyboard', model_snapshot=snapshot)
        config = desktop.opened[0][4]['_config']
        self.assertEqual(config['model'], 'snapshot')
        self.assertEqual(config['stage_skills'], [str(skill.path)])
        self.assertEqual(config['named_skills'], ['A'])
        save.assert_not_called()

    def test_empty_send_preserves_checked_order_and_config(self):
        import orchestrator.skill_registry as skill_registry
        name = skill_registry.default_registry(project=self.project).getByStage('storyboard')[0].name
        config_path = self.project / 'skill_config.json'
        config_path.write_text(
            json.dumps({'storyboard': {'skills': [name]}}, ensure_ascii=False), encoding='utf-8')
        before = config_path.read_bytes()
        desktop = self.desktop()
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        with lock, plan, selected, produced, prompt, \
                unittest.mock.patch('orchestrator.stage_config.save') as save:
            self.assertTrue(shared_send.send_storyboard(desktop, ''))
            self.finish(desktop)
        self.assertEqual(len(desktop.opened), 1)
        self.assertNotIn('_config', desktop.opened[0][4], '空发送不覆盖勾选配置')
        self.assertNotIn('点名执行', desktop.opened[0][2])
        self.assertEqual(stage_flow.selected_skills(self.project, 'storyboard'), [name])
        self.assertEqual(config_path.read_bytes(), before, '空发送不改写勾选配置')
        save.assert_not_called()

    def test_send_snapshots_selected_files_model_and_supplement(self):
        desktop = self.desktop()
        selected = unittest.mock.patch(
            'orchestrator.storyboard_selection.selected_many',
            side_effect=lambda project, kind: [self.script] if kind == 'script' else [])
        produced = unittest.mock.patch(
            'stage_execution_service.storyboard_produced_scripts', return_value=set())
        prompt = unittest.mock.patch(
            'orchestrator.workflow_tasks.storyboard_batch_prompt',
            return_value=('原始规则', '后续规则'))
        current = unittest.mock.patch(
            'orchestrator.workflow_settings.current', return_value={'model': 'snapshot'})
        with selected as selected_many, produced, prompt as batch_prompt, current:
            ticket = shared_send.open_storyboard_skill(
                desktop, request_text='补充要求', model_snapshot='snapshot')
            self.assertEqual(ticket, 1)
            self.finish(desktop)
        self.assertEqual(selected_many.call_args_list, [
            unittest.mock.call(self.project, 'script'),
            unittest.mock.call(self.project, 'storyboard')])
        batch_prompt.assert_called_once_with(self.project, [self.script], [])
        self.assertEqual(desktop.opened[0][2], '原始规则\n补充要求：补充要求')
        self.assertEqual(desktop.opened[0][3], '后续规则\n补充要求：补充要求')
        self.assertEqual(desktop.opened[0][4]['_config'], {'model': 'snapshot'})

    def test_preparation_rejects_duplicate_and_allows_next_after_finish(self):
        desktop = self.desktop()
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        with lock, plan, selected, produced, prompt:
            self.assertTrue(shared_send.send_storyboard(desktop, '第一次'))
            self.assertFalse(shared_send.send_storyboard(desktop, '第二次'))
            self.assertEqual(len(desktop.jobs), 1)
            self.finish(desktop)
            self.assertTrue(shared_send.send_storyboard(desktop, '第三次'))
        self.assertEqual(len(desktop.jobs), 2)
        self.assertEqual(len(desktop.opened), 1)

    def test_preparation_failure_releases_and_can_retry(self):
        desktop = self.desktop()
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        with lock, plan, selected, produced, \
                unittest.mock.patch('orchestrator.workflow_tasks.storyboard_batch_prompt',
                                    side_effect=[ValueError('准备失败'), ('prompt', 'followup')]):
            self.assertTrue(shared_send.send_storyboard(desktop, '第一次'))
            self.assertEqual(self.finish(desktop), ('err', '准备失败'))
            self.assertEqual(desktop.opened, [])
            self.assertFalse(getattr(desktop, '_storyboard_send_prep', False))
            self.assertTrue(shared_send.send_storyboard(desktop, '重试'))
        self.assertEqual(len(desktop.jobs), 2)

    def test_switch_project_or_destroyed_window_drops_late_result(self):
        for mode in ('switch', 'destroy'):
            with self.subTest(mode=mode):
                desktop = self.desktop()
                selected, produced, prompt = self.selection_patches()
                with selected, produced, prompt:
                    shared_send.open_storyboard_skill(desktop)
                    if mode == 'switch':
                        desktop.root = Path(self.tmp.name) / 'other'
                    else:
                        desktop.win.winfo_exists = lambda: False
                    self.finish(desktop)
                self.assertEqual(desktop.opened, [])
                self.assertFalse(getattr(desktop, '_storyboard_send_prep', False))

    def test_cancelled_ticket_does_not_block_or_clear_new_preparation(self):
        desktop = self.desktop()
        selected, produced, prompt = self.selection_patches()
        with selected, produced, prompt:
            shared_send.open_storyboard_skill(desktop, request_text='旧')
            self.assertTrue(desktop.background_tasks.cancel(1))
            desktop.worker = False
            shared_send.open_storyboard_skill(desktop, request_text='新')
            self.assertEqual(len(desktop.jobs), 2)
            old_work, old_done = desktop.jobs[0]
            old_done(old_work())
            self.assertEqual(desktop.opened, [])
            self.assertTrue(getattr(desktop, '_storyboard_send_prep', False))
            self.finish(desktop, 1)
        self.assertEqual(len(desktop.opened), 1)
        self.assertIn('补充要求：新', desktop.opened[0][2])

    def test_no_project_unselected_all_done_cancel_and_configure_do_not_start(self):
        desktop = self.desktop()
        desktop.root = None
        self.assertFalse(shared_send.send_storyboard(desktop, '草稿'))
        self.assertEqual(desktop.jobs, [])
        desktop.root = self.project
        for plan in ({'scripts': [], 'todo': [], 'revise': []},
                     {'scripts': [self.script], 'todo': [], 'revise': []}):
            lock, plan_patch = self.registry_patches(plan)
            with self.subTest(plan=plan), lock, plan_patch:
                self.assertFalse(shared_send.send_storyboard(desktop, '草稿'))
        self.assertEqual(desktop.jobs, [])
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        with lock, plan, selected, produced, prompt, \
                unittest.mock.patch('orchestrator.stage_models.plan') as modal_plan, \
                unittest.mock.patch('orchestrator.stage_models.before_manual') as modal_ask:
            self.assertTrue(shared_send.send_storyboard(desktop, '草稿'))
            modal_plan.assert_not_called()
            modal_ask.assert_not_called()

    def test_finish_reports_open_flow_agent_error_instead_of_raising(self):
        """open_storyboard_skill 的 finish() 遇到 open_flow_agent 抛错时不冒出，经 notifier 或状态栏提示。"""
        for with_notifier in (True, False):
            with self.subTest(with_notifier=with_notifier):
                desktop = self.desktop()
                errors = []
                if with_notifier:
                    desktop.notifier = SimpleNamespace(error=errors.append)
                desktop.open_flow_agent = Mock(side_effect=ValueError('未配置分镜模型，请先设置'))
                selected, produced, prompt = self.selection_patches()
                with selected, produced, prompt:
                    shared_send.open_storyboard_skill(desktop, request_text='补充')
                    self.finish(desktop)
                if with_notifier:
                    self.assertEqual(len(errors), 1)
                    self.assertIn('未配置分镜模型', errors[0])
                else:
                    self.assertIn('未配置分镜模型', desktop.status.get())
                self.assertFalse(getattr(desktop, '_storyboard_send_prep', False))

    def test_finish_preserves_status_written_by_open_flow_agent(self):
        """open_flow_agent 已写直连 API 状态后，finish() 不得用默认提示将其覆盖。"""
        desktop = self.desktop()
        direct_msg = '正在直连 API 制作初步分镜（后台进行，可点「强制停止制作」中断）…'

        def fake_open(stage, label, prompt, followup=None, **kwargs):
            desktop.opened.append((stage, label, prompt, followup, kwargs))
            desktop.status.set(direct_msg)

        desktop.open_flow_agent = fake_open
        selected, produced, prompt = self.selection_patches()
        with selected, produced, prompt:
            shared_send.open_storyboard_skill(desktop)
            self.finish(desktop)
        self.assertEqual(len(desktop.opened), 1)
        self.assertEqual(desktop.status.get(), direct_msg)

    def test_named_skill_ignores_writing_dict_request_model_snapshot(self):
        """shared_input.request_model 为 writing_api.capture_request 风格的 dict 时，/技能发送不因解包崩溃。"""
        desktop = self.desktop()
        skill = SimpleNamespace(name='C', stage='storyboard', path=Path('skills') / 'C.md')
        desktop.skills = [skill]
        desktop.shared_input.request_model = {
            'id': 'gpt-4o', 'record': {'context_length': 8192},
            'label': 'GPT-4o', 'provider': 'openai', 'settings': {'engine': 'qwen'},
        }
        registry = Mock()
        registry.getById.return_value = skill
        registry.getAll.return_value = [skill]
        lock, plan = self.registry_patches()
        selected, produced, prompt = self.selection_patches()
        seen_snapshots = []

        def strict_current(project, stage='previs', *, direct_api=False, model_snapshot=None):
            seen_snapshots.append(model_snapshot)
            if model_snapshot is not None:
                _selected, _item = model_snapshot
            return {'model': 'storyboard-model', 'skills': ['A'], 'stage_skills': ['a']}

        with lock, plan, selected, produced, prompt, \
                unittest.mock.patch('orchestrator.skill_registry.default_registry', return_value=registry), \
                unittest.mock.patch('orchestrator.workflow_settings.current', side_effect=strict_current), \
                unittest.mock.patch('orchestrator.stage_config.save') as save:
            parsed = {'kind': 'skill', 'name': 'C', 'stage': 'storyboard', 'rest': ''}
            self.assertTrue(shared_send.send(desktop, 'storyboard', '/C', parsed))
            self.finish(desktop)
        self.assertEqual(seen_snapshots, [None])
        self.assertEqual(len(desktop.opened), 1)
        self.assertEqual(desktop.opened[0][4]['_config']['named_skills'], ['C'])
        self.assertNotIn('too many values to unpack', desktop.status.get())
        save.assert_not_called()

    def test_start_storyboard_batch_reports_work_plan_error_to_status(self):
        """storyboard_work_plan 读取失败时，_start_storyboard_batch 须把原因写入状态栏而非静默。"""
        desktop = self.desktop()
        desktop.start_storyboard_send = Mock(return_value=False)
        with unittest.mock.patch.object(shared_send, 'selected_many', return_value=[self.script]), \
                unittest.mock.patch.object(shared_send, 'storyboard_work_plan',
                                           side_effect=ValueError('结构剧本目录损坏')):
            started = shared_send._start_storyboard_batch(desktop, self.project, '', None, None)
        self.assertFalse(started)
        self.assertIn('读取结构剧本输入失败', desktop.status.get())
        self.assertIn('结构剧本目录损坏', desktop.status.get())

    def test_launch_storyboard_flow_expands_reply_area_on_dispatch_and_error(self):
        """launch_storyboard_flow 在启动派发与异常报错时同步展开 storyboard 回话区，兼容 3 参桩。"""
        expanded = []
        notes = []
        desktop = self.desktop()
        desktop.page_index = pet_bus.STAGES.index('storyboard')
        desktop.reply_area = SimpleNamespace(
            stage='storyboard', set_expanded=lambda flag: expanded.append(bool(flag)))
        desktop.reply_note = lambda kind, stage, text: notes.append((kind, stage, text))
        selected, produced, prompt = self.selection_patches()
        with selected, produced, prompt:
            shared_send.open_storyboard_skill(desktop, request_text='补充')
            self.finish(desktop)
        self.assertEqual(expanded, [True])
        self.assertTrue(any(k == 'progress' and s == 'storyboard' for k, s, _t in notes))

        expanded.clear()
        notes.clear()
        desktop_err = self.desktop()
        desktop_err.page_index = pet_bus.STAGES.index('storyboard')
        desktop_err.reply_area = SimpleNamespace(
            stage='storyboard', set_expanded=lambda flag: expanded.append(bool(flag)))
        desktop_err.reply_note = lambda kind, stage, text: notes.append((kind, stage, text))
        desktop_err.open_flow_agent = Mock(side_effect=ValueError('未配置分镜模型'))
        with selected, produced, prompt:
            shared_send.open_storyboard_skill(desktop_err, request_text='补充')
            self.finish(desktop_err)
        self.assertEqual(expanded, [True])
        self.assertTrue(any(k == 'error' and '未配置分镜模型' in t for k, _s, t in notes))

        expanded.clear()
        desktop_other = self.desktop()
        desktop_other.reply_area = SimpleNamespace(
            stage='assets', set_expanded=lambda flag: expanded.append(bool(flag)))
        with selected, produced, prompt:
            shared_send.open_storyboard_skill(desktop_other, request_text='补充')
            self.finish(desktop_other)
        self.assertEqual(expanded, [], '非 storyboard 阶段回话区不得误展开')


class SharedInputHostTests(unittest.TestCase):
    """宿主接线：同一实例跨页 set_stage；非阶段页隐藏；/命令落到分流。"""

    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.status_label = tk.Label(self.win)
        self.status_label.pack()
        self.sent = []
        desktop = _Desktop(self.win, self.root,
                           shared_input=None)
        options = shared_send.host_options(desktop)
        self.box = shared_input.SharedStageInput(
            self.win, desktop=desktop, options=dict(options, on_send=None))
        # host_options 的 on_send 已含分流；直接用它验证端到端。
        self.box.on_send = options['on_send']
        desktop.shared_input = self.box
        self.desktop = desktop
        self.addCleanup(self.box.destroy)

    def test_set_stage_switches_context_without_rebuild(self):
        self.box.set_stage('storyboard')
        self.assertEqual(self.box.stage, 'storyboard')
        self.assertEqual(self.box.input.winfo_class(), 'Text')

    def test_sync_shared_input_maps_page_index(self):
        stub = SimpleNamespace(shared_input=self.box, page_index=0,
                               status_label=self.status_label)
        PageNavMixin._sync_shared_input(stub)
        self.assertEqual(self.box.stage, 'script')
        self.assertEqual(self.box.winfo_manager(), 'pack')
        stub.page_index = pet_bus.STAGES.index('video')
        PageNavMixin._sync_shared_input(stub)
        self.assertEqual(self.box.stage, 'video')
        stub.page_index = 13  # 参考网站
        PageNavMixin._sync_shared_input(stub)
        self.assertEqual(self.box.winfo_manager(), '')

    def test_enter_send_routes_through_dispatch(self):
        self.desktop.send_message = Mock()
        self.box.set_text('你好')
        self.assertTrue(self.box.send())
        self.desktop.send_message.assert_called_once_with()
        class _Event:
            state = 0
        self.box.set_text('再发一次')
        self.assertEqual(self.box._on_return(_Event()), 'break')
        self.assertEqual(self.desktop.send_message.call_count, 2)

    # ── R2980／REQ-S01-92：/ 与 @ 光标级候选浮层（自绘行＋光标锚定翻转） ──

    def _caret_end(self):
        self.box.input.mark_set('insert', 'end-1c')

    def _open_completion(self):
        self.box.set_text('/')
        self._caret_end()
        self.box._refresh_candidates()
        self.win.update_idletasks()
        self.win.update()

    def _show_window(self):
        self.win.geometry('1000x700+40+40')
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.update()

    def test_completion_anchors_to_cursor_and_flips_above(self):
        """候选卡锚在文本光标：输入框贴窗口底部时下方空间不足，翻到光标上方。"""
        self.box.pack(side='bottom', fill='x')
        self._show_window()
        self._open_completion()
        popup = self.box.candidates
        self.assertTrue(popup.open)
        panel = popup.frame
        self.assertEqual(panel.winfo_manager(), 'place', '候选层用 place 浮层')
        self.assertIs(panel.master, self.win, '浮层挂顶层窗：光标上方空间也画得出')
        cursor_x, cursor_top, cursor_bottom = popup._cursor_anchor()
        panel_bottom = panel.winfo_rooty() + panel.winfo_height()
        panel_right = panel.winfo_rootx() + panel.winfo_width()
        # 输入框在窗口底部：光标下方放不下 → 浮层整体翻到光标上方。
        self.assertLessEqual(panel_bottom, cursor_top + 1,
                             '底部空间不足时候选卡翻到光标上方')
        # 横向锚在光标附近且不出可视区。
        self.assertGreaterEqual(panel.winfo_rootx(), 0)
        self.assertLessEqual(panel_right, self.win.winfo_screenwidth())
        self.assertEqual(popup.index, 0, '默认高亮第一项')
        self.assertEqual(self.box.input.get('1.0', 'end-1c'), '/', '高亮不得误采纳候选')

    def test_completion_up_down_tab_and_enter_accept(self):
        self.box.pack(side='bottom', fill='x')
        self._show_window()
        self._open_completion()
        popup = self.box.candidates
        self.assertGreaterEqual(len(popup.entries), 2)

        class _Event:
            keysym = 'Down'
        self.assertEqual(popup.key(_Event()), 'break')
        self.assertEqual(popup.index, 1, 'Down 移到第二项')
        _Event.keysym = 'Up'
        popup.key(_Event())
        self.assertEqual(popup.index, 0, 'Up 移回第一项')
        # Enter 走宿主 _on_return：候选开着时采纳当前项而不是发送。
        class _Return:
            state = 0
        self.assertEqual(self.box._on_return(_Return()), 'break')
        self.assertFalse(popup.open, 'Enter 采纳后收掉浮层')
        value = self.box.input.get('1.0', 'end-1c')
        self.assertTrue(value.startswith('/'), '采纳把候选写回输入框')
        self.assertTrue(value.endswith(' '), '采纳结果带尾空格')
        self.assertEqual(getattr(self.desktop, 'navigated', []), [],
                         '行首 /name 之外 Enter 不得触发发送分流')

    def test_completion_hover_highlights_but_click_applies(self):
        self.box.pack(side='bottom', fill='x')
        self._show_window()
        self._open_completion()
        popup = self.box.candidates
        self.assertGreaterEqual(len(popup.entries), 2)
        row = popup._rows[1]
        label = next(w for w in row['widgets']
                     if w.winfo_class() == 'Label' and str(w.cget('text') or ''))
        label.event_generate('<Enter>')
        self.win.update()
        self.assertEqual(popup.index, 1, '悬停跟随高亮')
        self.assertEqual(self.box.input.get('1.0', 'end-1c'), '/', '悬停不自动采纳')
        self.assertTrue(popup.open)
        label.event_generate('<Button-1>', x=2, y=2)
        self.win.update()
        self.assertFalse(popup.open, '点击采纳后收掉')
        self.assertTrue(self.box.input.get('1.0', 'end-1c').startswith('/'))

    def test_completion_closes_when_focus_leaves_input(self):
        self.box.pack(side='bottom', fill='x')
        other = tk.Label(self.win, text='别处')
        other.pack()
        self.win.update()
        self._open_completion()
        popup = self.box.candidates
        self.assertTrue(popup.open)
        original = self.win.focus_get
        try:
            self.win.focus_get = lambda: other
            popup.close_if_focus_away()
            self.assertFalse(popup.open, '焦点移走即收掉候选层')
            self._open_completion()
            self.win.focus_get = lambda: self.box.input
            popup.close_if_focus_away()
            self.assertTrue(popup.open, '焦点还在输入框就不收')
        finally:
            self.win.focus_get = original

    def test_input_icons_carry_hover_tooltips(self):
        from unittest.mock import patch
        captured = []
        def fake_tooltip(widget, text, **kwargs):
            captured.append((widget, text))
            return widget
        with patch('desktop_shared_input.Tooltip', side_effect=fake_tooltip):
            box = shared_input.SharedStageInput(self.win, desktop=self.desktop,
                                                options={'on_send': None})
            self.addCleanup(box.destroy)
        by_widget = {str(widget): text for widget, text in captured}
        for widget, head in ((box.skill_button, '技能'), (box.attachment_button, '添加'),
                             (box.voice_button, '语音输入'), (box.send_button, '发送'),
                             (box.model_picker, '选择模型')):
            with self.subTest(widget=widget):
                self.assertTrue(by_widget[str(widget)].startswith(head),
                                '图标必须挂悬停提示卡（Tooltip）')

    def test_skill_and_engine_lists_are_cached_until_stage_or_import(self):
        first = self.box.skill_items()
        self.assertIs(self.box.skill_items(), first, '技能清单按实例缓存，不每次按键重读')
        engines = self.box.engine_names()
        self.assertIs(self.box.engine_names(), engines, '子引擎名单同样缓存')
        self.box.set_stage('storyboard')
        self.assertIsNone(self.box._skills_cache, '切阶段后技能缓存失效')
        self.assertIsNot(self.box.skill_items(), first, '切阶段后重新取技能清单')


class SingleThreadTranscriptTests(unittest.TestCase):
    """任务书轮 4 契约：模型会话目录 → 单一创意对话目录，旧目录首次读取迁移。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = make_minimal_project(self.tmp.name)
        self.ctx = project_context(self.proj)

    def _gw(self):
        return idea_chat_gateway()

    def test_model_history_path_is_one_file_for_all_models(self):
        first = idea_chat.model_history_path(self.ctx, '模型甲')
        second = idea_chat.model_history_path(self.ctx, '模型乙')
        self.assertEqual(first, second)
        self.assertEqual(first, idea_chat.history_path(self.ctx))
        self.assertTrue(first.name == '对话.json' and first.parent.name == '创意对话')

    def test_appends_from_two_models_share_one_file(self):
        idea_chat.append(self.ctx, 'user', '甲的创意', model='模型甲', gateway=self._gw())
        idea_chat.append(self.ctx, 'user', '乙的创意', model='模型乙', gateway=self._gw())
        unified = idea_chat.load(self.ctx, model='', gateway=self._gw())
        self.assertEqual([row['text'] for row in unified], ['甲的创意', '乙的创意'])
        self.assertEqual(idea_chat.load(self.ctx, model='模型甲', gateway=self._gw())[-1]['text'], '甲的创意')

    def test_legacy_model_dirs_merge_once_and_keep_files(self):
        from contract.project_stages import writing
        legacy = (writing(self.proj) / '模型会话' / 'm1--deadbeef' / '创意对话' / '对话.json')
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({'messages': [
            {'role': 'user', 'text': '旧模型甲的创意', 'model': '模型甲', 'at': '20200101_000000_000000'},
            {'role': 'assistant', 'text': '旧模型乙的回复', 'model': '模型乙', 'at': '20200101_000001_000000'},
        ]}, ensure_ascii=False), encoding='utf-8')
        idea_chat.append(self.ctx, 'user', '新的创意', model='模型丙', gateway=self._gw())
        rows = idea_chat.load(self.ctx, model='', gateway=self._gw())
        self.assertEqual([row['text'] for row in rows],
                         ['旧模型甲的创意', '旧模型乙的回复', '新的创意'])
        # 只迁移不删：旧目录文件原样保留。
        self.assertTrue(legacy.is_file())
        self.assertEqual(len(json.loads(legacy.read_text(encoding='utf-8'))['messages']), 2)
        # 第二次读取不再重复合并。
        again = idea_chat.load(self.ctx, model='', gateway=self._gw())
        self.assertEqual(len(again), 3)


if __name__ == '__main__':
    unittest.main()
