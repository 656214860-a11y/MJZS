# R1783：架构棘轮补强与审计记录（整理轮）

1. 本轮类型：§3.3 整理轮（只动门禁与文档，不改产品代码）。来源：对源码做的五维只读审计中，凡当场不适合重构的项，改为「冻结当前值、只许下降」，防止继续恶化；真正的重构另起各轮。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k architecture distribution`：398 条，1 个文件有红（见「未通过项」，非本批引入）。
   - 默认冒烟通过。
   - 完整安全全量：本轮只改门禁与文档，不要求补跑；合入 master 后随累计欠账一并补跑。

3. project_status.md 欠账少了吗：本轮改源码 +0；改门禁测试 +6。

## 改动

- `tests/architecture/test_complexity_ratchet.py`（新增，4 条）：嵌套深度 ≥6（19 个函数，最深 `pet_ui.click` 10 层）、参数 >7 个（52 个函数）、类 >600 行（14 个，最大 `pet_cloud.Cloud` 1524 行）三类各冻结当前值，只许下降、不许新增；降到线内必须从登记表删除。`architecture.md` 的架构门禁清单同步登记。
- `tests/architecture/_scan.py`＋`test_no_circular_import.py`＋`test_layers.py`：此前静态 import 扫描看不到 `import_module('x')` / `__import__('x')` 字面量，`white_model`↔`white_model_ref` 等 4 组环和 5 条向上依赖被绕开。新增 `dynamic_import_rows`，把现有的动态环（`KNOWN_DYNAMIC_CYCLES`）与动态向上依赖（`KNOWN_DYNAMIC_UPWARD`）按棘轮冻结，新增即红、清掉即要从台账删除。
- `tests/architecture/test_token_boundary.py`：hex 基线 46→41、padx/pady 基线 199→62 按实测收紧；新增 `LAYOUT_NUMBER_BASELINE`（`width/height/wraplength` 数字字面量，不含 0、1；39 个文件 132 处）冻结，并附谓词金丝雀用例。
- `tests/architecture/test_function_size_ratchet.py`：登记值全部收紧到实测值（只降不升）。
- `distribution_manifest.md`：声明根目录 `BLOCKED_ISSUES.md` 为开发资料，不随分发包。
- `BLOCKED_ISSUES.md`（新增，仓库根）：审计后「实测不成立」「需单独一轮处理」「已接受的信任边界」「已加棘轮、重构另起一轮」各项及原因。

## 未通过项

- `architecture.test_round_baselines.test_round_number_continuous`：状态页轮次头是 1776，最新结果文件已是 R1783，要求头＝最新结果＋1。`project_status.md` 只允许 master 提交（规则 41），合入 master 后单独补一次；分支上此项预期为红，非本批引入。

## 提交

- 已在分支 `claude/project-handoff-f6eb50` 提交，commit hash 见 git log `R1783:`。
