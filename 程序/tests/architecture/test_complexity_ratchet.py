"""结构复杂度棘轮：嵌套深度、参数个数、类行数只许下降（R1777 审计第 28／29／30 项）。

与 `test_function_size_ratchet` 同口径：超线的老代码登记当前值，**只许下降、不许新增**；
降到阈值以内必须从登记表删除。新代码用提前返回／辅助函数压平嵌套，用 dataclass 或参数对象收
参数，用 *_service／*_controller 或 Mixin 拆大类，不要抬高登记值。
深度只数 if／for／while／try／with 的嵌套层数；参数个数不含 self／cls。
"""
import ast
import unittest

from tests.architecture._scan import production_files

NEST_LIMIT = 6
PARAM_LIMIT = 7
CLASS_LIMIT = 600
CLASS_SLACK = 15

NESTING_CAPS = {
    ('app.py', 'tick'): 6,
    ('asset_batch_execution.py', 'run_batch'): 6,
    ('workflow_engines.py', 'run_background'): 6,
}
PARAM_CAPS = {
    ('recon_service.py', 'run'): 13,
    ('ui_widgets.py', '_configure_button'): 14,
    ('animatic_service.py', 'build_bundle'): 12,
    ('app.py', '__init__'): 11,
    ('cell_hover.py', '__init__'): 11,
    ('pet_report.py', 'daily'): 11,
    ('prompt_window.py', 'show'): 11,
    ('desktop_idea_chat.py', '_deliver_desktop_app'): 10,
    ('engine_probe.py', 'probe'): 10,
    ('environment_check.py', 'run_checks'): 10,
    ('idea_chat.py', 'receive_brief'): 10,
    ('native_assets.py', 'attach_controls'): 10,
    ('pet_llm.py', '_attempt'): 10,
    ('pet_report.py', 'gather'): 10,
    ('recon_service.py', 'collect'): 10,
    ('skill_orchestrator.py', '__init__'): 10,
    ('skill_panel_support.py', 'stage_button_label_for'): 10,
    ('tts_api.py', 'run_lines'): 10,
    ('ui_widgets.py', '__init__'): 10,
    ('desktop_idea_chat.py', 'open_flow_agent'): 9,
    ('desktop_script_pages.py', 'content_box'): 9,
    ('edit_service.py', 'assemble_image_timeline'): 9,
    ('idea_transcript.py', 'append'): 9,
    ('model_pool.py', 'tools_search'): 9,
    ('pet_agent.py', '__init__'): 9,
    ('pet_ui_support.py', 'flourish'): 9,
    ('stage_parallel.py', 'parallel_map'): 9,
    ('ui_widgets.py', '_show_stage_execution'): 9,
    ('asset_auto_batch_service.py', 'auto_batch'): 8,
    ('asset_batch_controller.py', '__init__'): 8,
    ('asset_batch_execution.py', 'resume_record'): 8,
    ('asset_detail_service.py', '_publish'): 8,
    ('client_profiles.py', 'adapt_executable'): 8,
    ('codex_tasks.py', 'prepare_task'): 8,
    ('comfy_service.py', 'submit'): 8,
    ('confirm_gates.py', 'record'): 8,
    ('desktop_automation_service.py', 'run_due'): 8,
    ('model_router.py', '__init__'): 8,
    ('native_assets.py', 'run'): 8,
    ('pet_chat_coordinator.py', '__init__'): 8,
    ('pet_llm.py', 'settle'): 8,
    ('previs_automation.py', 'start'): 8,
    ('production_lock_fields.py', '__init__'): 8,
    ('recon_service.py', '_fetch_all'): 8,
    ('recon_service.py', '_search_all'): 8,
    ('reference_wall.py', 'show'): 8,
    ('skill_orchestrator.py', 'run_stage_with_template'): 8,
    ('workflow_context_budget.py', 'prepare_request_context'): 8,
    ('workflow_engines.py', 'launch_interactive'): 8,
    ('workflow_tasks.py', 'script_followup'): 8,
    ('workflow_tasks.py', 'script_prompt'): 8,
}
CLASS_CAPS = {
    ('pet_cloud.py', 'Cloud'): 1115,
    ('desktop_idea_chat.py', 'IdeaChatMixin'): 1031,
    ('app.py', 'App'): 1388,
    ('desktop.py', 'Desktop'): 1302,
    ('skill_panel.py', 'Panel'): 1205,
    ('pet_ui_stages.py', 'PetStagesMixin'): 1186,
    ('pet_ui_voice.py', 'PetVoiceMixin'): 1119,
    ('desktop_media_pages.py', 'MediaPagesMixin'): 994,
    ('pet_ui_view.py', 'PetViewMixin'): 774,
    ('engine.py', 'Studio'): 735,
    ('skill_orchestrator.py', 'Orchestrator'): 719,
    ('pet_llm.py', 'RequestLedger'): 639,
    ('desktop_auto_flows.py', 'AutoFlowsMixin'): 638,
}


def _depth(node, level=0):
    deepest = level
    for child in ast.iter_child_nodes(node):
        step = isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With,
                                  ast.AsyncFor, ast.AsyncWith))
        deepest = max(deepest, _depth(child, level + step))
    return deepest


def _param_count(node):
    args = node.args
    positional = args.posonlyargs + args.args
    count = len(positional) + len(args.kwonlyargs) + (args.vararg is not None) + (args.kwarg is not None)
    if positional and positional[0].arg in ('self', 'cls'):
        count -= 1
    return count


def measure():
    """返回 (嵌套深度, 参数个数, 类行数) 三张 {(文件名, 名字): 数值} 表；同名取最大。"""
    nesting, params, classes = {}, {}, {}
    for path in production_files():
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
        for node in ast.walk(tree):
            key = (path.name, node.name) if hasattr(node, 'name') else None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nesting[key] = max(nesting.get(key, 0), _depth(node))
                params[key] = max(params.get(key, 0), _param_count(node))
            elif isinstance(node, ast.ClassDef):
                size = node.end_lineno - node.lineno + 1
                classes[key] = max(classes.get(key, 0), size)
    return nesting, params, classes


def _over(actual, limit, caps, label, unit):
    return ['%s::%s %d %s > 上限 %d' % (key[0], key[1], value, unit, caps.get(key, limit))
            for key, value in sorted(actual.items())
            if value > limit and value > caps.get(key, limit)]


def _stale(actual, limit, caps, slack=0):
    out = []
    for key, cap in caps.items():
        value = actual.get(key)
        if value is None:
            out.append('%s::%s 已不存在或改名，请更新登记' % key)
        elif value <= limit:
            out.append('%s::%s 实际 %d，已不超线，请从登记表删除' % (key[0], key[1], value))
        elif cap - value > slack:
            out.append('%s::%s 实际 %d，登记 %d，请下调到 %d' % (key[0], key[1], value, cap, value + slack))
    return out


class ComplexityRatchet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nesting, cls.params, cls.classes = measure()

    def test_nesting_does_not_grow(self):
        self.assertEqual(_over(self.nesting, NEST_LIMIT - 1, NESTING_CAPS, '嵌套', '层'), [],
                         '请用提前返回或辅助函数压平，不要抬高登记值')

    def test_parameter_count_does_not_grow(self):
        self.assertEqual(_over(self.params, PARAM_LIMIT, PARAM_CAPS, '参数', '个参数'), [],
                         '请用参数对象收拢，不要抬高登记值')

    def test_class_size_does_not_grow(self):
        over = [row for row in _over(self.classes, CLASS_LIMIT, CLASS_CAPS, '类', '行')]
        self.assertEqual(over, [], '请拆分类，不要抬高登记值')

    def test_registries_track_real_values(self):
        stale = (_stale(self.nesting, NEST_LIMIT - 1, NESTING_CAPS)
                 + _stale(self.params, PARAM_LIMIT, PARAM_CAPS)
                 + _stale(self.classes, CLASS_LIMIT, CLASS_CAPS, CLASS_SLACK))
        self.assertEqual(stale, [])


if __name__ == '__main__':
    unittest.main()
