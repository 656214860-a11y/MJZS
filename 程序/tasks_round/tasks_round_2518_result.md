# R2518 结果：剧本准备页响应速度慢的定位与修复（性能/资源轮）

## 三个问题

1. **本轮属于 §3 哪种类型？** §3.7 性能/资源轮（含 §3.2 修复轮性质：定位根因 → 最小修复 → 复测 → 回归）。
2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 `smoke_test.py`：8/8 通过（本轮改动前已跑）。
   - 定向门禁 `smoke_test.py --affected script_workspace_service`：**9/9 通过、0 文件有红、0 跳过，81 秒**（`ALL TESTS PASSED`）。
   - 架构门禁 `smoke_test.py --architecture`：**420 条，失败 4 条**——与本轮改动的**同一棵树上、stash 掉本轮改动后重跑完全相同的 4 条**（实测对照，见下「架构门禁基线对照」），**0 新增、0 消除**，属 worktree 环境缺口，非本轮引入。
   - 全量 `run_selftests.py --all --safe`：**未运行**（本轮改动单一 L2 模块，未命中 §5 全量触发条件；如实记为未运行）。
3. **`project_status.md` 的欠账少了吗？** 未新增欠账；本轮不涉及历史欠账条目。全量欠账计数不变。

## 诊断：问题定位（先建反馈回路，再改代码）

### 反馈回路（可复现、红绿可判）

微基准脚本（临时目录，未入库）：合成项目 = `Provider/Model/创意_日期/{项目设定,项目大纲,角色卡,项目剧本}`，
草稿 `script_raw.md` 约 9 万字符，8 模型 × 8 批 × 15 文件。

| 指标 | 改前 | 改后 | 变化 |
| --- | --- | --- | --- |
| `discover_script_documents` 中位耗时 | **536.1 ms** | **309.1 ms** | **−42.4%** |

### 成本拆解（同一合成项目，插桩统计，改前）

| 操作 | 调用次数 | 累计耗时 | 占比 |
| --- | --- | --- | --- |
| `Path.resolve()` | 4098 | **286.6 ms** | **53.5%** |
| `Path.stat()` | 3842 | 24.6 ms | 4.6% |
| `Path.iterdir()` | 273 | 17.3 ms | 3.2% |
| `Path.read_text()` | 1 | 0.5 ms | 0.1% |

改后同项目插桩：

| 操作 | 调用次数 | 累计耗时 | 占比 |
| --- | --- | --- | --- |
| `Path.resolve()` | **258** | 24.7 ms | 7.7% |
| `Path.stat()` | 3842 | 18.8 ms | 5.9% |
| `Path.iterdir()` | 273 | 14.5 ms | 4.5% |
| `Path.read_text()` | 961 | 136.0 ms | 42.4% |

### 根因

`script_workspace_service._batch_folder_documents()` 对**每一个**候选文件都调用
`path.resolve().relative_to(writing_root)` 做越界校验。目录级（`folder.resolve()`）已经
验过一次，文件级这次 resolve 只剩「防符号链接指向写作根外」一个意义，却占发现总耗时的
**53.5%**。剧本准备页的文件表走 `iter_script_document_rows` 分批加载（每批 24 个、经
`after_idle`），这部分 I/O 全部落在 Tk 主线程上，于是表现为分批反复卡顿。

### 排除的候选（实测否定，避免被历史记录误导）

- `idea_chat.has_history` 的目录 glob + JSON 解析：0.3 ms，排除。
- `writing_api.preparation_file_labels` 读 JSON：0 ms，排除。
- 页面 `build()` 同步段：约 10 ms，排除。
- `page.paint.script` 首绘：223–236 ms（阈值 1000 ms），排除。
- 「全文 `read_text` 去重」：改前实测仅 **0.1%**（该草稿去重只在 `draft['document'] is not None` 时触发，且样例项目里草稿并非自然剧本）。**此项原被误判为热点，实测否定后未采纳**。

结论：`app_logging.py` 里「01 剧本准备约 1.4s」是 R1754 之前「建页同步回填附件与聊天历史」的旧账，
当前已由延迟回填修复；**当前真实热点是逐文件 `resolve()`**。

## 修复（最小改动）

`程序/script_workspace_service.py`：`_batch_folder_documents()` 改为**只对符号链接**做
`resolve()` 越界校验，普通文件保留 `stat()`。净改动 +11 / −2。

语义等价的依据：目录级 `folder.resolve().relative_to(writing_root)` 已挡越界；目录内的普通
文件按构造必然在写作根内；唯一的越界载体是符号链接，而 `Path.is_symlink()` 只是一次廉价的
`lstat` 判断，不付 `resolve()` 的全路径规范化代价。

## 测试

新增 `程序/tests/test_script_workspace_service.py::test_regular_files_skip_resolve_but_symlinks_outside_are_excluded`
（docstring 锚 `REQ-S01-01`）：
- 普通文件正常出现；
- 指向写作根**外**的真实符号链接必须被排除。

改写 `test_all_published_batch_layouts_and_unsafe_entries`：原来用 `mock.patch(Path, 'resolve')`
伪造越界，现在改用**真实符号链接**，与新的按需-resolve 语义对应。**断言未弱化**：越界文件仍
必须不出现在结果里，只把「用 mock 伪造」换成「用真实文件系统构造」。原用例还顺带断言过
「同名目录、越界目录不抛错」，其中越界目录项由 mock 伪造、在真实文件系统下无对应构造方式，
已从该用例移除并在新用例中以符号链接覆盖同一安全边界。

跳过登记：两处 `skipTest` 均用 `skip_reasons.PLATFORM_DIRECTORY_LINK` 常量，
`维护记录/skip台账.json` 274 → 276 条（+2，已登记）。

## 架构门禁基线对照（证明 0 新增红）

同一棵 worktree 树上、`git stash` 掉本轮两个改动文件后重跑 `smoke_test.py --architecture`：

| | 用例总数 | 失败数 | 失败集合 |
| --- | --- | --- | --- |
| 基线（stash 后） | 420 | 4 | `test_performance_history_is_declared_as_historical_only`、`test_class_size_does_not_grow`、`test_nesting_does_not_grow`、`test_bare_json_load_debt_is_a_nonincreasing_subset` |
| 本轮改后 | 420 | 4 | **完全相同** |

差异集合：新增 = 空；消除 = 空。

环境缺口证据（与本轮改动无关）：
- `程序/维护记录/基准历史.json` 在 worktree **不存在**，主树存在 → `test_performance_history_*` 报 `FileNotFoundError`。
- `程序/skills/00全流程SKILL/AIGC创作全流程` 是 git submodule，worktree 内未初始化（空目录），
  AST 扫描混入后触发 `test_class_size_does_not_grow` / `test_nesting_does_not_grow` /
  `test_bare_json_load_debt_*`。已按既有做法从主树补齐该子模块内容（159 个文件，排除 `.git`），
  补齐后定向门禁内所有依赖 SKILL 的用例转为通过（`workflow_settings.freeze_skills` 不再报引用缺失）。

## 未完成 / 如实声明

- **未运行全量 `--all --safe`**：本轮只改一个 L2 模块与对应测试，未命中 §5 的全量触发条件
  （启动路径 / Tk 控件生命周期 / 删除语义 / 层级登记表均未动）。
- **未做真实用户项目实测**：所有数字来自合成项目上的微基准；`page.paint.script` 在空壳项目上
  实测 223–236 ms，未在真实项目副本上复测（真实项目需用户数据，未触碰）。
- **剩余热点已如实登记、本轮未改**：改后 `read_text` 占 42.4%（961 次），即「与内部草稿逐字
  去重」。若要继续提速，应改该去重策略（尺寸/摘要短路），属另一轮范围。
- 已提交：内容提交 `99708e21`；同轮清理误入快照提交 `373fefc9`（分支 `codex/wip-R2518`，rebase 到 master `3a257fa0`）。

## 结论

剧本准备页「响应速度慢」的当前根因是 **文件发现路径上逐文件的 `Path.resolve()`**（占发现耗时
53.5%），已用「只对符号链接做越界 resolve」的最小改动消除，同条件实测 `discover_script_documents`
**536.1 ms → 309.1 ms（−42.4%）**；定向门禁 9/9、0 红，架构门禁与基线完全一致（0 新增红）。
