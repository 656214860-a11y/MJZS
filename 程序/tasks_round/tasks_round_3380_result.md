# R3380 结果文件 — K0 基线重测与门控核对
<!-- round-evidence: {"commit_base": "fbe455a6", "credential_hits": 0, "evidence_sha256": "1575d1b3ad29afe6", "exit": 0, "failed": 0, "passed": 0, "round": 3380, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证／基线轮（只读诊断性质：全程未改任何 `.py`，仅新增本结果文件并按 K0-1 就地修订任务书 §0.1／§1.3 的数字与状态行）。
2. **测试跑了吗、三个基线过了吗？** 测量命令全部实跑（AST 扫描复用 `tests/architecture/_scan.py` 口径）；`smoke_test.py` 默认冒烟 9/9 绿；`smoke_test.py --architecture` 未整轮重跑（本轮零代码改动，测量所用架构扫描模块导入与调用正常）；全量回归未触发（无源码变更），欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 无新增欠账；顺带修正立书数字漂移 4 处（E6 扇入、E10 dataclass 数、E24 分支数、FF-04/05/18 实测值回填），使任务书与 master `fbe455a6` 实测一致。

## 测量口径

- 工作树：`devin-l0-constitution`（分支 `codex/l0-constitution`，基于 master `fbe455a6`＝R3379 合并后）；解释器：`运行环境\Python\python.exe`（Python 3.14.7）。
- E1/E6/E7/E10 等 AST 统计：`tests.architecture._layers.LAYERS`＋`_scan.module_scan_files()/module_import_rows()/module_dynamic_import_rows()`（与分层门禁同一扫描集与归一化口径，`contract.x` 归一为扁平名 `x`）。
- FF-04/FF-05：对 `contract/*.py`（35 个实体模块，不含 `__init__.py`）逐文件 AST 扫描，清单按任务书 K-H1。
- FF-18：随包解释器 `python -c "import time; t=time.perf_counter(); import contract.<mod>; …"`，每组 5 次取中位数。

## K0-1　E1–E27 重测（命令与输出摘要）

| # | 立书值 | R3380 实测 | 结论 |
| --- | --- | --- | --- |
| E1 | 35 模块／6,895 行／无环／最深链 5 级 | `contract/` 实体 35 个（＝`_layers` 登记 L0 35 名，双向一一对应）；`splitlines` 合计 **6,895 行**；L0 内部静态图无环；L0 内最深链 `script_contract`、`project_stages` 各 **5 跳**（6 模块） | 一致 |
| E2 | 6 个 L0 模块静态 import L1 `agent.core`；豁免 18 条 | 实测 **6 个**：`api_models:62`、`artifact_lineage:14`、`pet_bus:14`、`script_contract:36,69,250,834,908`（其中 250/834/908 为函数内惰性 import）、`script_manifest_schema:17`、`stage_layout:30`；`架构统一基数.json`「层级」`baseline_exempt=18`、`items=18` | 一致 |
| E3 | L0→L3 动态越层 1 处 | `contract/script_contract.py:1059,1065,1097` 三处 `import_module('script_skill_report')`（同一函数族三个入口） | 一致 |
| E4 | 豁免分散两处 | `架构统一基数.json`「层级」18 条＋`test_layers.KNOWN_DYNAMIC_UPWARD` 3 条（engine→white_model、keyframe_batch→stage_parallel、script_contract→script_skill_report） | 一致 |
| E5 | `contract/__init__.py` 声明「无 Tk、无 IO 副作用」与实际不符 | `__init__.py:1` 原文仍在；反例依旧：`platform_tools`（socket/subprocess/requests/ctypes/winreg/webbrowser/ssl）、`pet_bus`（线程＋mkdir＋open 读）、`stage_layout`（subprocess、os.symlink、mkdir） | 一致 |
| E6 | 扇入两极分化（见下表） | 见下「E6 重测表」；高扇入头部与零扇入集合结论不变，具体数值随代码漂移已同步任务书 | 数字已同步 |
| E7 | 35 个模块均无 `__all__` | 35/35 无 `__all__`（`grep -l __all__ contract/*.py` 零命中） | 一致 |
| E8 | 两套 Severity 词表 | `diagnostics.Severity`＝fatal/error/warn/degraded（`diagnostics.py:18,25-28`）；`error_codes.SEVERITIES`＝fatal/degraded/recoverable/info（`error_codes.py:16`） | 一致 |
| E9 | 事件契约只登记必填字段名，无类型/版本，命名混用 | `pet_bus.py:48-69` `CONTRACT` 仍是 `kind→必填字段元组`；`usage_updated`、`intent.command` 与 `stage.*` 点式命名并存 | 一致 |
| E10 | dict＋正则为主，6 个 dataclass，「空列表即通过」 | `@dataclass` 实测 **5 处**（diagnostics、error_codes、file_index_contract、project_context、service_contract），立书值 6 差 1，已同步；`asset_contract` problems 列表、`episode_contract` errors/warnings、`stage_layout.stage_contract_errors` 空集放行模式仍在 | 数字已同步 |
| E11 | `artifact_schema` 五态 | `classify()` 五态 current/legacy/missing/future/invalid（`artifact_schema.py:89-116`，注释 :21 明示闭集）；契约 API 仍无版本 | 一致 |
| E12 | `architecture.md` L0 行漏 16 个、错列 `continuity_ledger` | L0 行（`architecture.md:104`）仍列 20 名；比对 `_layers` L0 35 名：漏列仍为立书所列 16 个，`continuity_ledger` 仍错列（实登记 L1，`_layers.py:22` 注释 R1647） | 一致 |
| E13 | `--affected` 只看直接 import | `smoke_test.py` `_affected_test_plan`/`_direct_imports`（约 :495-511）仍按测试文件直接 import 名单筛选，无传递闭包 | 一致 |
| E14 | 15 份黄金文件＋自审/守卫/变异抽样 | `tests/fixtures/golden/` 15 份；`test_golden_outputs.py`、`test_gate_selfaudit.py`、`test_rule_guard_map.py`、`scripts/mutation_sample.py` 均在 | 一致 |
| E15 | 白名单措辞＋`AGENTS.md:15` | `依赖白名单.md` 第一节仍是「允许在证明必要后引入，不是默认放行」；`AGENTS.md:15` 仍写「白名单依赖」 | 一致 |
| E16 | 解释器 3.14.7 vs `pyproject` py310/3.10 | `sys.version`＝3.14.7；`pyproject.toml:3` `target-version="py310"`、`:11` `python_version="3.10"` | 一致 |
| E17 | 两个不可比版本源 | `contract/app_metadata.py:4` `VERSION='V0.7'`；仓库根 `安装信息.json` `"version":"0.6-20260918"`（未跟踪运行文件，实测值） | 一致 |
| E18 | `program_root()` 缺省指向 `程序/contract` | `contract/script_contract.py:1045-1047` `Path(program or Path(__file__).resolve().parent)`——`__file__` 在 `contract/` 内，缺省返回 `程序/contract` | 一致 |
| E19 | ≥3 种目录名＋LOCALAPPDATA KeyError＋Program Files 硬编码 | `infra/app_icon.py:313-314` `MangaAssistant`；`infra/cloud_assets.py:19`、`infra/qwen_setup.py:7` `漫剧制作助手`；`cloud_assets.py:19` `os.environ['LOCALAPPDATA']` 直取；`infra/integrations.py:23` `C:\Program Files\Comfy Desktop\...` | 一致 |
| E20 | stdlib 扫描只覆盖 `程序/*.py`＋`agent/` | `tests/test_stdlib_imports_available.py:14` `SOURCES = glob('*.py') + agent/**/*.py`，`contract/`、`infra/`、`domain/`、`orchestrator/`、`ui/` 不在面内 | 一致 |
| E21 | `MAX_PATH=260` 无平台能力声明 | `contract/file_naming.py:132` `MAX_PATH = 260`，`:175-176` 超长即 `ValueError` | 一致 |
| E22 | `pet_bus` 用墙钟、无可注入时钟 | `contract/pet_bus.py:119,372` 两处 `time.time()`；L0 无 clock 端口 | 一致 |
| E23 | 6D/7A/7B 未合入、无 L0 v2 完成文件 | `git merge-base --is-ancestor` 对 `a25edab1`(R3338/6D)、`bea4b548`(R3343/7A)、`9a611353`(R3364/7B) 均退出码 1，三者只在 `codex/wip-R3259`；`tasks_round/任务完成/` 无 L0 契约宪法化文件（L0 v2 完成文件亦不存在） | 一致 |
| E24 | 地基分支改 L0 文件 | 见下「E24 重测」；`foundation-hardening` 19 提交（立书 20）、`api-disk` 17、`rebase-preview` 15、`asset-disk` 16 均改 `platform_tools.py`＋`service_contract.py`（前三者另改 `test_dependency_whitelist.py`）；`context-policy` 改 `workflow_context_budget.py`；`ffmpeg-runtime` 改 `platform_tools.py`；`5ab81112`（R3319 A5）在 `foundation-api-disk`/`foundation-asset-disk` 未合入 | 数字已同步 |
| E25 | F11/F12/F13 过期 | `codex/wip-R3259` 现领先 master **8** 个提交（立书时 12）；`codex/wip-r3282` **0**（已并入）；豁免 **18/18**（立书时 8/8） | 过期属实，交接见 K0-5 |
| E26 | 5 个关键门禁坏样本自审 | `test_gate_selfaudit.py` 6 个测试方法覆盖 5 门禁；`tests/architecture/_canary/` 8 个坏样本 | 一致 |
| E27 | 生产锁 6 包＋开发锁 ruff/mypy | `requirements.txt`：requests 2.34.2、urllib3 2.8.0、certifi 2026.10.23、charset-normalizer 3.5.2、idna 3.20、Pillow 13.0.0；`dev-requirements.txt`：ruff 0.15.20、mypy 1.18.2 | 一致 |

### E6 扇入重测表（R3380）

口径：`module_scan_files()` 扫描集（顶层生产文件去门面＋六分层包实体）内，按 `module_import_rows`＋`module_dynamic_import_rows` 归一化后统计**不同导入方文件数**（静态＋动态，不含 `tests/`）。

| 类别 | 实测 |
| --- | --- |
| 高扇入 | `platform_tools` 71、`pet_bus` 61、`stage_layout` 44、`service_contract` 35、`stage_path_service` 34、`storyboard_paths` 33、`script_contract` 32、`project_stages` 32、`project_context` 29 |
| 零扇入（对外＝0，仅 L0 内部引用） | `script_brief`（仅 `script_contract`）、`script_output_spec`（仅 `script_contract`）、`script_manifest_contract`（`script_contract`/`script_manifest_schema`/`stage_layout` 三处 L0 内部引用） |
| 碎片模块（行数复核不变） | `app_metadata` 4 行、`pet_settings_contract` 9 行、`media_signature` 15 行、`model_protocol` 15 行 |
| 无测试直接 import（`tests/` 内无 import 语句命中） | `media_signature`、`model_protocol`、`pet_settings_contract`、`script_brief`、`shot_selection` 五模块复核仍为零直接 import |

全层合计：35 个 L0 模块被扫描集内文件引用总次数 486（含 L0 内部互引）；剔除 L0 内部引用后对外扇入合计 459。两极分化结论不变，头部数值较立书小幅漂移（代码在立书后继续演进）。

## K0-2　FF-04／FF-05 实测（K-H1 清单，逐模块）

扫描对象：`contract/` 35 个实体模块。FF-04 计「禁用模块 import 次数」（tkinter／GUI 绑定模块／L3-L4 编排／模型与传输／LLM SDK／第三方包／网络与写盘库模块的 import 与 from-import）；FF-05 计「IO 调用点」（`open()` 全模式、`Path.read_*`/`write_*`、`os.*`/`shutil.*`/`subprocess.*`/`socket.*`/`ssl.*`/`ctypes.*`/`webbrowser.*`/`requests.*` 等属性调用、`agent.core` IO 网关名 `read/save/save_text/read_json/file_hash` 调用）。

### FF-04＝34（禁用模块 import）

| 模块 | 次数 | 明细 |
| --- | --- | --- |
| `platform_tools` | 32 | `socket`×2、`subprocess`、`webbrowser`、`urllib.parse`×2、`urllib.request`×3、`urllib.error`×3、`requests`×3、`requests.adapters`、`urllib3.exceptions`×3、`urllib3.util`、`ssl`×2、`ctypes`×4、`winreg` |
| `stage_layout` | 1 | `import subprocess`（:27） |
| `artifact_schema` | 1 | `import shutil`（:14） |
| 其余 32 个模块 | 0 | — |

另：禁用「写盘/IO 原语」调用 47 处已并入 FF-05 口径统计（见下）；`agent.core` 写网关调用 6 处（`script_contract` 4、`stage_layout` 1、`artifact_lineage` 1）属 E2 豁免域，单列备查。

### FF-05＝69（IO 调用点）

| 模块 | 次数 | 构成 |
| --- | --- | --- |
| `platform_tools` | 36 | subprocess.run/Popen、socket.create_connection、ssl.*、requests.*、urllib.*、webbrowser.open、os.urandom、shutil.which、.mkdir 等 |
| `script_contract` | 15 | `agent.core` `read/save/save_text` 6、`Path.read_text/read_bytes` 7、`open()` 2 |
| `artifact_lineage` | 5 | `agent.core` `read_json`×3、`save`、`file_hash` |
| `pet_bus` | 4 | `.mkdir()`×2、`open(mode='r')`×2（ErrorLog 读写） |
| `stage_layout` | 4 | `.mkdir()`×2、`os.symlink`、`agent.core.save_text` |
| `artifact_schema` | 2 | `shutil.copyfile`×2（:233,:245，迁移前备份复制） |
| `api_models` | 1 | `agent.core.read`（:66） |
| `media_signature` | 1 | `open(mode='rb')`（:14，PNG 签名探测） |
| `script_manifest_schema` | 1 | `agent.core.read`（:384） |
| 其余 26 个模块 | 0 | — |

口径外备查：`exists/is_file/is_dir/stat/resolve/glob/iterdir` 等文件系统元数据探测调用另有 **87 处**（12 个模块，`script_contract` 33、`artifact_lineage` 10、`stage_path_service` 9、`stage_layout` 8 等），未计入 FF-05，供 K9 门禁口径参考。

### FF-01～FF-18 立书值核对（K0 只回填实测项，其余抄录立书值）

| ID | 立书值 | R3380 状态 |
| --- | --- | --- |
| FF-01 | 6 | 未重测（K12–K14 落地；豁免棘轮口径不变） |
| FF-02 | 1 | 实测仍为 1 处函数族（见 E3） |
| FF-03 | 2 | 实测仍为 2 个登记源（见 E4） |
| FF-04 | K0 实测 | **已回填 34** |
| FF-05 | K0 实测 | **已回填 69** |
| FF-06 | 0/35 | 实测仍为 0/35（见 E7） |
| FF-07 | 0 | 未重测（K4 落地） |
| FF-08 | 无检测 | 未重测（K5 落地） |
| FF-09 | 无机制 | 未重测（K6 落地） |
| FF-10 | 2 | 实测仍为 2 套词表（见 E8） |
| FF-11 | 0/20 | 未重测（K11 落地） |
| FF-12 | 6 个 dataclass | 实测 **5**（见 E10，已同步） |
| FF-13 | 2/6 | 未重测（K20 落地） |
| FF-14 | 5 | 实测 5 门禁／8 坏样本（见 E26） |
| FF-15 | 17 | 未重测（K15 落地；E12 漏列 16＋错列 1 与文档行口径略有出入，以 K15 实测为准） |
| FF-16 | 一层 | 未重测（K16 落地） |
| FF-17 | 无 | 未重测（K19 落地） |
| FF-18 | 0；K0 实测 | **已回填**：环 0；冷导入基线见下 |

## K0-3　FF-18 冷导入基线（随包解释器，5 次取中位数）

命令：`运行环境\Python\python.exe [-B] -c "import time; t=time.perf_counter(); import contract.<mod>; print((time.perf_counter()-t)*1000)"`，每组连续 5 次。

| 探测 | 无 `-B`（ms） | 中位 | `-B`（ms） | 中位 |
| --- | --- | --- | --- | --- |
| `contract.pet_bus` | 28.1 / 21.9 / 24.5 / 20.5 / 21.3 | **21.9** | 21.6 / 31.9 / 22.7 / 21.2 / 21.3 | **21.6** |
| `contract.script_contract` | 46.7 / 27.4 / 28.4 / 28.8 / 27.2 | **28.4** | 28.7 / 29.1 / 28.9 / 27.1 / 28.7 | **28.7** |

- FF-18 基线取 `contract.pet_bus` 为主指标：**21.9ms（无 -B）／21.6ms（-B）**；`contract.script_contract` 为参考：28.4ms／28.7ms。`-B` 影响 <2%，因 `contract.pet_bus` 依赖面小（仅 `agent.core`）。
- 「不超过 K0 基线 +20%」的验收线：pet_bus ≤ 26.3ms（按无 -B 中位计）。

## K0-4　门 G-0、G-1 核对结论

### G-0 —— **未满足**

- `git merge-base --is-ancestor 9a611353 master` → 退出码 1（7B 未合入）；`a25edab1`(6D)、`bea4b548`(7A) 同法验证均退出码 1，三者仅存于 `codex/wip-R3259`（现领先 master 8 个提交）。
- `tasks_round/任务完成/` 下无 `L0契约层防崩溃与协议补齐·任务完成.md`（本任务书的 L0 契约宪法化完成文件亦不存在）。
- `taskbook_closure.validate()` 输出 `[]`——但那是对**现存**完成文件的校验，本门要求的 L0 v2 完成文件根本不存在，故 validate 通过不构成 G-0 满足。
- **结论**：G-0 阻塞 K1 起全部轮次（K1、K2、K8 直接前置含 G-0；K3–K7、K10–K23 经 K1/K2/K8/K4 等传递阻塞）。按 §0.0.2 纪律，本车道不合并 `codex/wip-R3259`、不代填他人验收。

### G-1 —— **未满足**

核对方式：`git diff --name-only master...codex/foundation-*` 命中四文件（`contract/platform_tools.py`、`contract/service_contract.py`、`contract/workflow_context_budget.py`、`tests/architecture/test_dependency_whitelist.py`）。

| 分支 | 领先 | 命中文件 |
| --- | --- | --- |
| `codex/foundation-hardening` | 19 | platform_tools、service_contract、test_dependency_whitelist |
| `codex/foundation-api-disk` | 17 | 同上 3 件（含 A5 `5ab81112`） |
| `codex/foundation-rebase-preview` | 15 | platform_tools、service_contract |
| `codex/foundation-asset-disk` | 16 | platform_tools、service_contract |
| `codex/foundation-context-policy` | 1 | workflow_context_budget |
| `codex/foundation-ffmpeg-runtime` | 1 | platform_tools |

- **结论**：G-1 阻塞 K1（白名单测试同文件）、K10（`service_contract`）、K11（`platform_tools`）。
- 已按 K0-4 把任务书状态行更新为「G-0、G-1 未满足，依赖门轮次各自标注阻塞」。

### 受门影响的排程结论

- **可执行**：K9（L0 纯度门禁，前置仅 K0）——下一轮执行。
- **阻塞于 G-0**：K1、K2、K8（直接前置），及其全部下游 K3–K7、K10–K23。
- **阻塞于 G-1**：K1、K10、K11（与 G-0 阻塞叠加）。
- G-2（K8 Severity 自决）、G-5（K7 引擎自决）为执行模型自决门，到对应轮次时按判据执行，不预判。

## K0-5　地基任务书 F11／F12／F13 重测值（交接地基车道）

| # | 立书值（地基 §0.1） | R3380 重测 | 说明 |
| --- | --- | --- | --- |
| F11 | L0 分支 12 提交、L2 分支 14 提交未合入 | `git rev-list --count master..codex/wip-R3259`＝**8**；`master..codex/wip-r3282`＝**0**（L2 已合入，E25 同证） | L0 v2 收尾仍在推进但未合入；L2 阻塞已解除 |
| F12 | 反向依赖豁免 8/8 已满 | `架构统一基数.json`「层级」`baseline_exempt=18`、`items=18` | 豁免额度已扩至 18/18（R3255 agent/ 入册净增 10 条），「已满」结论仍成立且更紧 |
| F13 | `platform_tools` 登记 L0／正文 L1；`native_assets` 登记 L4／正文 L2 | `platform_tools`：`_layers.py:13` 登记 L0；`architecture.md` L0 行仍漏列（E12 之一），L1 行仅在说明栏提及、未列成员——「正文 L1」的显式矛盾已弱化但未消除；`native_assets`：`_layers.py:39` 登记 L4，`architecture.md:106` L2 行成员表仍列其名——**矛盾依旧** | 交接地基车道刷新；本书不代改地基任务书 |

另按 H8 取证（K0 兼负）：`git log -- 程序/contract/` 仅 38 个提交、最早 R2776（T10 批次1）；`contract/pet_bus.py` 全历史含 `--follow` 也仅 12 条（实体迁入于 R2835）。**结论：`contract/` 的 git 改动次数因 T10 搬迁被截断，不能作为稳定性指标——H8 假设成立**，K3+ 不得用改动次数论证「稳定」。

## 与立书值不一致项（已同步修订本任务书）

1. E6 扇入分布数值（口径已在表注明，结论不变）。
2. E10「6 个 dataclass」→ 实测 5。
3. E24 `foundation-hardening` 领先数 20→19，并补记 `rebase-preview`(15)、`asset-disk`(16) 两支同样命中四文件。
4. FF-04/FF-05/FF-18 由「K0 实测」回填为实测值。
5. 状态行按 K0-4 更新为门未满足的真实状态。

## 三个基线

- 默认冒烟：9/9 绿。
- 架构门禁：本轮未整轮重跑（零 `.py` 改动）；测量链路 `tests.architecture._scan`／`_layers` 导入与 AST 扫描实跑正常。
- 全量回归：未触发；凭据以 `full-safe-receipts.json` 为准。

## 提交

- 分支 `codex/l0-constitution`，轮次号 R3380；变更集＝本结果文件＋任务书 §0.1/§1.3/状态行数字修订（K0 允许范围）。

## 下一步

- `dev.py merge` 合入 master 后执行 **K9**（L0 纯度门禁，前置仅 K0 已满足）。
- K1、K2、K8 及其下游轮次继续标注「阻塞于门 G-0／G-1」，待 L0 v2（6D/7A/7B）与地基分支合入后解锁。
- 接力要点：工作树 `D:\漫剧制作助手\.agents\worktrees\devin-l0-constitution`；解释器用主工作区 `运行环境\Python\python.exe`；`contract/`、`tests/`、子模组内容沿用 KR 轮已补齐的本地状态（不入库）。

[TASK_CONTINUE]
