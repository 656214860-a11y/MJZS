# -*- coding: utf-8 -*-
"""C 卡回归：L0 工具结果协议、L4 执行器适配与付费确认续跑幂等。"""
import tempfile
import unittest

import contract.service_contract as service_contract
import ui.skill_tools as skill_tools
from orchestrator import skill_orchestrator


class FakeSkill:
    def __init__(self, name='probe-skill', *, paid=False, tools=('probe.tool',)):
        self.name = name
        self.displayName = name
        self.description = ''
        self.stage = 'assets'
        self.capabilities = ()
        self.preferredModels = ()
        self.fallbackModels = ()
        self.tools = tuple(tools)
        self.dependsOn = ()
        self.conflictsWith = ()
        self.parallelizable = True
        self.paid = paid


class FakeRegistry:
    def __init__(self, *items):
        self.items = {item.name: item for item in items}

    def canonical_id(self, name):
        return str(name or '').strip()

    def getById(self, name):
        return self.items.get(name)

    def getAll(self):
        return list(self.items.values())

    def getByStage(self, stage):
        return [item for item in self.items.values() if item.stage == stage]


class ToolExecutionProtocolTests(unittest.TestCase):
    def orchestrator(self, item, executor, project):
        orch = skill_orchestrator.Orchestrator(registry=FakeRegistry(item), project=project)
        orch.tool_executor = executor
        return orch

    def test_l4_adapter_and_l3_orchestrator_share_the_same_done_result(self):
        item = FakeSkill()
        with tempfile.TemporaryDirectory() as project:
            context = {'project': project,
                       'tools': {'probe.tool': lambda ctx: {'ok': True, 'detail': '探针完成'}}}
            direct = skill_tools.execute_tool('probe.tool', context)
            row = self.orchestrator(item, skill_tools.execute_tool, project).execute(item.name, context)
        self.assertEqual(direct.status, service_contract.TOOL_DONE)
        self.assertEqual(direct.data['detail'], '探针完成')
        self.assertEqual(row['status'], skill_orchestrator.DONE)
        self.assertEqual(row['tools'][0]['status'], service_contract.TOOL_DONE)
        self.assertEqual(row['tools'][0]['detail'], direct.data['detail'])

    def test_page_and_input_are_protocol_results_not_ui_exceptions(self):
        page = skill_tools.execute_tool('firstframe.batchGenerate', {})
        self.assertEqual(page.status, service_contract.TOOL_PAGE)
        self.assertIsInstance(page.page, int)
        self.assertTrue(page.page_title)
        self.assertTrue(page.hint)

        missing_input = skill_tools.execute_tool('storyboard.validate', {})
        self.assertEqual(missing_input.status, service_contract.TOOL_INPUT)
        self.assertIn('需要', missing_input.detail)

    def test_orchestrator_consumes_page_result_without_importing_ui(self):
        item = FakeSkill(tools=('firstframe.batchGenerate',))
        with tempfile.TemporaryDirectory() as project:
            row = self.orchestrator(item, skill_tools.execute_tool, project).execute(
                item.name, {'project': project})
        self.assertEqual(row['status'], skill_orchestrator.PAGE)
        self.assertEqual(row['tools'][0]['status'], service_contract.TOOL_PAGE)
        self.assertEqual(row['tools'][0]['page'], skill_tools.STAGE_PAGE['keyframe'])
        self.assertIn('页面上按', row['detail'])

    def test_l4_page_adapter_opens_the_recorded_stage_page(self):
        shown = []

        class Desktop:
            def show(self, page):
                shown.append(page)

        result = skill_tools.execute_tool('firstframe.batchGenerate', {})
        self.assertTrue(skill_tools.open_page(Desktop(), result))
        self.assertEqual(shown, [skill_tools.STAGE_PAGE['keyframe']])
        self.assertFalse(skill_tools.open_page(Desktop(), {'status': service_contract.TOOL_DONE}))

    def test_repeated_confirmation_reuses_the_first_resume_and_never_calls_twice(self):
        item = FakeSkill(paid=True)
        calls = []

        def executor(tool, context):
            calls.append(tool)
            return service_contract.tool_done({'detail': '付费探针完成'}, tool=tool)

        with tempfile.TemporaryDirectory() as project:
            orch = self.orchestrator(item, executor, project)
            context = {'project': project}
            run = orch.run([item.name], context)
            self.assertEqual([row['skill'] for row in run['pending']], [item.name])
            self.assertEqual(calls, [])
            orch.confirm_all(True)
            first = orch.resume_confirmed(run, run['pending'], context)
            second = orch.resume_confirmed(run, run['pending'], context)
        self.assertIs(second, first)
        self.assertEqual(calls, ['probe.tool'])
        self.assertEqual(first['results'][0]['status'], skill_orchestrator.DONE)

    def test_unbound_executor_is_an_explicit_missing_result(self):
        item = FakeSkill()
        previous = skill_orchestrator.install_tool_executor(None)
        try:
            with tempfile.TemporaryDirectory() as project:
                row = self.orchestrator(item, None, project).execute(item.name, {'project': project})
        finally:
            skill_orchestrator.install_tool_executor(previous)
        self.assertEqual(row['status'], skill_orchestrator.MISSING)
        self.assertIn('未绑定工具执行器', row['detail'])


if __name__ == '__main__':
    unittest.main()
