# R4361 · UX-FP-IMPORT：项目文件面板「导入文件」入口（REQ/DES-S01-103）
<!-- round-evidence: {"commit_base": "e0f94779c", "credential_hits": 0, "evidence_sha256": "3fd50a5c0f91c8b4", "exit": 0, "failed": 0, "passed": 189, "round": 4361, "tests": "run_selftests.py -k files_panel"} -->

## 开头三问

- （一）本轮类型：功能轮（AGENTS.md §3.1，先文档后码）。车道 `codex/ux-fp-import`，基准 `e0f94779`。队列卡 UX-FP-IMPORT，落实用户 2026-11-22 20:45「右侧停靠面板中没有导入文件的入口, 需要给用户导入新文件的功能」（用户 11-23 授权按推荐执行）。
- （二）测试跑了吗、三个基线：定向 `run_selftests.py -k files_panel` 189/189 绿（退出码 0）；`smoke_test.py --affected desktop_files_panel` 10/10 项绿（退出码 0）；`smoke_test.py --architecture` 702 条全绿（退出码 0）。默认冒烟基线未单独跑（`--affected` 冒烟已含 10 项通过）；全量回归未跑（卡面未要求，以 `full-safe-receipts.json` 凭据为准）。
- （三）欠账少了吗：未新增欠账；REQ-S01-103 由 ⬜ 转 🟡。

## 缺陷与复现方式

项目文件面板（`ProjectFilesPanel`）没有导入入口：面板头部只有收起钮与筛选控件，不存在把本机文件复制进项目的命令——`ProjectFilesPanel.import_files`、`desktop_files_panel_filters.import_into_stage`/`import_suffixes`/`_import_target` 在基线 `e0f94779` 上均不存在（`git diff` 全部新增行）。复现：`FilesPanelImportTests` 的 10 条用例直接调 `panel.import_files()` / `import_into_stage(...)` / `_import_target(...)`。

## 改前红（先写测试）

上一执行者先写 10 条测试（`FilesPanelImportTests`）再见红后改码；改前红的原文输出随宿主会话中断未能留存，红因按基线 `e0f94779` 代码与本轮 diff（全部新增行）逐条核对：

- `test_import_entry_copies_file_into_stage_write_dir`、`test_import_files_dialog_uses_stage_suffixes`：`ProjectFilesPanel` 无 `import_files` 成员 → AttributeError。
- `test_import_multi_select_copies_each`、`test_import_same_name_overwrite_replaces`、`test_import_same_name_keep_both_renames`、`test_import_same_name_cancel_no_op`、`test_import_never_overwrites_without_asking`、`test_import_rejects_unlisted_type`、`test_import_half_write_leaves_no_partial_file`：`from ui.desktop_files_panel_filters import import_into_stage` → ImportError。
- `test_import_target_never_escapes_project`：`from ui.desktop_files_panel_filters import _import_target` → ImportError。

定向条数 179 → 189（= 改前 + 新增 10），改后无回归。

## 改动（文件:行号）

- `程序/ui/desktop_files_panel.py:19` 导入 `import_into_stage`/`import_suffixes`；`:30` 导入 `BaseDialog`/`DescriptionBlock`；`:190-209` 新增 `_ImportConflictDialog`（同名三选窗：覆盖危险钮／保留两份／取消，关闭与 Esc 按取消）；`:212-219` `_ask_import_conflict` 同步询问；`:222-235` `_import_status_text` 状态栏文案；`:238-276` 新增 `FilesPanelImportMixin`——`_import_stage`（面板当前显示阶段优先，素材库视图回落当前页阶段）、`import_files` 入口（`page.safe` 包裹、无项目/未选阶段给状态栏提示、`file_dialog.open_files` 多选、filetypes 按本阶段允许后缀拼、复制后走 `fill_script_list`/`show_stage` 现有刷新）；`:278` `ProjectFilesPanel` 基类加入 `FilesPanelImportMixin`（行数棘轮内）。
- `程序/ui/desktop_files_panel_filters.py:84` 标题行装 `self._build_import_button()`；`:113-127` `_build_import_button`——`IconLoader.nav_icon('project_new')` 图标（缺图退回文本钮）、`Tokens.Composer.Icon.TButton`、Tooltip「导入文件到当前阶段目录」；`:837-858` `import_suffixes` 按阶段取现有类型判定表（`VISIBLE_SUFFIXES`/`IMAGE_SUFFIXES`/`AUDIO_SUFFIXES`/`VIDEO_SUFFIXES`/`delivery_import_service.ALLOWED_SUFFIXES`）；`:861-869` `_import_target`——目标目录唯一经 `stage_path_service.write_dir`，文件名经 `file_naming.validate` 剥目录段并校验越界；`:872-879` `_check_importable` 白名单外类型点名拒绝；`:882-888` `_default_import_copier`——覆盖经 `agent.core.save_file` 原子替换、新建经 `agent.core.copy_file_new` 排他发布；`:891-901` `_clean_import_temp`、`:904-915` `_import_publish` 失败清 `*.tmp` 残留不留半文件（经 `file_cache.remove_temporary_file`）；`:918-941` `_import_candidates`/`_import_one` 同名三选（缺省取消绝不静默覆盖、`stem(N).ext` 递增改名）；`:944-975` `import_into_stage` 批量入口，成功经 `file_index.update`＋`record_origin(ORIGIN_USER)` 入索引。
- `程序/tests/test_files_panel.py:404-582` 新增 `FilesPanelImportTests` 10 条（无 Tk、临时目录、替身面板）。
- `程序/docs/stages/S01_剧本准备.md`：REQ-S01-103 ⬜→🟡、DES-S01-103 由「未实现」更新为落地设计描述。

## 改后命令输出尾部

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel`（退出码 0）：

```
共 189 条用例，227.2 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：83.4 秒

ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --affected desktop_files_panel`（退出码 0）：

```
✅ 门禁 run_selftests.py（定向：desktop_files_panel）：308 秒 → 0 个文件有红

==================================================
通过：10 项
失败：0 项
==================================================

✅ 冒烟测试通过，可以进入下一轮
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：

```
Ran 702 tests in 236.841s

OK
✅ 架构治理测试：tests/architecture
```

## git diff --numstat 原文

```
2	2	程序/docs/stages/S01_剧本准备.md
180	0	程序/tests/test_files_panel.py
94	4	程序/ui/desktop_files_panel.py
162	1	程序/ui/desktop_files_panel_filters.py
```

## 未验证

- 真实 Tk 界面上导入钮的图标与同名三选窗未人工查看；`_ImportConflictDialog` 经隐藏桌面外的替身断言覆盖决策逻辑，未做截图核验。
- 改前红的原文输出随宿主会话中断未能留存，红因按基线代码与 diff 核对推断（上文已标注）。
- `test_files_panel_stages.py` 未改动（卡面标注「必要时」，既有用例已覆盖阶段切换下的面板行为）。
- 大文件/特殊权限文件的复制耗时与失败路径未实测；半写失败经 `copier` 注入桩覆盖。

## 卡外发现（只记录，不修）

- `_build_import_button` 的 `text=STAGE_RAIL_ALL` 仅作 PNG 缺图时的占位文本，含义不贴切；图标在本机环境可加载，未动。

## 回滚

`git revert` 本轮提交。
