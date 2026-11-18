# R3384 结果文件 — K0-R 门控复核与基线刷新（K0 续验）
<!-- round-evidence: {"commit_base": "00ff7962", "credential_hits": 0, "evidence_sha256": "ea947e408d823c06", "exit": 0, "failed": 0, "passed": 0, "round": 3384, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证／基线轮（K0 的门控续验：R3382 合入 `codex/wip-R3259` 后 G-0 翻转，须按 K0-4 口径复核 G-0/G-1 并刷新受漂移影响的实测值；全程未改任何 `.py`，仅修订任务书数字/状态行与新增本结果文件）。
2. **测试跑了吗、三个基线过了吗？** 测量命令全部实跑（门核对、AST 复测、FF-18 冷导入复测）；`smoke_test.py` 默认冒烟 9/9 绿；`smoke_test.py --architecture` 未整轮重跑（本轮零代码改动）；全量回归未触发（无源码变更），欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 无新增欠账；修正任务书 6 处（状态行门态、E1 行数、E23 已解决、E24 分支数、FF-04/FF-05 严格口径重测值），使任务书与 master `00ff7962`（R3383 合并后）实测一致。

## 复核基线

- 工作树：`devin-l0-constitution`（分支 `codex/l0-constitution`，已快进至 master `00ff7962`＝R3383 合并轮，含 dc3b3bb8 的 L0 v2 全量合入）。
- 解释器：`运行环境\Python\python.exe`（Python 3.14.7，随包）。
- K0（R3380）测于 `fbe455a6`；本轮在 `00ff7962` 复测，wip-R3259 合入带来的 contract/ 漂移已计入。

## 门复核（K0-4 续验）

### G-0 —— 已满足 ✓

| 核对项 | 命令 | 结果 |
| --- | --- | --- |
| 6D/7A/7B 合入 master | `git merge-base --is-ancestor 9a611353 master` | 退出码 0（R3382 `dc3b3bb8` 合入 `codex/wip-R3259` 全量，含轮 0–7B＋7B 补项＋收尾） |
| L0 v2 完成文件存在 | `ls 程序/tasks_round/任务完成/` | `L0契约层防崩溃与协议补齐·任务完成.md` 在 |
| 闭环校验 | `python -B -c "import sys; sys.path.insert(0,'scripts'); import taskbook_closure as t; print(t.validate())"` | 输出 `[]` |

### G-1 —— 未满足 ✗（阻塞 K1、K10、K11）

`git diff --name-only master...codex/foundation-*` 仍命中 4 个点名文件的分支（6 个）：

| 分支 | 命中文件 | 领先 master |
| --- | --- | --- |
| `codex/foundation-api-disk` | `contract/platform_tools.py`、`contract/service_contract.py`、`tests/architecture/test_dependency_whitelist.py` | 17 |
| `codex/foundation-asset-disk` | 同上 3 个 | 17 |
| `codex/foundation-hardening` | 同上 3 个 | 17 |
| `codex/foundation-rebase-preview` | 同上 3 个 | 15 |
| `codex/foundation-context-policy` | `contract/workflow_context_budget.py` | 1 |
| `codex/foundation-ffmpeg-runtime` | `contract/platform_tools.py` | 1 |

按阻塞纪律：不代做他人车道合并、不代填验收勾选。K1（白名单测试）、K10（`service_contract`）、K11（`platform_tools`）继续标注「阻塞于 G-1」；K2、K8、K9 仅前置 K0+G-0，**本轮起可执行**。

## 漂移复测（K0-1 续）

| # | K0/R3380 值 | R3384 复测（`00ff7962`） | 处置 |
| --- | --- | --- | --- |
| E1 | 35 模块、6,895 行、最深链 5 级 | 35 模块、**6,913 行**（+18：wip 的 asset_contract/stage_layout/stage_path_service 改动）；无环不变；最深链仍 5 级（按边计，6 模块链 `project_stages→stage_path_service→stage_layout→script_manifest_contract→asset_contract→pet_bus`，wip 未新增 L0 内部边） | 任务书已改 6,913 |
| E2 | 6 模块 import `agent.core` | 6 模块不变（`api_models`、`artifact_lineage`、`pet_bus`、`script_contract`、`script_manifest_schema`、`stage_layout`）；豁免 `baseline_exempt=18`/`items=18` 不变 | 一致 |
| E3 | 3 处 `import_module('script_skill_report')` | 仍 3 处（`script_contract.py:1059,1065,1097`） | 一致 |
| E6 | 高扇入前十 | 逐值一致：`platform_tools` 71、`pet_bus` 61、`stage_layout` 44、`service_contract` 35、`stage_path_service` 34、`storyboard_paths` 33、`script_contract`/`project_stages` 各 32、`project_context` 29 | 一致 |
| E7 | 35/35 无 `__all__` | 35/35 无 `__all__` | 一致 |
| E10 | 5 处 `@dataclass` | 5 处不变 | 一致 |
| E18 | `program_root()` 缺省指向 `程序/contract` | 仍是潜伏缺陷（`script_contract.py:1045-1047`），K2 处理 | 一致 |
| E22 | `pet_bus` 墙钟 `time.time()` | `time.time()` 仍在 `:119,:372`（7B 终态幂等未改时钟） | 一致 |
| E23 | 6D/7A/7B 未合入、无完成文件 | **已解决**：R3382 合入＋完成文件＋closure `[]`（见上） | 任务书已改 |
| E24 | 地基分支领先数 | 复测见 G-1 表（hardening/api-disk/asset-disk/rebase-preview＝17/17/17/15，context-policy/ffmpeg-runtime＝1/1） | 任务书已改 |

## FF-18 冷导入复测（`00ff7962`，随包解释器，各 5 次取中位数）

| 模块 | K0/R3380 基线 | R3384 复测 | 判定 |
| --- | --- | --- | --- |
| `contract.pet_bus` 无 `-B` | 21.9ms | 20.4ms | 低于基线 |
| `contract.pet_bus` 带 `-B` | 21.6ms | 18.8ms | 低于基线 |
| `contract.script_contract` 无 `-B` | 28.4ms | 22.6ms | 低于基线 |
| `contract.script_contract` 带 `-B` | 28.7ms | 21.8ms | 低于基线 |

复测值低于 K0 基线（机器波动与 wip 改动），FF-18 基线仍以 K0/R3380 值为准（目标「不超过 K0 基线 +20%」），本表仅证无回归。

## FF-04／FF-05 严格 K-H1 口径重测（K0-2 续）

K0/R3380 按较窄口径记 FF-04=34、FF-05=69（漏 `file_naming`/`pet_bus`/`script_contract` 的禁用 import，且未计入 K-H1 禁用调用全量）。本轮按 K-H1 字面清单（§3.2：允许标准库白名单＋禁用模块＋禁用调用）用 AST 重测，结果写回任务书 §1.3：

- **FF-04＝56**（禁用模块 import，含函数体内与 try 内）：`platform_tools` 46（os 非 path 用法、shutil/socket/subprocess/sys/webbrowser/threading/time/contextlib/urllib.*/requests/urllib3/certifi/ssl/ctypes/winreg/uuid/base64/struct/array 等）、`script_contract` 3（`importlib` 动态导入）、`pet_bus` 3（queue/threading/time）、`stage_layout` 2（os 非 path、subprocess）、`artifact_schema` 1（shutil）、`file_naming` 1（time）。
- **FF-05＝77**（K-H1 禁用调用 AST 属性名口径：`open()` 全模式、Path 禁用方法名、`os.environ` 访问）：`script_contract` 30、`platform_tools` 15、`stage_layout` 8、`stage_path_service` 7、`pet_bus` 4、`artifact_lineage` 3、`episode_contract` 2、`storyboard_paths` 2、`api_models`/`artifact_schema`/`media_signature`/`script_manifest_schema`/`shot_selection`/`storyboard_contract` 各 1。已剔除：6 处字符串 `.replace()` 误报（`script_contract:192,212,616`、`prompt_templates:90` 均为 `str.replace`）、3 处 `os.urandom`/`os.symlink`（不在 K-H1 禁用调用字面清单，os 模块用法已由 FF-04 计）。
- 口径说明：FF-05 按「属性名」计，未做接收者类型判定（`.exists()` 等在非 Path 对象上的调用可能被计入）；K9 门禁实现时以接收者类型精化，台账以 K9 扫描器实测为准。K0/R3380 的 34/69 与本值并存于结果文件链中，本值为后续轮次引用口径。

## 本轮改动清单

- `程序/tasks_round/L0契约宪法化演进级任务书.md`：状态行（G-0✓/G-1✗）、E1 行数、E23 已解决、E24 分支数、FF-04/FF-05 单元格（共 6 处，就地修订数字与坐标，未改任何决策与勾选行文字）。
- `程序/tasks_round/tasks_round_3384_result.md`：本文件。

## 后续轮次状态

- **可执行**：K2（前置 K0+G-0✓）、K8（K0+G-0✓＋G-2 自决）、K9（K0✓）。
- **阻塞于 G-1**：K1、K10、K11（地基 6 分支未合入或明确放弃前不动）。
- 排程按 §6.1 依赖图与 §6.2 批次执行；下一轮从 K2 开始。

## 三基线

- 默认冒烟：9/9 绿（本工作树实跑）。
- 架构门禁：未整轮重跑（零 `.py` 改动；K0 同口径）。
- 全量回归：未触发（无源码变更）；凭据以 `full-safe-receipts.json` 为准。

## 提交

- 分支 `codex/l0-constitution`；提交号与 hash 见下方提交记录（docs-only 轮，`dev.py commit` 自动生成 `evidence/R3384.json`）。
