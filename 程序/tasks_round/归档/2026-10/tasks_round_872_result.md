# R872 UI 统一入口覆盖率：FileDialog 收口

## 范围与结论

- `UI统一入口路线图_v1.md` 尚未完成：其余 14 项仍标为“待审计”，不可据此宣布路线图完成。
- 本轮完成其中“文件选择”入口的全量收口：所有业务模块均改为通过 `ui_dialogs.FileDialog` 调用，不再直接调用 `tkinter.filedialog`。

## 实现

- 迁移 `app`、资产详情／参考图导入、桌面工作台、参考图墙、阶段配置、分镜文件、白模和工作流设置中的 18 个文件选择或保存调用。
- 架构门禁从部分页面的冻结上限补充为全业务模块零直调规则；`ui_dialogs.py` 是唯一允许直连 tkinter 文件选择器的边界。
- 调整 ComfyUI 启动回归测试，改为注入统一入口所持有的选择器。
- `app` 主镜头表／资产选择器、`reference_wall`、`local_previs`、`keyframe_comfy` 与 `storyboard_files` 的业务表格改用 `DataTable`，保留原有选择、勾选列及自适应列宽行为。
- Qwen、Seedream、TTS 与工作流设置表单的 8 个单行输入及 1 个多行输入改为 `LineInput`／`TextArea`。
- 全部业务裸窗口均改用 `BaseDialog`：资产参考图导入、白模镜头选择／预演、资产放大预览、参考图候选墙、Seedream 与流程设置、背景人物、云端视频、首帧制作、剧本准备、资产选择、应用设置、SKILL 管理以及项目管理窗口均保持原有布局与模态语义。
- 继续收口所有业务右键菜单：`app`、`desktop`、单元格悬浮层及三虎的一级／子级菜单均经 `ContextMenu`；统一组件补充子菜单、单选项、禁用标题、安全 `grab_release` 与旧 Tk 菜单状态的兼容代理。
- 视频工作台与桌面工作台的非确认型模态消息已迁入 `NotificationDispatcher`，提示同时写入状态栏；删除、付费、导出和强制关闭等有副作用的确认仍保留原有同步确认语义，待以 `ConfirmDialog` 的异步回调逐项迁移。
- 视频提示词的全选、剧本聊天记录的保存与取消，已改由 `ShortcutRegistry` 以页面作用域登记，避免与既有复制动作冲突。
- 主题层的复选框四态图元已迁入 `IconLoader.check_indicator()`：按 Tk 宿主、尺寸、状态与主题色缓存，不再由主题页直接构建 `PhotoImage`。

## 验收

- 提交门禁：`python run_selftests.py --all --safe` 必须以 0 红完成，并写入当前内容树的安全全量验证记录。
- `python -m unittest 程序/tests/architecture/test_file_dialog_boundary.py`：5 条／0 红。
- `python -m unittest test_ui_edges.UiEdgeTests.test_launch_comfy_does_not_block_on_a_starting_service test_ui_edges.UiEdgeTests.test_launch_comfy_is_silent_in_the_production_chain`（在 `程序/tests`）：2 条／0 红。
- `python -m unittest tests.architecture.test_data_table_boundary tests.architecture.test_local_previs_json_boundary`（在 `程序`）：17 条／0 红。
- `python -m unittest test_keyframe_comfy`（在 `程序/tests`，`PYTHONPATH=..`）：14 条／0 红。
- `python -m unittest test_video_ui.AssetCheckTableTests` 的主镜头表与资产选择器定向用例：5 条／0 红。
- `python -m unittest test_final_viewer`（在 `程序/tests`，`PYTHONPATH=..`）：13 条／0 红。
- `python -m unittest tests.architecture.test_input_boundary tests.architecture.test_workflow_settings_json_boundary`：5 条／0 红；`test_tts test_qwen_adapter`：43 条／0 红。
- `python -m unittest tests.architecture.test_dialog_boundary`：5 条／0 红；`test_reference_images`：21 条／0 红。
- 白模入口与边界：60 条／0 红；参考图墙：13 条／0 红；流程设置／对话框／表格架构门禁：22 条／0 红。
- `test_skills test_skill_tools test_skill_templates`：145 条／0 红；`test_video_ui.AssetCheckTableTests`：12 条／0 红。静态 AST 审计显示业务模块中零个直接 `tk.Toplevel` 调用；仅 `ui_widgets.py` 内统一基类实现保留该调用。
- `rg 'filedialog\\.' 程序 --glob '*.py' --glob '!tests/**'`：仅统一入口 `ui_dialogs.py` 保留直连实现。
- `python -m unittest tests.architecture.test_context_menu_boundary tests.test_ui_notifications`（在 `程序`）：6 条／0 红。
- `python -m unittest test_cell_menu`（在 `程序/tests`，`PYTHONPATH=..`）：40 条／0 红；`test_pet_ui.MenuFeedbackTests`：11 条／0 红。
- 静态 AST 门禁 `test_context_menu_boundary` 断言：除 `ui_widgets.py` 的统一实现外，所有业务模块零个直接 `tk.Menu` 构造。
- `test_video_ui`：64 条／0 红；`test_idea_chat.SendMessageTests.test_composer_right_click_only_offers_paste_for_text_clipboard`：1 条／0 红。
- `test_app_shortcut test_ui_shortcuts`：41 条／0 红；`tests.architecture.test_shortcut_registry_boundary`：1 条／0 红。
- `test_ui_icons test_ui_theme`：17 条／0 红；图标与滚动条架构门禁：2 条／0 红。

## 后续

- 继续以全量零直调为标准处理 DataTable、LineInput/TextArea、BaseDialog 与 ShortcutRegistry；历史“数量不得增加”门禁不能作为路线图完成凭据。
- 路线图的通知分发、忙碌状态、快捷键、提示、图标、滚动条、术语和阶段名，以及既有权限边界审计仍未逐项提供完成证据，不能宣布全路线图完成。
