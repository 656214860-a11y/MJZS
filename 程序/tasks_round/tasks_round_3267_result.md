# R3267 结果：L0 契约层任务书轮 3A — D3 契约轮（Severity／Diagnostic／StartupPhase＋注入式自检＋错误码 severity/analyze）
<!-- round-evidence: {"commit_base": "f8b33714", "credential_hits": 0, "evidence_sha256": "a960f0d8871ffea4", "exit": 0, "failed": 0, "passed": 27, "round": 3267, "tests": "run_selftests.py -k test_selfcheck test_error_codes"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.4 契约轮（任务书轮 3A：D3-a～D3-f，Q12 最小规模，只动 `contract/` 与测试/登记/文档；启动接线属轮 3B，本轮不做）。
2. **测试跑了吗、三个基线过了吗？**
   - 定向自检：`run_selftests.py -k test_selfcheck error_codes` → 27 条全绿（`test_selfcheck` 16、`test_error_codes` 11）。
   - 默认冒烟：`smoke_test.py` → 通过 9 项／失败 0。
   - 架构门禁：`smoke_test.py --architecture` → 502 条，failures=1／errors=2（明细 §4）；失败集合较 R3259（failures=2／errors=2）少 1 条且零新增——`test_whitelist_versions` 已由 R3263 合入 master 修复，本轮新增模块零违规。
   - 全量：`run_selftests.py --all --safe --allow-dirty-diagnostic` → 8476 条／788.3 秒，9 个文件红共 16 条用例、5 条登记 skip；红项全部可归因既有环境/状态欠账与本树草稿文件，**与本次改动零交集**（明细 §5）。
3. **欠账少了吗？** 少了任务书 D3-a～D3-f 六项：L0 启动诊断类型、注入式自检运行器与两个 L0 内建甲类检查、错误码 severity＋analyze 派发链、测试与登记文档同步。D3-g～D3-n（启动接线、L1 检查项、崩溃预算、fail-open 开关）属轮 3B；D4 起后续轮次不变。

---

## 1. 改动清单

| 文件 | 改动 |
| --- | --- |
| `程序/contract/diagnostics.py` | 新建 L0：`Severity`（`FATAL`/`ERROR`/`WARN`/`DEGRADED` 闭集，D3-a）；`StartupPhase`（`CONTRACT`/`CONFIG`/`RESOURCE`/`UI_SHELL`/`READY`）；`Diagnostic` 冻结 dataclass（`severity`/`scope`/`code`/`message`/`remedy`/`escape_hint`，§3c-1 含逃生通道；`code` 为固定闭集类别码即 kind；`severity` 收字符串归一枚举、非法值 `ValueError`）。仅标准库。 |
| `程序/contract/selfcheck.py` | 新建 L0：`run(checks) -> list[Diagnostic]` 注入式运行器（G3/Q12）；检查契约 `None`/`Diagnostic`/`Diagnostic` 序列，返回值形状非法或检查自身抛异常均记一条 DEGRADED `check-error`（G5，永不升级 FATAL、不中断其余检查，§3b-1 同旨）；`default_checks()` 供 L0 自带两项甲类检查：`_stage_contract_check`（`stage_layout.stage_contract_errors()` 不一致→FATAL）与 `_artifact_registry_check`（`artifact_schema.REGISTRY` 每项须为含 `version`/`required`/`owner` 的自洽对象→FATAL）。函数内惰性 import 仅限 `contract.*`，无向上依赖；不扫描目录、不联网、不读用户项目。 |
| `程序/contract/error_codes.py` | `SEVERITIES` 闭集（`fatal`/`degraded`/`recoverable`/`info`，§3b-1）；`ErrorCode` 增 `severity` 字段（第二位置参数）＋`__post_init__` 校验，16 个既有码逐一补级、**不删任何码**（D3-d）；新增 `analyze(failure, analyzers)`：按序遍历、首个非 `None` 结果胜出、analyzer 异常吞掉继续、全落空回退 `lookup('E-UNKNOWN')`，原始 `failure` 不被吞没。 |
| `程序/tests/test_selfcheck.py` | 新建 16 条：枚举闭集与序位、`Diagnostic` 全字段含 `escape_hint` 与 severity 归一/拒绝、`run()` 空/单条/多条/生成器/乱序收集、检查异常→DEGRADED 且不升级 FATAL 不中断、返回值形状非法→DEGRADED、无 `__name__` 可调用对象兜底命名、`default_checks()` 健康树空列表与阶段契约/产物登记四类不一致→FATAL、与外来注入检查混排。 |
| `程序/tests/test_error_codes.py` | +5 条（共 11）：`SEVERITIES` 闭集、severity 抽查值、非法 severity 拒绝、`analyze` 首中/跳过 None/空表回退、analyzer 抛异常被吞且原始 failure 保留。 |
| `程序/tests/architecture/_layers.py` | `_register(0, "diagnostics", "selfcheck")`（R3267 注释：纯 L0 契约，检查函数由上层注入，G3）。 |
| `程序/architecture.md` | §3 分层表 L0 行补 `diagnostics`/`selfcheck` 条目与权威说明；新增 R3267 段落记 D3 口径。 |
| `程序/PROJECT_MAP.md` | 「模型与安全」行补 `contract/diagnostics.py`、`contract/selfcheck.py`，并记 `error_codes` severity/`analyze()`（R3267 起）。 |
| `程序/AGENTS.md` | §2.2 权威表新增「启动诊断与自检」行（指向三模块）；为守 16KB 预算同步精简：§4 删除与 §5 重复的 Tk 隐藏桌面句（§5 为唯一权威表述）、§6 删分母派生括注、该行压缩——净 15964B ≤ 16000B（详见 §3）。 |
| `程序/runbook.md` | §11 覆盖率口径同步：模块总数 654→656、未覆盖 579→581、L0/L1 实体 88→90。 |
| `程序/维护记录/覆盖率基线.json` | 重测刷新：`modules_total` 656、`modules_covered` 75、9 组定向用例全绿。 |
| `程序/维护记录/分支覆盖率基线.json` | 重测刷新：90 个 L0/L1 实体、1275/2440 决策点、80 组定向用例（含新增 `tests.test_selfcheck`）全绿。 |
| `程序/维护记录/分支覆盖率下限.json` | 新增 `diagnostics.py: 100.0`、`selfcheck.py: 100.0`（实测 0 决策点/13 决策点全覆盖）；`error_codes.py` 维持 100.0 下限且实测回到 100%（7/7）。 |

## 2. 验证输出摘要

- `run_selftests.py -k test_selfcheck error_codes`：27 条，0 失败 0 错误 0 跳过（末次定向复跑；此前一轮 46 条含 `stage_layout` 亦全绿）。
- 分支覆盖实测：`selfcheck.py` 13/13=100%、`error_codes.py` 7/7=100%、`diagnostics.py` 0 决策点=100%。
- `smoke_test.py`：9/9。
- `smoke_test.py --architecture`：502 条，failures=1／errors=2（§4）。
- `run_selftests.py --all --safe --allow-dirty-diagnostic`：8476 条用例／788.3 秒；9 个文件红（16 条用例），5 条登记 skip；`[NO_RECEIPT]` 仅诊断不记账。红项归因：① `test_distribution_selfcheck` 2 条＝工作树根 `_d2_sim.py` 未跟踪草稿未入分发清单——已按 runbook 脏树协议 rescue 到 common-dir 后删除，定向复跑 `test_distribution_selfcheck`＋`test_archive_results` 7/7 绿；② `test_git_hooks` 6＋`test_round_claim`/`test_merge_round`/`test_lane_merge_queue`/`test_storyboard_catalog_scan_count`/`test_worktree_ledger`/`test_archive_results` 共 13 条＝git/子进程 `text=True` 捕获遇 GBK 输出解码崩（`stdout/stderr=None`），与架构门禁两个覆盖率工具 ERROR 同族的既有环境欠账，且呈抖动性（`test_archive_results` 单独复跑即绿）；③ `architecture.test_round_baselines.test_round_number_continuous` 1 条＝状态页 3234 滞后。**本次改动文件（contract/diagnostics/selfcheck/error_codes 及其测试）零红**。

## 3. 小决策（任务书未覆盖处）

- **`Diagnostic.code` 即 kind 闭集**：任务书 §3c-1 要求「`kind` 用固定闭集枚举」，字段清单（D3-a/附录）落为 `code`——产出方在各自模块内登记类别码（本模块 `stage-contract`/`artifact-registry`/`check-error`），不收自由文本；测试以行为断言守住。
- **检查返回值契约收紧**：`run()` 除「检查抛异常」（G5 明文）外，把「返回值不是 None/Diagnostic/Diagnostic 序列」同样记 DEGRADED——诊断器输出形状错误与检查崩溃同害，不升级不静默。
- **AGENTS.md 预算处置**：新增权威行使文件 15973→16279B 越过 16000B 预算（架构门禁当场转红）。按文件头「新增规则前先删旧规则，细则写 runbook」处理：权威行压缩至指针级；§4 的 Tk 隐藏桌面句与 §5 逐字重复义务删除（§5 保留完整口径）；§6 分母派生括注属实现细节删除。净 15964B，门禁复绿，未删任何规则条目。
- **轮次号**：领号得 **3267**（3265/3266 租约已被他树持有）；文档内预写的 R3265 字样同步更正为 R3267。

## 4. 架构门禁失败集合（改前后对比）

`smoke_test.py --architecture` 改后：502 条，failures=1／errors=2。

| 用例 | 结果 | 归因 |
| --- | --- | --- |
| `test_round_baselines…test_round_number_continuous` | FAIL | `project_status.md` 当前轮次 3234 vs 最新结果+1；状态页只在 master 更新，工作树分支固有滞后（R3246/R3259 已记录同项） |
| `test_branch_coverage_floor…test_branch_coverage_tool_runs_on_bundled_interpreter` | ERROR | 测试子进程 `text=True` 无 encoding，工具输出 GBK 字节触发 UnicodeDecodeError（既有环境欠账） |
| `test_coverage_baseline…test_coverage_tool_runs_on_bundled_interpreter` | ERROR | 同上 |

对比 R3259 基线（failures=2／errors=2，488 条）：`test_whitelist_versions` FAIL 已由 R3263 合入 master 修复消失；条数 488→502 系 R3263 合并带入的新增架构用例。**本改动零新增违规**：`diagnostics`/`selfcheck` 登记 L0 后 `test_layers` 全绿，L0 无新增向上 import（两模块仅 import 标准库与 `contract.*`）。

## 5. 遗留欠账

- **轮 3B（D3-g～D3-n）**：L1 乙类检查项、启动器接线（FATAL→MessageBox 拦截／DEGRADED 暂存播报）、`desktop_launcher` 复用、`diagnostic_capture` 崩溃预算、`data/selfcheck_failopen.flag`、三虎 DEGRADED 出口、规则 33 零递归扫描与耗时预算测试——按任务书属下一轮，本轮未动。
- **全量凭据结构性欠账**：`--all --safe` 绿凭据绑定 `HEAD:程序` 内容树且要求净树；工作树 `project_status.md` 滞后（3234）使 `test_round_number_continuous` 必红，任何工作树分支都产不出绿凭据——与 R3246/R3259 同口径，层级登记表改动按 §5 约定「合入 master 前触发当次全量」，留待合入轮由 auto_full_safe/post-commit 补跑。本轮已用 `--allow-dirty-diagnostic` 拿到真实全量证据（8476 条），未产生也不冒充绿凭据。
- **环境性门禁欠账（扩大实证）**：全量诊断档暴露 GBK 子进程解码崩影响 7 个测试文件共 13 条用例（`test_git_hooks`/`test_round_claim`/`test_merge_round`/`test_lane_merge_queue`/`test_storyboard_catalog_scan_count`/`test_worktree_ledger`/`test_archive_results`），与既有 2 条覆盖率工具 ERROR 同根因（子进程 `text=True` 未指定 encoding，git 输出 GBK）；在 auto-ci 环境（R3258 凭据 8495 条 0 红）不复现，属本机手动跑环境差异，建议主区统一子进程 encoding 口径后复测。
- **环境性门禁欠账**：两个覆盖率工具子进程 GBK 解码 ERROR、状态页轮次滞后 FAIL 均为既有项（R3246 起记录），建议主区择机处理。
- `_d2_sim.py`（D2-0 测量草稿）已按 runbook 脏树处置协议 rescue 至 `<git common-dir>/rescue/dsh-5158b800-34ae/` 后从工作树删除，不再产生分发清单红项。
- 任务书 §8「轮 3A」勾选框未勾：R3259 对已完成的轮 2 同样未勾，验收总清单留待任务完成文件统一核销。

## 6. 提交

- 领号：R3267（`round_claim.py next`，租约属本工作树 `dsh-5158b800-34ae`／`codex/wip-R3259`）。
- commit：`R3267: …`（hash 见 git log；`round_evidence` 自动盖 `tasks_round/evidence/R3267.json` 并回填本文件机器头）。
- 本轮由前序会话完成主体实现（diagnostics/selfcheck/error_codes/测试/登记/基线），本次接手复核全部 diff、修复 AGENTS.md 预算回归、补跑架构门禁与覆盖率基线并收尾。
