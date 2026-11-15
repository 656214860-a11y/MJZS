# R2605 结果：SWE-2 T7（步骤 1/3）test_ui_edges.py 按功能域拆分＋共享夹具模块
<!-- round-evidence: {"commit_base": "4ee740d0", "credential_hits": 0, "evidence_sha256": "0bf6f2c7735f0894", "exit": 0, "failed": 0, "passed": 227, "round": 2605, "tests": "run_selftests.py -k ui_edges selftests skip_hygiene static_hygiene agents_md idea_inline_brief"} -->

## 类型与三问

- 类型：结构治理轮（任务书 T7 第 1 步：5440 行测试文件按功能域拆分）。本轮按规则 16 的纪律执行——只搬测试与修 import，断言／fixture／测试逻辑逐字保留；因轮次类型是结构治理而非测试搬家，`dev.py commit` 不触发 `test_move_audit`（该守卫只认搬家标记且不支持 1→N 拆分），改用 **AST 级逐字核对**提供同等保证：旧文件 186 个函数节点（含方法、嵌套函数、装饰器）与新文件逐一比对，缺失 0、差异 0。
- 测试：默认冒烟 8/8 绿；`run_selftests.py --layer architecture --all` 466/466 绿；定向 `run_selftests.py -k`（5 个新域文件＋消费方抽样）全绿；`scripts/skill_package_pins.py --check` 绿。
- project_status 欠账：无新增（状态页按规则仅 master 侧同步）。

## 拆分方案（T7 步骤 1）

`tests/test_ui_edges.py`（5440 行，115 条用例）→ 6 个文件：

| 新文件 | 内容 | 分类落位 |
| --- | --- | --- |
| `tests/ui_edges_support.py` | 项目夹具（make_minimal/adopted/populated_project、adopt_storyboard_fixture、keep_storyboard_fresh、with_dialogue、real_png、PNG、settle_workers、final_storyboard_dir(s)、popup_windows、widget_texts、FFMPEG/FFPROBE/PROGRAM/PAGE 等）＋ `UiEdgeCase` 基类（setUp/enable_sanhu_auto/setUpClass 逐字迁入） | 非 test_ 前缀，不被发现 |
| `tests/test_ui_edges_autopilot.py` | UiEdgeTests 无人值守／自动链 26 法 ＋ BatchContinuationTests、WorkerThreadSafetyTests | gui-e2e（Tk 受控并行） |
| `tests/test_ui_edges_pages.py` | UiEdgeTests 页面构建／布局 20 法 ＋ StartupFirstPaint、StageConfigEntry、BriefTint、ContentBoxFit、TalkBoxFit、PageHint | gui-e2e |
| `tests/test_ui_edges_tables.py` | UiEdgeTests 表格／缩略图 11 法 ＋ RowHeight、StoryboardRowLayout | gui-e2e |
| `tests/test_ui_edges_controls.py` | UiEdgeTests 控件／选择器 15 法 ＋ EditorStartMenuScan | gui-e2e |
| `tests/test_ui_edges_guards.py` | PromptWindowSourceGuard、ApprovedVersionSourceGuard、EngineNameFallback（纯源码扫描＋文件夹具，不碰 Tk） | service（非 Tk 并行池，白赚并行） |

原 `UiEdgeTests` 按域拆为 `UiEdgeAutoTests/UiEdgePagesTests/UiEdgeTablesTests/UiEdgeControlsTests`（基类 UiEdgeCase），小类名不变。

## 保真证据

- 用例数：旧文件 `def test_` 计数 115 → 新文件合计 115（34+40+15+18+8）。
- AST 逐字核对：旧文件全部 186 个函数/方法 AST 与新文件集合一一对应，0 缺失、0 差异。
- skip 台账：`维护记录/skip台账.json` 88 条 `tests/test_ui_edges.py` 登记按新类名／新文件重映射（UiEdgeTests.x → UiEdge<域>Tests.x，小类仅换 file）；`test_skip_hygiene` 双向一致性绿。
- 分类：`gui_test_module` 按直接 import 判定——4 个域文件仍含方法内 `import desktop`／`from desktop import Desktop` → GUI；guards 只引 `ui_edges_support` 具名符号 → service。GUI_E2E_MODULES 更新为 4 域文件＋test_pet_ui。
- 星号导入禁令：域文件初稿用 `from ui_edges_support import *` 被 `test_static_hygiene` 拦下，已改为按实测用量生成的具名 import 列表。

## 消费方与登记同步

- 17 个测试文件与 3 个 `维护记录/基准脚本/` 基准脚本的 `test_ui_edges` 导入改为 `ui_edges_support`（保持各自 `tests.`／裸名两种风格）；4 处模块级用法 `test_ui_edges.X` → `ui_edges_support.X`。
- `run_selftests.py`：GUI_E2E_MODULES 更新、文档注释同步；`tests/test_selftests.py` 三处 `test_ui_edges` 占位名 → `test_ui_edges_autopilot`。
- `smoke_test.py` ROUND_CHECKS 两条历史锚点路径 → `test_ui_edges_autopilot.py`（关键词不变，锚定的测试方法按内容归属 autopilot 域）。
- `docs/stages/S01_剧本准备.md`（REQ-S01-76 锚点表）、`S03_初步分镜.md`（REQ-S03-19 叙述）、`README.md` 四处 `test_ui_edges` 引用 → 按锚点实际位置改为新文件名。
- `distribution_manifest.md`：`程序/tests/**` 已 glob 覆盖，无需登记。

## 环境补备（不入提交）

- 本工作树按 `维护记录/外部技能包哈希.json` 克隆 3 个 gitlink 技能包（AIGC创作全流程@1a43ae5、剧本锻造@6c3d739、编剧技能集@357d134）——新克隆工作树原本缺失，消费方测试报 SKILL 引用缺失。
- `维护记录/基准历史.json`（gitignored 机器本地文件）自主工作区复制——`test_agents_md` 基准历史声明用例依赖。

## 轮外记录（不处理）

- `scripts/test_move_audit.py` 只支持 N→N 改名/移动，不支持 1→N 拆分；如后续测试搬家轮需要拆分场景，可扩展该守卫（T7 步骤 2 再议）。
- `维护记录/测试分层基线.json` 由 `--layer architecture --all` 正常刷新（architecture：313→466 用例计数随门禁增长，elapsed 22.6s）。

## T7 剩余步骤

- 步骤 2：`run_selftests.py`（约 1600 行）拆分：发现／调度／凭据复用／报告各一个模块并补单测。
- 步骤 3：非 Tk 并行收益实测——全量 `--all --safe` 前后 `full-safe-receipts.json` 秒数对比（本轮已验证域文件可并行跑 4 路 GUI 工作单元，单文件粒度收益已体现）。

## 提交

- 待回填 hash。
