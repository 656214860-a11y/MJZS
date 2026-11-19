# R3419 — A9 首批静态包子模块导入扫描收口
<!-- round-evidence: {"commit_base": "e6bfbec3", "credential_hits": 0, "evidence_sha256": "0a3136dd5b702f49", "exit": 0, "failed": 0, "passed": 24, "round": 3419, "tests": "run_selftests.py -k test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行轮；授权来源《六层架构收口与企业级演进任务书》A9、R3411 C/G/H/I/J/K、R3416 C/F/H/J。只实施本子批，不宣称 A9 或任务书整体完成。
2. 测试：先红后绿；定向 24/24、默认冒烟核心基线 8/8＋隐藏桌面探针 1/1（包含在 --affected 的 10/10 中）；完整架构 539/542→542/545，均为同一 2 failures＋1 error，无新增失败。安全全量未运行，历史欠账未清零。
3. 欠账：只收口静态 from-import/相对导入漏边；完整身份与分类、动态注册等仍归后续 A9。没有改变生产依赖或扩大任何豁免。

## A. 基线、领号与范围
- 基线 e6bfbec31bf774a10c9f1079ec59471e5135147f，已含 A4/A6/A7/A8。初始树干净、detached HEAD；建立 `codex/architecture-a9-scan` 后用 `round_claim.py next` 领取 R3419。初次领号退出 0，但一个子进程读取线程报 GBK 解码错误；返回编号 3419，后续统一 PYTHONUTF8=1/PYTHONIOENCODING=utf-8，不重复领号。
- 允许模块共 3 个：`tests/architecture/_scan.py`、`tests/architecture/test_layers.py`、`architecture.md`。结果及自动 evidence 属轮次留痕。没有新增测试模块、硬规则编号、层级登记或生成索引条目。
- 未发现本 A9 子批专属队列 ID，不认领其他车道的任务。未改 master、未推送、未复制私有数据。
- `dev.py scope`：95 个其他活跃分支中 25 个报告重叠（15 个仅 architecture.md，10 个另含 _scan.py）；其余 70 个无重叠。L0/L1/L2/foundation 相关车道没有本批扫描器或 test_layers 的等价改动；旧分支扫描器最后相关提交为历史扫描范围调整，非本次 from-import 修复。架构说明仅在 §3 新增本轮扫描边界段，不覆盖其他车道登记表。

## B. 在途等价交付核对
- L0 `codex/l0-constitution` = 0e3fc763：HEAD 对该分支 15/0；K9 纯度门禁与 K2 动态豁免已在本树，复用不重写。
- L1 `codex/l1-enterprise` = ea9f94ed：HEAD 对该分支 20/3；R3396/I1 关系规范和 R3401/I3 的 adapter 上移、注入解耦、18→15 豁免仍在途。其 _layers 登记不可视为已合入，本批不代改。
- L2 `codex/l2-maturity-taskbook` = 4d00aee4：HEAD 对该分支 20/5；R3410/R3417 操作上下文与取消发布/stdlib 闭包仍在途。本批不接管其生产模块。
- foundation-hardening = b6ed0cf6：HEAD 对该分支 33/19；未知窗口拒发/测试欠账仍归原 owner。其他 foundation scope 重叠为共享 architecture.md 文本，不是本子批解析器等价交付。
- 因完整 H01 身份迁移还会涉及 _layers、环守卫、登记/生成视图、包初始化与未知项处置，无法与 H03/H09 在 3 模块内安全完成。本批仅修现有静态解析路径，保留既有扁平棘轮身份；后续输入见 F。

## C. 改前负例
在临时包树调用真实 `test_layers._upward_pairs()`，扫描 ROOT/候选源与层级图由 fixture 注入；不执行被扫描模块。7 个最小样本中 5 个失败、2 个既有回归对照通过，exit1：
```text
canaries=7 failures=5
contract/client.py: from ui import high as view -> []
contract/client.py: from . import high -> []
contract/nested/client.py: from .. import high -> []
contract/client.py: def load(): from ui import high -> []
contract/client.py: try: from ui import high -> []
```
每例期望越层边 `('client.py', 'client', 'high')`；旧实现只有 `node.module` 且没有解析子模块别名。`from .high import Marker` 和 `from ..high import Marker` 原本可按 stem 命中，作为保留对照，不谎称全部相对导入失效。

## D. 实现与验证
### 实施边界
- `_scan._from_module()` 按源文件包解析相对前缀，越过顶层的非法相对导入报错；`resolved_module_import_rows()` 从 AST 保留包边并识别本地子模块，保留行号/原实体名，不 import 被扫描代码、不把导出符号或 as 名当模块。
- 实际消费者 `test_layers._upward_pairs()` 与附件服务分层检查接入增强解析；新增 3 个 canary 测试方法，旧断言未删改。`architecture.md` §3 原位注明已覆盖与未覆盖边界。静态豁免仍 18、动态仍 2，无新键/阈值调整。
- **首次消费者回归发现实际环**：初版将增强解析直接放入共享 `module_import_rows()`，24 条中 2 条失败（`test_no_circular_import.py` 的静态与含动态两项），命中 A1 已知五模块环 api_endpoints/diagnostic_capture/model_metering/model_pool/request_ledger。新增可见边为 `infra/model_metering.py:20 → diagnostic_capture`、`infra/request_ledger.py:146 → diagnostic_capture`。
- 按 R3411 J「先影子差异、先修额外真缺陷再切强制」，将增强解析限定在分层消费者：现有 `module_import_rows()`/环消费者保持原行为，后续须先接 L1 拆环再迁移。没有将真环加入 `KNOWN_*`，不把本批绿色定向结果说成完整导入图已绿。

### 负例、重试与适用验证
环境：已核实的随附 Python 3.14.7，程序 cwd，PYTHONUTF8=1/PYTHONIOENCODING=utf-8；本树缺解释器，仅借用既有可执行文件，没有复制运行数据。
1. C 的临时旧实现探针：7 样本/5 漏报，exit1。随后在旧扫描实现上运行永久 `python -B -m unittest tests.architecture.test_layers.PackageImportCanaryTests`：3 方法/10 个失败（含 subTest），exit1；关键输出 `AssertionError: AssertionError not raised`（5 个坏依赖）、`'low' not found`（4 个正例要求的真实边）、`(2, 'high') not found`（别名行号）。不是缺 API 引起的红灯。
2. 初版共享解析的定向首次运行：`python -B -m unittest tests.architecture.test_layers tests.architecture.test_no_circular_import tests.architecture.test_gate_selfaudit tests.architecture.test_rule_guard_map`，24 条/2 失败，13.341 秒，exit1；上述五模块环是真实新覆盖缺陷。调整到分层专用入口后原命令 24/24，13.698 秒，0 skip、exit0。包含全部增强解析消费者、原环消费者、自审与生成规则索引一致性。
3. 冒烟首次用了 `--affected architecture.test_layers architecture.test_no_circular_import architecture.test_gate_selfaudit architecture.test_rule_guard_map`；解析器按 `architecture` 导入额外选择 `test_skills`，执行架构子集后等待其他树 GUI 令牌。中断本次多选运行（exit1，无完整通过数），核实本树隐藏子进程已退出；未停止占用者。改用精确 `python -B smoke_test.py --affected test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map`：仅 4 文件，24/24、0 skip、exit0；9 项默认冒烟检查（含自动隐藏桌面探针）＋1 项定向门禁合计 10/10。未手动添加不支持的 --probe 参数。
4. 完整架构：改前 `python -B smoke_test.py --architecture` 542 条、2 failures＋1 error，260.234 秒、exit1；改后 545 条、同一 2 failures＋1 error，244.538 秒、exit1。通过数 539→542，新增 3 个 canary 方法全通过；失败测试 ID 集合完全相等（下节三项），没有新增架构回归。没有新增测试模块，架构清单集合仍一致；规则生成索引一致性测试通过，无须重写索引。
5. 安全全量未运行：本批不改变层级登记/启动/Tk 生命周期/删除语义，也不在 master 提交点；`dev.py debt` 实读上次绿色 R3293，最新 R3416，源码轮次 23（线8），主干 False/后台触发 False。最近后台全量 HEAD 0e3fc76 退出1，失败文件 test_shared_adapter_infrastructure、test_ui_edges_guards、test_pet_ui、test_perf_baseline。没有改写 receipts。

### 完整架构既有失败的边界
- `test_agents_md.py:191`：未随本工作树交付的 `维护记录/基准历史.json`。不从主树复制私有/运行历史，不伪造绿凭据。
- `test_round_baselines.py` 状态轮次检查：改前 N=3409、M=3416（要求3417）；本批结果后 M=3419（要求3420）。按 AGENTS §2.6/§7，功能分支不能提交 project_status.md，须父任务主干合入轮维护。
- `test_skill_reference_injection.py:19`：缺少 `skills/00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md`。按 R3411 K 为 A14/交付输入，未复制私有技能或删除断言。
修复以上历史问题须超过已授权 3 模块边界或进入主干/交付所有权。本批保留真实失败报告，不宣称完整架构绿色或任务书完成。

## E. 提交与状态
分支不修改 project_status.md；本树 N=3409、M=3419，N=M+1 未满足，由父任务的主干合入轮更新至3420（若届时有更晚结果，按真实最新结果重算）。完整架构未绿，按 runbook §13 规则36采用 `R3419-FAIL: A9静态包子模块分层扫描收口及既有门禁阻塞` 检查点，不标 `[TASK_COMPLETE]`。

提交使用标准 `scripts/dev.py commit --tests test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map`。现入口 `commit_round.py:40` 的 `ROUND_MESSAGE_RE` 只匹配 `R数字:`，不会为 `-FAIL` 自动生成 evidence；因此先显式调用原 `round_evidence.py 3419 -k ...` 执行同一精确定向测试、凭据扫描，再调用其 `stamp_result()` 写机器头并暂存 evidence，保持真实证据，不修改提交工具或跳过测试。证据位于 `tasks_round/evidence/R3419.json`，与本报告、上述 3 模块共一提交；检查点的最终 commit hash 由 `git log -1 --format=%H -- 程序/tasks_round/evidence/R3419.json` 唯一定位，并在交接消息给出（避免把自引用提交哈希伪写入其自身）。

`git diff --check` 通过；暂存白名单只含上述 3 模块、本结果及 evidence。未更新全量凭据、未增豁免、未删除断言、未 push。父任务收到的是可恢复检查点：范围内分层修复及正负例已交付，完整架构验收因三项既有问题仍阻塞。

## F. 下一子批输入
1. A9：先接 L1 对上述五模块环的拆环/诊断 sink 注入证据，再将环消费者迁到增强解析；不得把已知新环记入豁免。之后规范包限定身份、同 stem 冲突、门面与 __init__ 独立副作用、未知层拒绝；同步 _layers 与实际环/层级消费守卫及权威/生成视图，先影子差异再启用，不扩大旧豁免。
2. A9：H03 caller/函数/目标装配例外与动态注册闭包、未知注册键坏样本；H09 TOOLS 的实际生产分类、tests/scripts 禁入与 ASR 独立环境闭包。保留 CLI/注册/分发兼容责任。
3. A10/A11：先接收 L0/L1/L2/foundation 已有等价交付，再处置新扫描暴露的反向边/环；不将 A1 新环记作旧豁免，不重做 HTTP/事务/计量/后台生命周期，不新增 A8 拒绝或延期的依赖。
本子批不启动下一轮，由父任务决定后续子会话。
