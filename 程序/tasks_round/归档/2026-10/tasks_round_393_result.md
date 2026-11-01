# R393 功能轮结果

## 范围

- 前置已读：`tasks_round/tasks_round_391_result.md` 第 3 节。
- 修改：`tests/architecture/test_dynamic_import_registry.py`、`tests/architecture/test_stage_command_contract.py`、`tests/architecture/test_completion_gate.py`、`tests/architecture/test_recycle_service.py`、`project_status.md`、本结果文件。
- 未修改：生产 `.py`、`AGENTS.md`、`architecture.md`、`PROJECT_MAP.md`。

## 门禁测试

- 动态导入：扫描指定 L4 模块，禁止 `__import__`、`import_module` 和 `importlib.import_module` 绕过 `ui_plugin_registry.module()`。
- 阶段命令：扫描 L4 阶段命令调用方，要求存在 `stage_handler_registry.start()` 入口，禁止直接调用阶段实现。
- 完成核验：禁止 UI/Agent 直接发送 `stage.completed`，并要求发送模块显式依赖 `stage_completion_service`。
- 回收服务：禁止授权范围外的 `os.remove`、`os.unlink`、`shutil.rmtree` 和 `Path.unlink`；报告精确文件:行号。

## 验证

命令：`D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`

- 发现并调度全部 18 项架构测试，新增四份测试均可运行。
- 通过：15 项。
- 失败：3 项，均为新增门禁发现的既存生产代码契约违规：
  - 动态导入：`app.py:1438 importlib.import_module`。
  - 完成事件：`pet_ui.py:1056`、`pet_ui.py:1125` 直接发送 `stage.completed`。
  - 回收服务：21 处未授权物理删除：`app_shortcut.py:182`、`asset_generated_import_service.py:19,72`、`asset_thumbs.py:185,527,569`、`desktop.py:4919,5207,5356`、`keyframe_comfy.py:162`、`line_endings.py:100`、`local_video.py:57`、`model_secrets.py:150`、`native_assets.py:100`、`pet_report.py:129`、`projects.py:106,134`、`qwen_adapter.py:144`、`storyboard_final.py:165`、`white_model.py:76`、`workflow_engines.py:95`。
- 阶段命令静态门禁通过。

## 结论

本轮仅增加架构测试与记录文件；未为通过门禁而弱化断言或修改生产代码。后续修复轮应按违规类别逐项处理。
