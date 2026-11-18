# R3286 结果：L0 契约层任务书轮 4A — D4 产物版本契约 ＋ D5 事件总线协议（契约轮，L0 only）
<!-- round-evidence: {"commit_base": "e7796e68", "credential_hits": 0, "evidence_sha256": "0c11ae573917d883", "exit": 0, "failed": 0, "passed": 85, "round": 3286, "tests": "run_selftests.py -k artifact_schema pet_bus"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 契约轮（任务书轮 4A：D4＋D5 的 L0 部分；只动 `contract/artifact_schema.py`、`contract/pet_bus.py` 与对应测试，不接线业务——D4-c/d/e、D5-d 属轮 4B）。
2. **测试跑了吗、三个基线过了吗？**
   - 先红后绿：新测试对改前代码实测 **70 条用例 → 3 failures＋30 errors**（`classify`/`STEPS`/`migrate_file`/`TERMINAL_EVENTS`/`emit_status`/`_write` 保护全部缺位）；实现后同组 70 条全绿。
   - 定向自检：`run_selftests.py -k artifact_schema pet_bus event_bus` → 89 条用例 0 红；`-k artifact pet_bus file_cache` → 123 条用例 0 红（含 `test_artifact_lineage`、`test_file_cache`）。
   - `smoke_test.py --affected artifact_schema pet_bus` → 10/10 项通过（消费者全量 38 个测试文件 259 秒 0 红）；默认 `smoke_test.py` → 9/9。
   - 变异抽样：`scripts/mutation_sample.py` → 8/8 位点杀死（含本轮把 migrate 位点改指 `while current < target:` 边界）。
   - 分支覆盖率基线：工具真实重测刷新（90 模块 1330/2523 决策点，1512 条目标用例全绿）；`artifact_schema.py` 77.5%（下限 76.0）、`contract/pet_bus.py` 51.7%（下限 37.0），均过棘轮。
   - 全量：`run_selftests.py --all --safe --allow-dirty-diagnostic` → 8552 条用例／784.4 秒，10 文件红 16 条，**本改动文件零红**（红项全部为既有环境/状态欠账，§5）；`[NO_RECEIPT]` 仅诊断不记账（净树＋状态页滞后使绿凭据结构性不可得，同 R3267/R3280 口径）。
   - 架构门禁：`smoke_test.py --architecture` → 502 条，failures=1／errors=2（唯一 FAIL `test_round_number_continuous`＝状态页 3234 滞后，工作树分支固有欠账；2 条 ERROR 为覆盖率工具子进程 GBK 解码环境假红，`PYTHONIOENCODING=utf-8` 下复跑全绿，R3267/R3280 同口径）。
3. **欠账少了吗？** 少了任务书 D4-a/b、D5-a/b/c 六项契约缺口；轮 4B 的属主读取点接线、终态事件调用方传 `run=`、`emit_status` 消费方改造按计划留到下一轮，不算本轮欠账。

---

## 1. 改动清单

| 文件 | 改动 |
| --- | --- |
| `程序/contract/artifact_schema.py` | D4 主体（267 行）：① `CLASSIFICATIONS` 五态闭集＋`classify(kind, payload)`——只读、不抛异常、不改数据；`current` 须 `schema_version` 在场且等于登记版本，旧键 `version` 即便同号也算 `legacy`（缺新键，下次正常写入顺带补，G8）；`missing` 无任何版本字段（含 `schema_version: None`）；`future` 高于登记版本；`invalid` 非对象／未登记 kind／版本值不可解析（bool、浮点、非数字串）。② `stamp()` 拒绝 `version > 登记版本`（`ValueError`），不高于登记版本照常写。③ `STEPS = {}` 版本阶梯登记表（kind→{目标版: 纯函数}，现有产物全在 v1 暂无阶梯）；`migrate()` 改走阶梯：从 `classify` 定态，`future`/`invalid` 不抬升只进动作清单，缺某一级或步骤抛异常返回 `(原副本, problems)` 不抛 `KeyError`、版本号不前进；无版本字段按第 1 版走完整阶梯。④ `migrate_file(kind, path, *, publish, read)`＝§3c-2 InvokeAI 式落盘：`.bak` 备份 → 调用方注入的 `publish` → `read` 读回 `classify=='current'` 断言 → 失败 `_restore_backup` 回滚；status 闭集 `written`/`skipped`/`failed`；`.bak` 成功后保留。`validate()` 行为不变。 |
| `程序/contract/pet_bus.py` | D5 主体：① `TERMINAL_EVENTS` 常量清单（`STAGE_EVENTS`＋`script.completed`/`delivery.ready`/三个 `*.task.failed`）；② `event(kind, key=None, run=None, **payload)` 新增 `run` 形参——只对终态事件生效：进负载并参与 `identify` 幂等键，同 run 重复仍去重、跨 run 同文各自送达；非终态事件忽略 `run`；`at` 永不进键。③ `publish` 拆出 `_publish(item) -> 'queued'/'suppressed'`，返回值不变；④ 新增 `Bus.emit_status(kind, **payload) -> (status, item)`（H3 闭集 `delivered`/`suppressed`/`failed`，构造失败不抛）；⑤ `_write` 包 `try/except OSError` → `_note_error('journal.write', …)` 有界环形，`_deliver` 照常；`_record_error`/`_diagnose` 共用 `_note_error`，订阅者异常计数口径不变。 |
| `程序/pet_bus.py` | 顶层兼容门面补导出 `TERMINAL_EVENTS`（其余名字原样转发）。 |
| `程序/tests/test_artifact_schema.py` | +19 个用例 5 个测试类：`ClassifyTests`（五态逐项＋只读不抛不改）、`_LadderKind` 临时三版登记、`StepsLadderTests`（1→3 全阶梯、中途起步只跑余级、缺步 problems 不抛、中途步骤异常、future 不抬升、无版本走全梯、classify 阶梯态跟踪）、`StampBoundaryTests`（越界拒、登记版与更低版收）、`MigrateFileTests`（.bak 留旧版、current/future/缺步跳过不写盘、publish 失败回滚、读回断言失败回滚、非对象跳过）。 |
| `程序/tests/test_pet_bus.py` | +5 个测试类 16 个用例：`RunKeyedIdentityTests`（run 改键、同 run 同键、不传 run 行为不变、进度类忽略 run、终态清单断言）、`RunKeyedDeliveryTests`（同文异 run 两条送达、无 run 重复仍去重、_queued 背压不削弱、publish/emit 返回值不变）、`JournalFailureTests`（OSError 仍送达＋`journal.write` 入 errors、error_limit 有界）、`EmitStatusTests`（delivered/suppressed×2/failed×2、emit_safe 返回不变）。 |
| `程序/scripts/mutation_sample.py` | migrate 位点原文 `elif current != item['version']:` 已不存在，改指新阶梯边界 `while current < target:` → `<=`（实测杀死）。 |
| `程序/architecture.md` | L0 行 `artifact_schema` 契约描述同步五态/阶梯/migrate_file（R3286 标注）。 |
| `程序/说明/持久化产物版本清单.md` | 约定节同步 classify/STEPS/migrate_file；顺手修正权威路径 `程序/artifact_schema.py` → `程序/contract/artifact_schema.py`（实体早已入包，本文件原写错）。 |
| `程序/维护记录/分支覆盖率基线.json` | 工具真实重测刷新：决策点口径随新分支更新（artifact_schema 18→40 点、pet_bus 23→29 点），90 模块 1512 条目标用例全绿。 |

## 2. 验证输出摘要

- 先红：改前代码跑新测试 `unittest tests.test_artifact_schema tests.test_pet_bus` → `Ran 70 tests`，`FAILED (failures=3, errors=30)`（缺 `classify`/`STEPS`/`migrate_file`/`TERMINAL_EVENTS`/`emit_status`；旧 `event(**payload)` 会把 `run` 当普通负载进键，进度类去重口径不同）。
- 改后：同组 `Ran 70 tests OK`；`run_selftests.py -k artifact_schema pet_bus event_bus` → 89 条 0 红 5.5s；`-k artifact pet_bus file_cache` → 123 条 0 红 1.3s。
- `smoke_test.py --affected artifact_schema pet_bus` → 10/10（内含 38 个消费者测试文件定向回归 259s 0 红）；`smoke_test.py` → 9/9。
- `scripts/mutation_sample.py` → 杀死 8 / 存活 0 / 错误 0。
- 分支覆盖率：`artifact_schema.py` 31/40＝77.5%（下限 76.0）、`pet_bus.py` 15/29＝51.7%（下限 37.0）；基线 JSON 已由工具重写。
- 全量 `--all --safe --allow-dirty-diagnostic`：8552 条用例／784.4 秒，10 文件红 16 条——`architecture.test_round_baselines`×1（状态页轮次滞后）＋GBK 子进程解码族 12 条（`test_git_hooks`×6、`test_archive_results`、`test_lane_merge_queue`、`test_merge_round`、`test_round_claim`、`test_storyboard_catalog_scan_count`×2、`test_worktree_ledger`，均 `subprocess` stderr/stdout 为 None 或 GBK 解码错）＋GUI 环境抖动 2 条（`test_model_manager_actions` 窗高 1061<1227、`test_ui_edges_tables` 滚动 212≠248；串行复跑同红，运行期有其他 PID 持 GUI 令牌，R3280 同两条）。红项与本改动零交集：本轮只动 L0 契约＋其测试＋文档＋基线 JSON，不触 UI/git 钩子/子进程路径。
- `smoke_test.py --architecture`：502 条，failures=1／errors=2；2 条 ERROR 定位为 `scripts/branch_coverage_report.py`／`coverage_report.py` 子进程在 GBK 控制台输出中文汇总行、父进程按 UTF-8 解码致 reader 线程崩、`stdout=None`——`PYTHONIOENCODING=utf-8` 复跑两条全绿，属环境假红非本改动回归。

## 3. 小决策（任务书未覆盖处）

- **`classify` 对「旧键同号」判 `legacy`**：`{'version': 1}` 在登记版为 1 时无 `schema_version`，仍属 legacy——它确实缺新键，下一次正常写入经 `stamp()` 顺带补写（G8「只加键不删数据」口径）；若判 current 会让 `migrate_file` 跳过补写，旧键永远残留。
- **`migrate()` 返回 `(副本, actions)` 沿用旧签名**：旧实现即此形状，消费者（若有）不破；缺步/步骤失败把问题写进 actions 并返回**原始副本**（版本号不前进），由调用方决定是否落盘——落盘与否统一收口在 `migrate_file`。
- **`migrate_file` 的 `publish`/`read` 注入而非直接 import**：L0 不得反向依赖 L1 `file_cache`／`agent.core`；生产侧接线（属主写路径调用）属轮 4B，本轮只交付契约与用 `json` 读写的测试替身验证语义。
- **`emit_status` 构造失败也返回三元组**：`event()` 的 `ValueError`/`TypeError` 一律归 `failed`、`item=None`，保证「只让确需区分的调用方改用」时不引入新异常面；`emit`/`publish`/`emit_safe` 路径不变。
- **`run` 只对 `TERMINAL_EVENTS` 生效**：任务书只点名终态事件；进度/实时类传 `run` 直接忽略（不进负载不进键），避免 G7 之外的去重口径漂移。`key=` 显式键仍最高优先，`run` 不覆盖它。
- **`_write` 失败记 `journal.write`、`_diagnose` 失败记 `journal.error`**：两类基础设施异常只进有界环形、不占 `errors_total`（该计数只管订阅者异常，口径不变）。
- **门面补 `TERMINAL_EVENTS`**：`程序/pet_bus.py` 是测试与未改写消费方的扁平入口，新常量必须同口径可达；未新增 `def`、未改既有转发。
- **`AGENTS.md` §2.2 未改**：原文「新写入写 `schema_version`，读取侧容忍缺版本」仍准确；本轮未新增 §2.3 硬约束（规则 26 不触发），且文件距 16KB 上限仅约 420B，不值得为描述性细节冒改约束表的风险。
- **轮次号**：领号得 **3286**。

## 4. 架构门禁失败集合（改后）

`smoke_test.py --architecture`：502 条，failures=1／errors=2。

| 用例 | 结果 | 归因 |
| --- | --- | --- |
| `test_round_baselines…test_round_number_continuous` | FAIL | `project_status.md` 当前轮次 3234 vs 最新结果+1＝3287；状态页只在 master 更新，工作树分支固有滞后（R3246/R3259/R3267/R3280 同项） |
| `test_branch_coverage_floor…test_branch_coverage_tool_runs_on_bundled_interpreter` | ERROR | 覆盖率工具子进程 GBK 输出 vs 父进程 UTF-8 解码，`stdout=None`；`PYTHONIOENCODING=utf-8` 复跑绿 |
| `test_coverage_baseline…test_coverage_tool_runs_on_bundled_interpreter` | ERROR | 同上 |

改前对比：R3280 同门禁 502 条 failures=1／errors=0（其环境带 `PYTHONIOENCODING`）；本轮 failures 集合不变、errors 为同源环境假红（R3267 曾记 failures=1／errors=2 同项）。本轮未增删架构测试、未动 `_layers.py` 登记，门禁总数 502 与改前一致。

## 5. 欠账与边界

- **留给轮 4B**：`REGISTRY` 各 owner 读取点调 `classify`、G8 处置（legacy/missing 只计数、future 拒写＋【警告】）、写方改 `stamp()` 双键、终态事件调用方传 `run=`、`emit_status` 消费方改造。本轮按任务书不接线。
- **`STEPS` 现为空表**：全部已登记产物在 v1，无真实阶梯可迁；阶梯语义由测试内临时登记的三版 kind 验证。首个真实版本升级落地时按级补 `STEPS[kind][n]`。
- **`migrate_file` 暂无生产调用方**：属主写路径接入属轮 4B；本轮契约＋注入式 IO 已由 `MigrateFileTests` 覆盖。
- **既有欠账未动**：`pet_bus.py` 顶层门面待「门面清除轮」统一改写后删除；`test_round_number_continuous` 状态页滞后为分支固有。
- **未运行项**：无。任务书三条命令（`-k artifact_schema pet_bus event_bus`、`smoke_test.py`、`--all --safe`）与用户追加的 `smoke_test.py --architecture`、`-k artifact pet_bus file_cache`、`--affected`、变异抽样、分支覆盖率重测均已实跑，结果如上。
