# R2954 合并轮结果
<!-- round-evidence: {"commit_base": "10e389b5", "credential_hits": 0, "evidence_sha256": "5617a34b67a9ee4b", "exit": 0, "failed": 0, "passed": 0, "round": 2954, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/wip-R2942` 到 master。
- 说明：R2942 功能轮——共享输入框对齐 DSH（`/` 补全浮层浮在输入框上方＋五图标悬停提示卡＋流畅度缓存）；模型选择器内嵌共享输入框（页面级「阶段配置」按钮＋模型下拉框在 13 页全部删除）；剧本准备页「项目文件」四表合并为单一竖向列表＋折叠开关（折叠时右侧功能区放大）。
- 冲突：5 处，全部解决：
  - `desktop.py`：保留分支新增的 `import tkinter as tk`，采纳 master 的 `orchestrator.stage_handler_registry`／`ui_plugin_registry` 路径。
  - `page_navigation_controller.py`：采纳 master 的 T10 门面（`_sys.modules[__name__] = _entity`），R2942 的「缓存不再存 stage_button」落到实体 `orchestrator/page_navigation_controller.py`（`cache_entry` 5 参 → 4 参）。
  - `skill_panel.py`：采纳 master 的 `orchestrator.skill_notes` 导入；删除已随 R2942 移除的 `attach_stage_pickers/stage_button_for` 导入。
  - `tests/architecture/test_complexity_ratchet.py`：登记取 R2942 实测（`Desktop` 819、`Panel` 646），合并后门禁实测同值。
  - `tests/test_desktop_compact_layout.py`：保留 R2923/R2942 的共享输入框与单列表断言＋master R2897 侧栏项目选择器断言，删除已过时的 `idea_row`／`idea_input_hint`／`d.list` 断言。
- 验证：默认冒烟 8/8；架构门禁 470/470；定向回归 `test_idea_chat test_ui_edges_pages test_desktop_compact_layout test_writing_page_services test_shared_input_ui test_shared_input_stages test_video_ui test_skills test_page_cache test_page_navigation_controller` 全绿。未跑全量。
