# -*- coding: utf-8 -*-
"""F 卡回归：L0 ToolResult 协议的独立接口验收。"""
import tempfile
import unittest

import contract.service_contract as service_contract


class ToolResultContractTests(unittest.TestCase):
    def test_status_constants_are_a_closed_enum(self):
        self.assertEqual(service_contract.TOOL_STATUSES,
                         (service_contract.TOOL_DONE, service_contract.TOOL_PAGE,
                          service_contract.TOOL_INPUT, service_contract.TOOL_FAILED,
                          service_contract.TOOL_MISSING))
        self.assertEqual(service_contract.TOOL_STATUSES,
                         ('done', 'page', 'input', 'failed', 'missing'))
        self.assertEqual(len(set(service_contract.TOOL_STATUSES)), 5)

    def test_service_result_failure_split_keeps_cancelled_out_of_failures(self):
        self.assertFalse(service_contract.is_failure(service_contract.success({'ok': True})))
        self.assertTrue(service_contract.is_failure(service_contract.UserError('请补输入')))
        self.assertTrue(service_contract.is_failure(service_contract.SystemError('环境异常')))
        self.assertFalse(service_contract.is_failure(service_contract.Cancelled()))

    def test_tool_result_accepts_each_status_and_rejects_unknown_status(self):
        for status in service_contract.TOOL_STATUSES:
            with self.subTest(status=status):
                self.assertEqual(service_contract.ToolResult(status).status, status)
        for status in ('', 'DONE', 'success', 'retry'):
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, '未知工具执行状态'):
                    service_contract.ToolResult(status)

    def test_factories_build_the_five_protocol_results(self):
        done = service_contract.tool_done({'count': 1}, detail='完成', tool='probe.tool')
        self.assertEqual((done.status, done.detail, done.data, done.tool),
                         (service_contract.TOOL_DONE, '完成', {'count': 1}, 'probe.tool'))

        page = service_contract.tool_needs_page('2', title='03 资产', hint='点生成',
                                                detail='回页面执行', tool='probe.tool')
        self.assertEqual((page.status, page.page, page.page_title, page.hint, page.detail),
                         (service_contract.TOOL_PAGE, 2, '03 资产', '点生成', '回页面执行'))

        need = service_contract.tool_needs_input('缺少分镜', tool='probe.tool')
        self.assertEqual((need.status, need.detail, need.tool),
                         (service_contract.TOOL_INPUT, '缺少分镜', 'probe.tool'))

        failed = service_contract.tool_failed('执行失败', tool='probe.tool', data={'partial': True})
        self.assertEqual((failed.status, failed.detail, failed.data),
                         (service_contract.TOOL_FAILED, '执行失败', {'partial': True}))

        missing = service_contract.tool_missing('工具未登记', tool='probe.tool')
        self.assertEqual((missing.status, missing.detail),
                         (service_contract.TOOL_MISSING, '工具未登记'))

    def test_page_factory_accepts_integer_forms_without_truncating(self):
        for raw, expected in ((0, 0), (2, 2), ('2', 2), (' 02 ', 2), (2.0, 2)):
            with self.subTest(raw=raw):
                self.assertEqual(service_contract.tool_needs_page(raw).page, expected)

    def test_page_factory_rejects_illegal_pages(self):
        for raw in (None, '', 'x', '-1', -1, 1.5, True, object()):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, '非法工具页面序号'):
                    service_contract.tool_needs_page(raw)

    def test_coerce_returns_an_existing_tool_result_by_identity(self):
        original = service_contract.tool_missing('原样返回', tool='probe.tool')
        self.assertIs(service_contract.coerce_tool_result(original, tool='other.tool'), original)

    def test_coerce_preserves_each_protocol_status_from_a_history_dict(self):
        for status in service_contract.TOOL_STATUSES:
            with self.subTest(status=status):
                result = service_contract.coerce_tool_result({'status': status})
                self.assertEqual(result.status, status)

    def test_coerce_reads_historical_protocol_dict_and_camel_case_title(self):
        payload = {'status': 'page', 'detail': '回页面', 'data': {'draft': 1},
                   'page': '3', 'pageTitle': '04 分镜', 'hint': '按生成',
                   'tool': 'legacy.tool'}
        result = service_contract.coerce_tool_result(payload, tool='fallback.tool')
        self.assertEqual((result.status, result.detail, result.page, result.page_title,
                          result.hint, result.tool),
                         (service_contract.TOOL_PAGE, '回页面', 3, '04 分镜',
                          '按生成', 'legacy.tool'))
        self.assertIs(result.data, payload['data'])

    def test_coerce_reads_snake_case_title_and_fallback_tool(self):
        payload = {'status': 'page', 'detail': '回页面', 'page': 1,
                   'page_title': '02 剧本结构', 'tool': ''}
        result = service_contract.coerce_tool_result(payload, tool='fallback.tool')
        self.assertEqual((result.status, result.page, result.page_title, result.tool),
                         (service_contract.TOOL_PAGE, 1, '02 剧本结构', 'fallback.tool'))

    def test_coerce_tolerates_missing_and_illegal_historical_pages(self):
        for raw in (None, '', 'x', '-1', -1, 1.5, True, object()):
            with self.subTest(raw=raw):
                result = service_contract.coerce_tool_result({'status': 'page', 'page': raw})
                self.assertEqual(result.status, service_contract.TOOL_PAGE)
                self.assertIsNone(result.page)

    def test_coerce_reads_valid_historical_page_numbers(self):
        for raw, expected in ((0, 0), (2, 2), ('2', 2), (' 02 ', 2), (2.0, 2)):
            with self.subTest(raw=raw):
                result = service_contract.coerce_tool_result({'status': 'page', 'page': raw})
                self.assertEqual(result.page, expected)

    def test_coerce_treats_dict_without_a_protocol_status_as_business_data(self):
        for payload in ({'ok': True, 'detail': '历史业务结果'},
                        {'status': 'success', 'detail': '未知状态只是业务字段'}):
            with self.subTest(payload=payload):
                result = service_contract.coerce_tool_result(payload, tool='probe.tool')
                self.assertEqual(result.status, service_contract.TOOL_DONE)
                self.assertIs(result.data, payload)
                self.assertEqual(result.tool, 'probe.tool')

    def test_coerce_wraps_plain_values_as_done_payloads(self):
        for value in (None, 0, '文本', ['镜头'], ('键', '值')):
            with self.subTest(value=value):
                result = service_contract.coerce_tool_result(value, tool='probe.tool')
                self.assertEqual(result.status, service_contract.TOOL_DONE)
                self.assertEqual(result.data, {'value': value})
                self.assertEqual(result.tool, 'probe.tool')


class ToolResultExceptionBoundaryTests(unittest.TestCase):
    def test_l4_adapter_turns_tool_exception_into_failed_after_one_call(self):
        import ui.skill_tools as skill_tools

        calls = []

        def broken(_context):
            calls.append('probe.tool')
            raise RuntimeError('工具内部异常')

        result = skill_tools.execute_tool('probe.tool', {'tools': {'probe.tool': broken}})
        self.assertEqual(result.status, service_contract.TOOL_FAILED)
        self.assertIn('工具内部异常', result.detail)
        self.assertEqual(calls, ['probe.tool'])

    def test_l3_execution_turns_executor_exception_into_failed_after_one_call(self):
        from orchestrator import skill_orchestrator

        class Skill:
            name = 'probe-skill'
            displayName = '探测技能'
            stage = 'assets'
            tools = ('probe.tool',)
            paid = False
            parallelizable = True

        item = Skill()

        class Registry:
            def canonical_id(self, name):
                return str(name or '').strip()

            def getById(self, name):
                return item if name == item.name else None

            def getAll(self):
                return [item]

            def getByStage(self, stage):
                return [item] if stage == item.stage else []

        calls = []

        def executor(tool, _context):
            calls.append(tool)
            raise RuntimeError('执行器异常')

        with tempfile.TemporaryDirectory() as project:
            orchestrator = skill_orchestrator.Orchestrator(registry=Registry(), project=project)
            orchestrator.tool_executor = executor
            row = orchestrator.execute(item.name, {'project': project})

        self.assertEqual(row['status'], service_contract.TOOL_FAILED)
        self.assertIn('执行器异常', row['detail'])
        self.assertEqual(row['tools'][0]['status'], service_contract.TOOL_FAILED)
        self.assertEqual(calls, ['probe.tool'])


if __name__ == '__main__':
    unittest.main()
