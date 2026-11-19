# R3826 结果：验收分支全量自检红项清零（棘轮合规＋环境对齐＋基线重测）
<!-- round-evidence: {"commit_base": "c051bbdd", "credential_hits": 0, "evidence_sha256": "bd7df64c5de61be6", "exit": 0, "failed": 0, "passed": 61, "round": 3826, "tests": "run_selftests.py -k silent_exception_ratchet unification_ratchet copy_rules branch_coverage_floor error_codes secret_status_diagnostics"} -->

- 轮次类型：修复轮（§3.2）——验收分支合入 master 前的全量 `--all --safe` 自检暴露红项，逐项定位根因后最小修复。
- 是否跑测试：跑了——棘轮/文案/契约定向 unittest、分支覆盖率基线重测（98 个目标用例全量）、走查脚本回归；结果以提交回执为准。
- 积压是否下降：是——分支侧架构棘轮、文案规则、契约测试恢复绿色；覆盖率基线按真实重测刷新（model_metering 11→12 决策点）。

## 1. 三问

1. **什么类型轮**：修复轮。触发源：`run_selftests.py --all --safe`（隐藏桌面全量）在 R3815 后暴露 13 个测试文件红项。
2. **是否跑测试**：跑了——见 §4。
3. **积压是否下降**：是——本轮产生的验收脚本欠账（棘轮登记）当轮闭环；历史欠账中属环境性的已对齐工作树环境核验，属 master 侧陈旧的测试契约已同步 master 权威版本。

## 2. 红项根因分类与处置

### 2.1 本轮代码欠账（已修复）

| 红项 | 根因 | 处置 |
| --- | --- | --- |
| `test_silent_exception_ratchet` | 6 个验收脚本 27 处 `except Exception: pass` | 全部改 `app_logging.swallowed()` 留痕（限频去重，不改语义） |
| `test_unification_ratchet` 第四项 | 脚本内 22 处裸 `json.loads` 未登记 | 15 处文件读改 `file_cache.read_json()`（正式 JSON 读唯一入口）；7 处内存载荷解析（HTTP 请求体/JSONL 行/b64）在 `维护记录/架构统一基数.json` 登记 exempt 并写明理由 |
| `test_unification_ratchet` 第五项 | `acceptance_release_probe.py:main` 读 `config.json` 走裸 open/loads | 同上改 `file_cache.read_json()`，函数内不再含 load/loads/open 调用 |
| `test_copy_rules` | 探针脚本字符串常量含「你」 | `acceptance_e2e_worker.py` 假剧本正文与 `acceptance_stage_op_walkthrough.py` 假对白 `你`→`您`（仅夹具文案，非产品文案） |
| `test_branch_coverage_floor` | `model_metering.py` 决策点 11→12（R3709 修复引入，master 侧同样陈旧） | `scripts/branch_coverage_report.py` 以 98 个登记目标真实重测刷新 `维护记录/分支覆盖率基线.json`；门禁明示「须真实重测，不能计量兼容门面」，故不手改基线 |

### 2.2 分支陈旧，已同步 master 权威版本（契约未变）

| 红项 | 根因 | 处置 |
| --- | --- | --- |
| `test_error_codes` | 分支测试黄金表缺 master 已增的 5 个错误码条目（`contract/error_codes.py` 两侧一致） | `git checkout master -- tests/test_error_codes.py` |
| `test_secret_status_diagnostics` | 分支测试仍期望导出包无 `metrics_summary.json`；现行 `diagnostic_capture.export` 恒写指标快照 | `git checkout master -- tests/test_secret_status_diagnostics.py` |
| `test_rule_guard_map` | 已生成报告与规则源不同步（规则 35 名称） | `python -B scripts/rule_guard_map.py --write` 重新生成 |

### 2.3 工作树环境缺件（不入库，已对齐主工作区）

| 红项 | 根因 | 处置 |
| --- | --- | --- |
| `test_skills`／`test_round_gate`／`test_script_contract` | 技能注册表 71≠73：`skills/01 剧本准备SKILL/剧本锻造`、`编剧技能集` 为 submodule，工作树未初始化 | 自主工作区同步技能包内容（父仓 gitlink 不变，不产生提交） |
| `test_agents_md` | `维护记录/基准历史.json` 为 gitignore 运行时文件，工作树缺失 | 自主工作区复制同名运行时文件 |
| `test_dependency_whitelist` | 工作树 `运行环境` 曾复制自正式安装版（含 pydantic 等非白名单包） | 删除错误副本；`运行环境` 改为 junction 指向 `D:/漫剧制作助手/运行环境`（白名单解释器＋ffmpeg 俱全），测试一律用随附解释器 |
| `test_secret_status_diagnostics`（首轮） | `logs/metrics_summary.json` 运行时残留混入导出白名单 | 清理运行时残留；根因另见 §2.2 |
| `test_keyframe_*`（覆盖率重测两轮） | junction 建立前 `tool_path('ffmpeg')` 不可达 | junction 后复测 25/25 通过 |

### 2.4 保留红项（如实记录，非本轮可修）

- `architecture.test_round_baselines.test_round_number_continuous`：`project_status.md` 轮次头仅 master 可提交（§2.6），分支上恒红；master 侧该测试当前亦滞后（头 3784＜最新结果+1），合入轮由状态页同步解决，本轮不绕过。

## 3. 改动清单

- `scripts/acceptance_{chain,e2e,recovery,release,security,stage_op}_probe.py`、`acceptance_{e2e,recovery}_worker.py`：棘轮合规重构（`app_logging.swallowed()`、`file_cache.read_json()`、夹具文案「您」）。
- `维护记录/架构统一基数.json`：第四项新增 7 条 exempt 登记（内存载荷解析，非文件读）。
- `维护记录/规则守卫对照.md`：`rule_guard_map.py --write` 再生成。
- `维护记录/分支覆盖率基线.json`：98 目标真实重测刷新（含 model_metering 12 决策点）。
- `tests/test_error_codes.py`、`tests/test_secret_status_diagnostics.py`：同步 master 权威版本（契约未变，仅断言对齐现行行为）。

## 4. 测试与基线

- 定向：`python -B -m unittest tests.architecture.test_silent_exception_ratchet tests.architecture.test_unification_ratchet tests.test_copy_rules` 全绿；`tests.test_keyframe_lifecycle_service tests.test_file_origin_provenance` 25/25。
- `run_selftests.py -k`（原失败集 10 文件）：除 `test_round_baselines`（§2.4）外全绿。
- `scripts/branch_coverage_report.py`（98 目标）：全部目标用例通过后写入基线，退出码 0。
- `smoke_test.py`：提交回执为准。
- 全量 `--all --safe`：本轮修复针对上一轮全量暴露的红项；合入 master 后按 §5 在主工作区重跑当次全量。

## 5. 未测／限制

- 探针脚本重构为语义保持型改动（异常处理留痕、JSON 读入口、夹具用字）；E/D/F 取证结论不受影响，F 走查脚本已回归复跑确认。
- `test_round_baselines` 分支红为机制性（状态页仅 master 可写），合入后由合并轮状态页同步核销。
