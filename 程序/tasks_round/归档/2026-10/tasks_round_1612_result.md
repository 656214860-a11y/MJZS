# R1612 函数行数棘轮（Q2）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round_1610_result.md) J 第二批 Q2）。
- 测试：定向 `tests.architecture.test_function_size_ratchet`＋`test_agents_md` 通过；架构门禁 350/350 通过（170.684 秒，较上轮 348 增 2）；默认冒烟 0 失败。完整安全全量未跑。
- 欠账：本轮改源码／测试，`project_status.md` 全量欠账计数 +1，未清。

## 改动

1. **新增函数行数棘轮** `tests/architecture/test_function_size_ratchet.py`：新函数 ≤ 150 行；现存 21 个 ≥150 行的函数按 (文件, 函数名) 登记上限，**只许下降**；登记上限高于实际 15 行以上或已降到 ≤150 行必须同步登记表。口径与 `test_module_size_ratchet`（文件行数棘轮）完全一致。
2. **`AGENTS.md` §5 清单同步**加入 `test_function_size_ratchet.py`（`test_agents_md` 要求清单与实际文件集合相等）。

## 登记的超限函数（仅上界，实际即上限值）

`keyframe_comfy.show`(626)、`desktop_writing_page.writing`(577)、`pet_models_ui.open_manager`(497)、`storyboard_files.show_final`(401)、`storyboard_files.show`(335)、`desktop_storyboard_page.storyboard`(323)、`app.__init__`(267)、`desktop_idea_chat.open_flow_agent`(254)、`local_previs.show`(252)、`desktop_script_pages.script_structure`(251)、`asset_batch.show`(243)、`desktop_asset_pages.assets`(225)、`ui_theme.install_window_placement`(224)、`cloud_video.settings_window`(204)、`reference_wall.show`(193)、`desktop_script_pages.content_box`(187)、`writing_api._preparation_step`(181)、`desktop.__init__`(175)、`desktop_idea_chat.send_message`(171)、`native_assets.attach_controls`(167)、`desktop.show`(152)。

## 未在本轮物理拆解最长函数的理由

- `keyframe_comfy.show`(626) 等属于「一个对话框内约 30 个嵌套闭包、共享 win／view／episode 等几十个局部量」的 UI 构建函数。机械外提会把这些局部量变成长参数表或引入上下文对象，**改动面大、收益小、回归风险高**；现有覆盖为 Tkinter 结构断言（`tests/test_keyframe_comfy.py`），不足以兜住回调接线的语义回归。
- 因此本轮采用与 `test_module_size_ratchet` 相同的治理方式：**登记上限并冻结增长，义务是后续逐步下降**，把物理拆解留给专门的拆分轮（有预算与明确验收时再做）。不把「已登记」冒充「已拆解」。

## 下一项

Q4（正式 JSON 产物 schema 版本与迁移守卫）。