# R646｜结构治理轮：剧本准备页拆分

## 开工三问与验证档位

1. 本轮是结构治理轮：执行 `tasks_round/tasks_round_630_result.md` 的候选 6.1；唯一入口为 `desktop.py` 的剧本准备页 `Desktop.writing()` 及其直接调用链。
2. `Desktop.writing()` 位于 `desktop.py:3456`，462 行，是本页直接定义/调用范围内唯一超过 200 行且最长的函数；本轮拆分目标为 `Desktop.writing()`，起始行 3456。
3. `IdeaChatController` 已承接对话请求、发送节流、附件引用和流式进度状态，本轮不重复拆分。仍留在 UI 层的职责是 Tk 控件构造、事件绑定、页面重建、空闲回调注册、按钮状态和状态文案。

本轮改动涉及 3 个模块（`desktop.py` 剧本准备页函数 + 新建/复用控制器 + 测试文件），按分级规则执行默认冒烟 + `--affected desktop` + 架构门禁，跳过全量，理由：单页面内部拆分，未触及启动路径、契约、用户数据格式或删除路径。

## 执行前只读盘点

`Desktop.writing` 的直接页面定义：`stop_input_hint`（3495，2 行）、`update_input_hint`（3497，23 行）、`refit_talk`（3520，44 行）、`clear_example`（3564，4 行）、`start_writing`（3568，5 行）、`on_modified`（3573，6 行）、`fit_composer`（3579，13 行）、`expand_composer_for_click`（3592，3 行）、`restore_composer_after_blur`（3595，3 行）、`focus_composer_from_hint`（3598，20 行）、`send_on_enter`（3618，4 行）、`measure_page_fixed`（3664，5 行）、`fit_talk`（3669，29 行）、`cancel_layout_job`（3698，11 行）、`schedule_layout`（3709，20 行）、`set_script_box_visible`（3729，10 行）、`cancel_script_load`（3739，11 行）、`fill_script_list`（3750，61 行）、`current_script_tree`（3811，4 行）、`open_script_file`（3815，9 行）、`keep_one_script_selection`（3824，6 行）、`selected_script`（3830，6 行）、`selected_scripts`（3836，7 行）、`selection_changed`（3843，15 行）、`rename_script`（3858，8 行）、`delete_script`（3866，17 行）、`delete_selected_scripts`（3883，20 行）、`script_menu`（3903，15 行）。

直接调用的 `Desktop` 方法：`idea_example`（2967，18 行）、`draft_text`（660，7 行）、`idea_draft_range`（655，5 行）、`idea_still_the_example`（688，3 行）、`queue_initial_brief_document`（1653，18 行）、`restore_idea_draft`（678，7 行）、`tint_brief`（691，20 行）、`show_conversation`（1192，37 行）、`update_idea_attachment_status`（930，21 行）、`update_script_download_button`（1592，8 行）、`finish_bubble_edit`（1070，30 行）、`fit_content`（497，30 行）、`safe`（1638，5 行）、`delete_project`（4358，26 行）和 `open_folder`（6051，1 行）。其余直接调用为 Tk/ttk 控件、既有 UI 辅助函数或受控服务入口。

超过 200 行的函数（按行数降序）：`Desktop.writing`（`desktop.py:3456`，462 行）。因此没有触发“该页面无需拆分”的停止条件。

## 改动文件清单

- `writing_page_controller.py`：新增无 Tk `ScriptListLoadController`，管理剧本文档列表加载的代次失效、每批行集合、最终排序和条目 ID 汇总。
- `desktop.py`：`Desktop.writing()` 委托控制器维护渐进列表加载状态；仍由页面执行迭代调度、Treeview 插入、控件存活检查、可见性切换和状态提示。
- `tests/test_writing_page_controller.py`：新增批次完成、代次失效、最新优先排序和条目集合回归。

未改 `IdeaChatController`、对话协议、删除路径、项目数据格式、其它页面或用户项目目录。

## 验证结果

新增控制器回归：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_writing_page_controller
Ran 2 tests in 0.000s
OK
```

默认冒烟：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
```

定向门禁：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected desktop
共 7 条用例，2.0 秒；0 个文件有红
ALL TESTS PASSED
```

架构门禁原始输出片段：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture
test_migrated_services_never_import_tk ... ok
test_direct_popen_is_limited_to_platform_or_background_boundaries ... FAIL
test_physical_removal_is_recycle_or_tempfile_owned ... FAIL
```

架构门禁中的失败为既存 `test_platform_process_boundary` 与 `test_recycle_service`；本轮控制器不导入 Tk，未修改进程或删除调用链。尽管默认和定向验证通过，已声明档位中的架构门禁存在红项，故本轮结论为 **[TASK_FAILED]**。

## 用户数据确认

本轮未以用户项目目录为目标执行写入命令；未修改 `skill_config.json`、项目 JSON、密钥、媒体或用户资产数据。

## J 后续

- `test_platform_process_boundary` 与 `test_recycle_service` 的既存红项需分别另立修复/诊断轮；本轮不顺手处理。
- 若继续 R630 候选 6.1，须由用户指定 `desktop.py` 或 `pet_ui.py` 的下一个唯一页面入口。

## 自审

- 只处理了 `Desktop.writing()` 的剧本文档列表加载状态拆分。
- 未重复拆分 `IdeaChatController`，Tk 控件构造、事件绑定、页面重建和状态文案仍在 UI 层。
- 未触碰用户数据格式、删除路径、L0 契约或其它页面；全量按预先声明跳过。
