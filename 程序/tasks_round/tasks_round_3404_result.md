# R3404 结果 —— K9 L0 纯度门禁与 L0P 层登记
<!-- round-evidence: {"commit_base": "3a97b184", "credential_hits": 0, "evidence_sha256": "97e57cf79990e1d0", "exit": 0, "failed": 0, "passed": 53, "round": 3404, "tests": "run_selftests.py -k contract_purity layers gate_selfaudit agents_md"} -->

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（门禁）。任务书「轮 K9」，车道 L0，前置 K0＋G-0（K0/R3380 已合、G-0 于 R3384 复核满足）。
2. **测试跑了吗、三个基线过了吗？** 跑了。默认冒烟 9/9 通过；定向 `run_selftests.py -k contract_purity layers gate_selfaudit` 47 条全绿（contract_purity 10、test_layers 6、test_model_probe_layers 16、test_gate_selfaudit 6，另 agents_md 15 复验）；`smoke_test.py --architecture` 首轮 541 条仅 `test_architecture_guard_list_matches_actual_test_files` 一红——系本轮新增 `test_contract_purity.py` 后清单未同步的时序陈旧失败，同轮已补 `architecture.md` 门禁清单并复跑该文件转绿，全量复跑结果见下方「验证」节。
3. **欠账少了吗？** 无新增欠账；FF-04／FF-05 从「只有实测数」升级为「AST 门禁＋台账棘轮」——`contract/` 现存 136 处违规（import 53＋禁用调用 83）按「文件:符号:类型」逐项登记 `架构统一基数.json`「L0 纯度」段，后续 K12–K14 迁移每消一处必须同步减台账，只减不增。

## 开工与领号

- 车道 `devin-l0-constitution`／分支 `codex/l0-constitution`；`round_claim.py next` 领 **R3404**（2026-11-18 20:24:27）。
- master 基线：R3403 合并轮 `3a97b184`（K2 已合入）；`project_status.md` 当前轮次 3404。

## K9-1 纯度门禁（`tests/architecture/test_contract_purity.py`，新增）

- 扫描对象：`contract/*.py`（36 文件，含 `__init__.py`）。
- **禁用 import**：AST 全树遍历（模块级、函数体内、`try` 内一律计入）；相对导入与第一方包（`contract/infra/domain/orchestrator/ui/agent/foundation/tests/scripts` 及 contract 同级模块名）不判；`os` 仅放行 `os.path` 纯用法（`import os.path`／`from os import path`／`from os.path import *`）；K-H1 允许标准库白名单之外的标准库与全部第三方运行时包均计违规，类型记 `import:<顶层模块>`。
- **禁用调用**：`open()`（builtin）、Path 禁用方法名集合（`read_text/write_text/read_bytes/write_bytes/open/mkdir/touch/unlink/rename/replace/iterdir/glob/rglob/exists/is_file/is_dir/stat`）、`os.environ` 属性访问与 `os.getenv()`，类型记 `call:<名>`。接收者为字符串字面量／`JoinedStr` 时不计 Path 方法（保守口径：其余接收者一律计入，棘轮只减不增，接收者类型精度后续轮次可只减不增地精化）。
- **登记格式**：「文件:符号:类型」，符号取最近作用域 qualname（模块级记 `<module>`），同键计数合并为 `count`，行号无关、随无关行平移不 churn。
- **棘轮**：`test_scan_matches_ledger_and_never_exceeds_baseline` 断言实测 Counter 与台账逐项相等（双向，不等即红）且总数 ≤ `baseline_total`（立书基线，只减不增）。

## K9-2 坏样本自审（`tests/architecture/_canary/`）

- `l0_purity_import_subprocess.py`：函数体内 `try` 里的 `import subprocess` → 识别 `import:subprocess`。
- `l0_purity_path_write_text.py`：`Path(path).write_text(...)` → 识别 `call:path.write_text`。
- 另有内联样本覆盖：`from os import environ`、`open()`、`os.environ[...] =`、`requests`/`sys`/`time` 第三方与非白名单标准库、白名单与第一方放行样本。

## K9-3 L0P 层登记（`tests/architecture/_layers.py`、K-H2）

- `LAYER_NAMES` 新增 `0.5: "L0P 平台基座"`；`LAYERS`/`_register` 注解放宽为 `float`（层号非整数按数值比较，未重排既有层号）。
- 语义：L0P 只许依赖 L0 与标准库；L0(0) < L0P(0.5) < L1(1)，故 L0 import L0P 按 `test_layers` 同一数值判定为越层；`foundation/` 实体包待 K11 建包时按真实依赖入 `LAYERS`。
- `architecture.md` §3 分层表在 L0 与 L1 行之间新增 L0P 行；§「当前架构门禁清单」补登 `test_contract_purity.py`。

## K9-4 `contract/__init__.py` docstring

改为与门禁一致表述并引用门禁名 `test_contract_purity.py` 与台账「L0 纯度」段。

## 台账基线（K9 扫描器实测，权威口径）

- `baseline_total = 136`：`import` 53＋`call` 83，122 个「文件:符号:类型」键。
- 分模块：platform_tools 61、script_contract 35、stage_layout 10、pet_bus 7、stage_path_service 7、artifact_lineage 3、artifact_schema 2、episode_contract 2、storyboard_paths 2、api_models／file_naming／media_signature／prompt_templates／script_manifest_schema／shot_selection／storyboard_contract 各 1。
- 与 R3384 严格口径（FF-04=56、FF-05=77，合计 133）差异说明：K2 已移除 script_contract 3 处 `importlib` 动态导入（53＝56−3 吻合）；call 侧 +6 为保守接收者口径把 R3384 手工剔除的字符串 `.replace()` 等计入（台账以 K9 扫描器实测为准，R3384 已预留此口径）。

## 验证

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k contract_purity layers gate_selfaudit` | 47 条全绿（0 红 0 跳过） |
| `run_selftests.py -k agents_md contract_purity`（清单补登后复验） | 25 条全绿 |
| `smoke_test.py`（默认冒烟） | 9/9 通过 |
| `smoke_test.py --architecture` | 两轮共 541＋542 条；唯一红项均为 `test_round_number_continuous`——特性分支上结果文件先于状态页抬头存在属预期形态（`project_status.md` 仅 master 可提交，合并轮由 `merge_round.py` 抬头至「结果轮次+1」，合并候选 CI 期间该检查按 `merge_round.py` 既有逻辑跳过）；门禁清单时序红已修并复验转绿 |

## 改动清单

- 新增 `程序/tests/architecture/test_contract_purity.py`（门禁＋L0P 登记测试）
- 新增 `程序/tests/architecture/_canary/l0_purity_import_subprocess.py`、`l0_purity_path_write_text.py`
- `程序/tests/architecture/_layers.py`：LAYER_NAMES 增 0.5 L0P；`LAYERS`/`_register` 注解 float
- `程序/architecture.md`：§3 分层表 L0P 行；门禁清单补 `test_contract_purity.py`
- `程序/contract/__init__.py`：docstring 对齐门禁
- `程序/维护记录/架构统一基数.json`：新增「L0 纯度」段（allowed_stdlib／禁用口径说明／baseline_total=136／items 122 键）

## 边界与后续

- 本门禁只判纯度（外部依赖与 IO 调用），不判分层方向；`contract/` 对 `agent.core` 等第一方向上 import 仍由 `test_layers`＋「层级」台账管辖。
- `json`/`datetime`/`pathlib` 的「只用于编解码／纯计算／路径运算」使用面约束属 K-H1 描述性条款，本轮按 import 级白名单执行，使用级精化留待 K12–K14 迁移轮按需收紧（棘轮只减不增，不会回退）。
- K8（Severity 统一）与 K9 均已具备前置；K1/K10/K11 仍阻塞于 G-1（6 个地基分支未合）。
