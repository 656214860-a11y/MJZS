# R3259 结果：L0 契约层任务书轮 2 — D2 结构治理轮（agent 分层入册＋is_png 下沉 L0）
<!-- round-evidence: {"commit_base": "132547af", "credential_hits": 0, "evidence_sha256": "8e061513ada9281c", "exit": 0, "failed": 0, "passed": 22, "round": 3259, "tests": "run_selftests.py -k layers episode_contract media_signature"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（任务书轮 2：D2-a～D2-e），先 D2-0 只读测量回写任务书，再落码。
2. **测试跑了吗、三个基线过了吗？**
   - 定向自检：`run_selftests.py -k layers episode_contract` → 22 条全绿；`run_selftests.py -k coverage_baseline branch_coverage` → 36 条中仅 2 条红（覆盖率工具子进程 GBK 解码，既有环境欠账，见 §4）。
   - 默认冒烟：`smoke_test.py` → 通过 9 项／失败 0。
   - 架构门禁：`smoke_test.py --architecture` → 488 条。本轮新增可见违规已全部按棘轮登记（D2-0 实测 19 条→消 1 条→净 +10 条 exempt，任务书已回写清单）；改后失败集合 failures=2／errors=2，较 R3246 基线（failures=2／errors=3）无新增回归，差异项见 §4。
   - 全量凭据：未运行。层级登记表改动按任务书约定「合入 master 前触发当次全量」，留待合入轮执行。
3. **欠账少了吗？** 少了 3 条任务书项：D2-a（`is_png` 下沉 L0 无豁免）、D2-b（agent 十子模块入册）、D2-d（违规可见化＋棘轮只降不升）。D2-0/D2-c/D2-e 以测量回写、台账登记、文档同步形式闭环。D3–D8、§9.2 增补项仍在后续轮次。

---

## 1. 改动清单

| 文件 | 改动 |
| --- | --- |
| `程序/contract/media_signature.py` | 新建 L0 模块：`PNG_SIGNATURE`＋`is_png()`（纯文件格式事实，只读 8 字节头），从 `agent.media` 下沉，无豁免（D2-a/Q8）。 |
| `程序/agent/media.py` | 删除本地 `is_png`/`PNG_SIGNATURE` 定义，改为 `from contract.media_signature import …` 再导出——`agent.media.is_png` 既有消费面不变。 |
| `程序/contract/episode_contract.py` | `:12` 改 `from contract.media_signature import is_png`（消除 L0→L1 违例）。 |
| `程序/image_agent_runner.py` | `:5` 同上改 `contract.media_signature`。 |
| `程序/tests/architecture/_scan.py` | `PACKAGE_NAMES` 加入 `"agent"`（第六分层包）：`agent/*.py` 实体进入分层扫描集，`agent.x` import 归一化为扁平登记名；`registry_key`/`_package_target`/docstring 同步口径。 |
| `程序/tests/architecture/_layers.py` | 按 G9 实际 import 核实登记：`media_signature`→L0；`core`/`media`/`publication`→L1；`shot_assets`/`volcengine`/`wan`/`video`→L2；`voice_mcp_server`/`optimizer_mcp_bridge`→L3；`prompt_optimizer`→L4。注释注明 shot_assets(:118)/volcengine(:23)/wan(:19) 对 `ui.white_model_ref` 的懒加载记棘轮豁免、不为抬层。 |
| `程序/tests/architecture/test_no_circular_import.py` | `KNOWN_STATIC_CYCLES` 新增 `{core, file_cache, publication}`；`KNOWN_DYNAMIC_CYCLES` 4→5 条（新增 `{core,file_cache,publication}`，`{keyframe_evidence,shot_assets,stage_parallel,white_model,white_model_ref}` 吸收原 `(white_model,white_model_ref)` 二环）。 |
| `程序/tests/architecture/test_atomic_write_boundary.py`／`test_print_ratchet.py`／`test_recycle_service.py` | 随 agent 包入扫描集同步口径（统计范围/豁免名单对齐）。 |
| `程序/维护记录/架构统一基数.json` | 「层级」台账：D2-0 净增 10 条可见越层全部按 `exempt` 登记（8→18，`baseline_exempt` 同步），清单已回写任务书 §轮2 表下。 |
| `程序/维护记录/覆盖率基线.json`／`分支覆盖率基线.json`／`分支覆盖率下限.json` | `media_signature.py` 入档；`modules_total` 650→651、`modules_covered` 74→75；分支覆盖率下限 `media_signature.py: 100.0`，L0/L1 实体 84→88（+media_signature L0、+core/media/publication L1）。 |
| `程序/runbook.md` | 覆盖率口径数字同步：651/75/576、L0/L1 实体 88（接手时补齐，上游中断前漏改）。 |
| `程序/architecture.md`／`PROGRAM_MAP.md`→`PROJECT_MAP.md` | 分层表与模块地图同步 agent 第六包与 `contract.media_signature`。 |
| `程序/tasks_round/L0…任务书.md` | D2-0 实测回写：19 条可见越层对明细、净 +10 条结构说明（`contract→agent.core` 实为 6 模块而非报告行数口径 11 处，另有 `h3_reference_adapter→shot_assets` 与 3 条 `→white_model_ref`）、环清单变化。 |

## 2. 验证输出摘要

- `run_selftests.py -k layers episode_contract`：22 条全绿（`architecture.test_layers` 6/6、`test_model_probe_layers` 16/16）。
- `run_selftests.py -k coverage_baseline branch_coverage`：36 条，2 红＝两个覆盖率工具子进程用例（`completed.stdout` 为 None，GBK 解码既有环境欠账，改前同红）。
- `smoke_test.py`：9/9。
- `smoke_test.py --architecture`：488 条，failures=2／errors=2（明细 §4）。

## 3. 小决策（任务书未覆盖处）

- **agent 包入册机制**：`agent/` 原不在 `PACKAGE_NAMES`，其模块对分层门禁完全隐身（既不扫也不计）。本轮把 `agent` 加为第六分层包而非新造扫描器；`agent/__init__.py` 为空不产生依赖边。`agent.media.is_png` 消费面经再导出保持兼容，未改任何调用方。
- **棘轮起点按实测登记**：D2-0 要求「总数与预期差距大时先回问」；实测净 +10 条与预期「约 10 条 contract→agent.core」同量级但结构不同（6 模块＋3 条 L2→L4 懒加载＋1 条 L1→L2），按最简方案直接记 exempt 起点并回写任务书，未回问。
- **环登记**：静态环 `{core,file_cache,publication}` 与动态环新增均为登记事实（`core`↔`file_cache`/`publication` 既有环被 agent 入册照亮），进 `KNOWN_*_CYCLES` 显式清单而非消音。

## 4. 架构门禁失败集合（改前后对比）

`smoke_test.py --architecture` 改后（含 runbook 口径修正）：488 条，failures=2／errors=2。

| 用例 | 结果 | 归因 |
| --- | --- | --- |
| `test_branch_coverage_floor…test_branch_coverage_tool_runs_on_bundled_interpreter` | ERROR | 测试子进程 `text=True` 无 encoding，GBK 输出 UnicodeDecodeError（既有环境欠账，R3246 已记录） |
| `test_coverage_baseline…test_coverage_tool_runs_on_bundled_interpreter` | ERROR | 同上 |
| `test_dependency_whitelist…test_whitelist_versions` | FAIL | 本分支落后 master：旧测试硬编码 `requests==2.32.3`，共享解释器已被 whitelist-framework 合入升级至 2.34.2；master 已重写该测试改读锁文件，合并 master 后消除（见 §6） |
| `test_round_baselines…test_round_number_continuous` | FAIL | `project_status.md` 轮次 3234 vs 最新活动 3256+；状态页只在 master 更新，工作树分支固有滞后 |

对比 R3246 基线（failures=2／errors=3）：`基准历史.json` 缺失 ERROR 与 skills 内容 FAIL 已由 R3255 轮修复消失；本轮新增的 `test_runbook_states_the_directed_measurement_caliber` FAIL（runbook 650/74/576、84 未同步）已在收尾时修正复绿。**本改动零新增违规**：D2-0 净增 10 条越层全部入 exempt 棘轮，环全部显式登记。

## 5. 遗留欠账

- 任务书 D3–D8、§9.2 增补 D9–D11、D7 增补：按轮次表后续执行（轮 3A 起）。
- 环境性架构门禁欠账（GBK 子进程、状态页滞后）为既有项，建议主区择机处理。
- `agent/` 其余未列入 §2.5 修订表的子模块（如 `agent/shot_assets` 已列、`media` 已列等 10 个之外的文件）若存在，仍按旧口径不入分层扫描——任务书范围外，未扩大。
- `_d2_sim.py`（D2-0 测量脚本）为工作树根未跟踪草稿，不入库。

## 6. 提交

- 领号：R3259（轮次归属 `dsh-5158b800-34ae`／`codex/wip-R3255`，本文件即该轮结果）。
- commit：`R3259: …`（hash 见 git log；`round_evidence` 自动盖 `tasks_round/evidence/R3259.json` 并回填本文件机器头）。
- **中断接续说明**：本轮代码改动由前序会话完成（最后写入 01:11，轮次 01:37 领号后中断）；本次接手复核改动完整性、补齐 runbook 口径、补跑验证并收尾提交，未推翻任何既有改动。
- **下一步**：合并 master（R3258+，含 whitelist-framework）消除 §4 白名单版本滞后并解锁轮 3B/4B 的 requests 基建，再进轮 3A。
