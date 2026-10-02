# R671 修复轮：阶段配置 SKILL 面板五项修复

## 开头三问

1. 当前轮次与台账是否一致：开始时一致；本报告为 R671，验证前会将台账推进为 R672 待执行。
2. 上一轮进行中未完成的任务是什么：R670 已完成全量基线；本轮为新授权的 SKILL 面板修复。
3. 下一轮该做什么：仅在本轮验证失败或 .codex 根因越出 `skill_panel.py` 时，另立一轮处理登记项。

## 验证档位声明

本轮改动涉及 2 个模块（`skill_panel.py` 与 `tests/test_skills.py`），按用户指定执行默认冒烟 + `--affected skill_panel` + 架构门禁，跳过全量安全自检，理由：仅为单个 UI 面板及其回归，未触及启动路径、L0 契约、用户数据格式或删除路径权威服务。

## 第一部分：只读诊断（修复前）

1. **说明区首次未刷新。** `skill_panel.py:1074` 的 `refresh_notes()` 重建目录并调用 `show_note()`；它在 `build_notes()`（`skill_panel.py:1060`）和 `save_flow_skill()`（`skill_panel.py:923`）调用。普通注册 SKILL 勾选框在 `skill_panel.py:798-799` 仅绑定 `command=self.save`，而 `save()`（`skill_panel.py:1210`）不刷新说明。`load()`（`skill_panel.py:1171`）只同步变量与流程勾选，也没有在完成后刷新。原始片段：`variable=var, command=self.save`、`self.refresh_notes(label)`。
2. **“SKILL”标签未显示。** 标签仍在 `skill_panel.py:783` 创建：`self.flow_skill_label = ttk.Label(..., text='SKILL', ...)`；紧随注释（`skill_panel.py:782`）明确写为“不 pack”，因此不是已删除而是 R622 之后保留兼容属性时未创建布局项。
3. **“台词润色”与“情绪曲线”空白。** 两项都是 `build_flow_skill()` 的 `ttk.Checkbutton`，由 `layout_skill_controls()`（`skill_panel.py:831-851`）统一用 `grid()` 自动换行；未发现这两项之间的占位控件、隐藏控件或 row/columnspan。空白来自同一行同时混排下拉、流程 SKILL 与注册 SKILL，再按请求宽度换行的贪心布局；标签又不参与该布局，首行可用顺序不稳定。
4. **`.codex` 路径。** `skill_panel.py` 的 SKILL 文件读取只在 `markdown_document()`（`skill_panel.py:78-92`）读取传入路径、`flow_skill_choices()`（`skill_panel.py:145-164`）调用 `workflow_settings.preset_skill()`；不存在 `_home_skill()` 调用。`workflow_settings.py:66-67` 的 `preset_skill()` 恒为 `_bundled_skill()`，`_home_skill()` 已不存在（R622 结果也记录其删除）。当前项目 `D:/漫剧下载/项目/摄像头3_20260924/skill_config.json` 的 script 条目只引用 `script-dialogue-polish` 与 `script-emotion-curve` 注册 ID，未含 `.codex`。结论：不是磁盘读取、显示缓存或配置残留；候选列表来源已是程序 `skills/`。
5. **顺序不一致。** 勾选框来源 `Panel.__init__()` 的 `self.skills`，在 `skill_panel.py:578-579` 用 `sorted(..., key=skill_order)` 重排；说明区 `note_entries()`（`skill_panel.py:1065-1071`）也读取 `self.skills`，但还在前面插入流程 SKILL。注册项相对顺序相同，完整列表顺序与勾选框不一致的差异是 `note_entries()` 的 `flow_skill_choices()` 前置行（1065）以及 `skill_order` 重排（579）；不符合“以注册表返回顺序为准”。
## 第二部分：修复

- skill_panel.py:579：取消面板侧排序，直接采用 skill_registry.getByStage() 的注册顺序；勾选框与说明区均遍历同一 self.skills。
- skill_panel.py:784-785：将既有 SKILL 标签纳入原 skill_controls 响应式 grid 布局，恢复可见性且不改变布局容器。
- skill_panel.py:798-802、893-897、1234-1250：注册 SKILL 勾选框改绑 save_and_refresh_notes()；load() 完成变量同步后调用 refresh_notes()。因此打开页面与任一勾选变化都会重建说明区，不再依赖“全选”下拉。
- skill_panel.py:775、805-808、899-949：新增“删除已勾选 SKILL”按钮。仅接受 程序/skills/ 内、后缀严格为 .skill.md 的现存文件；删除前只读检查当前项目 skill_config.json，发现注册 id 引用即警告并返回，不改配置；用户确认后复用 storage_maintenance.recycle_paths()，根参数为程序目录，回收目录固定为 程序/工作流任务/回收站/。成功后强制注册表刷新、移除对应控件/变量、刷新说明区并重排。

未为 .codex 增加 shim、重导出或扫描分支：该项诊断为无残留，故无需也未改 skill_registry.py 或用户配置。

## 改动文件清单

1. skill_panel.py：本轮唯一生产文件。
2. tests/test_skills.py：阶段面板顺序、加载刷新、标签、删除回收与引用警告回归。
3. project_status.md、本结果文件：轮次台账与审计记录；不改变运行时功能或用户项目数据。

## 新增／更新回归断言

1. 页面构造后，说明目录内容等于当前流程项加注册表返回的阶段项，不依赖“全选”。
2. SKILL 标签文本存在、处于 skill_controls，删除按钮存在。
3. 注册 SKILL 勾选顺序与说明目录中的注册项顺序均等于 registry.getByStage() 的原始返回顺序。
4. 勾选程序 skills/temporary-delete.skill.md 后，源文件消失、程序/工作流任务/回收站/ 有副本，面板变量立即移除。
5. 当前项目 skill_config.json 引用 referenced-delete 时，显示警告、不弹确认、源文件保留。
6. 工作流候选回归继续限定为程序内预置路径，无 .codex 路径。

## 验证（声明档位内）

默认冒烟命令：D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py

原始输出片段：通过：8 项；失败：0 项；冒烟测试通过，可以进入下一轮。

受影响模块命令：D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected skill_panel

原始输出片段：ALL TESTS PASSED；定向 skill_panel 门禁 0 个文件有红；通过：9 项；失败：0 项。

该命令有一条既有的增量台账临时文件权限提示：维护记录/自检增量.json.*.tmp；输出明确标注“不影响结果”，且定向测试取得 ALL TESTS PASSED。

架构门禁命令：D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture

原始输出片段：Ran 102 tests in 26.983s；OK；架构治理测试通过。

## 用户数据未改动确认

未写入、迁移或删除任何用户项目数据、skill_config.json、密钥或用户配置。删除功能的引用检查只读；其实际回收目标仅限程序 skills/ 内的 .skill.md，本轮回归使用临时目录。

## J 后续

无。本轮未发现 .codex 读取残留；无需另立该项轮次。若后续运行时另有来源绕过 skill_panel.py，应另立轮次定位，不能在本面板内增加兼容路径。

## 自审

是：生产改动仅在 skill_panel.py；复用既有 storage_maintenance.recycle_paths()；未改 skill_registry.py 扫描根、缓存键或逻辑；未引入新的扫描；未夹带其他问题修复。
