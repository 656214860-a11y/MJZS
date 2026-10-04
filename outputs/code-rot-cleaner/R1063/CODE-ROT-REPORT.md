# Code Rot Report

> **REPORT READY** — 生产源码未修改；仅新增诊断证据、轮次报告并更新轮次元数据。未执行删除验证或项目测试。

## 中文结论与下一步

扫描 562 个源码文件。自动整文件候选经人工复核全部保留；另有以下三个符号待验证，不能删除其所在模块。

| ID | 符号及位置 | 行数 | UTF-8 字节（LF 归一化） |
|---|---|---:|---:|
| CRT-026 | idea_chat.py:459 project_document_kind | 25 | 1349 |
| CRT-027 | projects.py:316 Projects.remove_internal_links | 19 | 1107 |
| CRT-028 | workflow_process_registry.py:70 cancel_process_slot_request | 10 | 334 |

三个精确符号名在允许扫描的已跟踪源码、测试、文档中均仅发现定义，未发现调用或字符串引用。动态调用、外部使用和被排除目录不在此结论覆盖范围；总计 54 行、2790 字节，只是潜在删除量，不是已释放空间。

### 待批准的副本验证（尚未执行）

仅建立程序源码、测试和必要静态资源的临时副本，不复制用户数据、private、配置、日志或运行环境。先核对测试所需夹具；若依赖受保护数据则停止并报告，不放宽边界。在副本程序目录运行以下命令建立基线，然后只移除上述三个函数体及定义，再运行同组命令对比：

```powershell
& 'D:/漫剧制作助手/运行环境/Python/python.exe' -B run_selftests.py --safe -k idea_chat projects workflow_process_registry
& 'D:/漫剧制作助手/运行环境/Python/python.exe' -B smoke_test.py
& 'D:/漫剧制作助手/运行环境/Python/python.exe' -B smoke_test.py --architecture
```

保留 projects.py 的 remove_project_link_node 导入及其他调用；保留项目级取消、队列、所有测试及断言。此方案为三个符号的批次验证，不冒称逐符号独立证明。技能自带整文件删除证明器不适用于此方案。通过后仍需再次确认真实源码的精确删除范围；失败则保留并分析，不削弱测试。

Project: `D:\漫剧制作助手\程序`  
Generated: `2026-10-04T20:33:13Z`

## Executive summary

| Result | Candidates | LOC | Size |
|---|---:|---:|---:|
| SAFE TO REMOVE | 0 | 0 | 0 B |
| REVIEW | 3 | 54 | 2.7 KB |
| KEEP | 25 | 2,294 | 105.7 KB |

## Ranked candidates

| ID | Status | Category | Subject | Confidence | Risk | LOC | Proof |
|---|---|---|---|---|---|---:|---|
| CRT-001 | **KEEP** | orphan-file | `asset_reference_import.py` | medium | medium | 115 | 动态入口：ui_plugin_registry.py:11、desktop.py:5800。 |
| CRT-002 | **KEEP** | orphan-file | `blender_previs_template.py` | medium | medium | 64 | 运行模板：previs_batch_service.py:41 明确要求复用，不按导入模块判定。 |
| CRT-003 | **KEEP** | orphan-file | `desktop_launcher.py` | medium | medium | 28 | 桌面启动入口：app.py:1449 动态加载。 |
| CRT-004 | **KEEP** | orphan-file | `script_skill_report.py` | medium | medium | 79 | script_contract.py:1099/1105/1137 动态 import_module 调用。 |
| CRT-005 | **KEEP** | orphan-file | `storyboard_catalog.py` | medium | medium | 17 | 仍有 asset_context.py:54 等调用，且兼容窗口未结束。 |
| CRT-006 | **KEEP** | orphan-file | `tests/architecture/_canary/audit20_cache_violation.py` | medium | medium | 2 | 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。 |
| CRT-007 | **KEEP** | orphan-file | `tests/architecture/_canary/audit21_platform_violation.py` | medium | medium | 2 | 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。 |
| CRT-008 | **KEEP** | orphan-file | `tests/architecture/_canary/audit22_violation.py` | medium | medium | 2 | 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。 |
| CRT-009 | **KEEP** | orphan-file | `tests/architecture/_canary/audit24_violation.py` | medium | medium | 2 | 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。 |
| CRT-010 | **KEEP** | orphan-file | `tests/architecture/_canary/audit25_event_violation.py` | medium | medium | 1 | 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。 |
| CRT-011 | **KEEP** | orphan-file | `tests/architecture/_canary/audit26_violation.py` | medium | medium | 2 | 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。 |
| CRT-012 | **KEEP** | orphan-file | `tests/architecture/_canary/audit27_secret_violation.py` | medium | medium | 13 | 安全审计 canary：test_secret_sink_audit.py:15,89。 |
| CRT-013 | **KEEP** | orphan-file | `tests/performance_contract.py` | medium | medium | 15 | 测试契约：tests/test_baseline_history.py:13 导入。 |
| CRT-014 | **KEEP** | orphan-file | `tests/skip_reasons.py` | medium | medium | 21 | 跳过原因常量：tests/test_app_icon.py:8 等导入。 |
| CRT-015 | **KEEP** | orphan-file | `维护记录/基准脚本/benchmark_history.py` | medium | medium | 100 | 维护辅助库：基准_启动与页面.py:13 导入。 |
| CRT-016 | **KEEP** | orphan-file | `维护记录/基准脚本/install_git_hooks.py` | medium | medium | 37 | AGENTS.md §2.6 指定的 hooks 安装 CLI。 |
| CRT-017 | **KEEP** | orphan-file | `维护记录/基准脚本/round_claim.py` | medium | medium | 373 | AGENTS.md §2.5 指定的中央轮次 CLI，本轮使用。 |
| CRT-018 | **KEEP** | orphan-file | `维护记录/基准脚本/round_gate.py` | medium | medium | 55 | 维护门禁 CLI，命令行操作不要求静态入站导入；未证明已废弃，保守保留。 |
| CRT-019 | **KEEP** | orphan-file | `维护记录/基准脚本/worktree_ledger.py` | medium | medium | 220 | AGENTS.md §2.5 指定的 worktree 台账 CLI。 |
| CRT-020 | **KEEP** | orphan-file | `维护记录/基准脚本/基准_内存长跑.py` | high | low | 357 | 独立内存基准 CLI，文件内提供手动用法；零导入不等于废弃。 |
| CRT-021 | **KEEP** | orphan-file | `维护记录/基准脚本/基准_启动与页面.py` | medium | medium | 202 | 独立启动性能基准 CLI。 |
| CRT-022 | **KEEP** | orphan-file | `维护记录/基准脚本/基准_长列表.py` | medium | medium | 122 | 独立长列表性能基准 CLI。 |
| CRT-023 | **KEEP** | orphan-file | `维护记录/基准脚本/扫描_代码质量.py` | high | low | 125 | 独立静态扫描维护脚本；旧测试目录识别值得另轮评估，不能据此删除。 |
| CRT-024 | **KEEP** | orphan-file | `维护记录/基准脚本/探针_阶段门禁端到端.py` | medium | medium | 151 | 独立阶段门禁端到端探针 CLI。 |
| CRT-025 | **KEEP** | orphan-file | `附加工具/ComfyUI_批量首帧_Klein4B/batch_frames.py` | medium | medium | 189 | 启动批量首帧.pyw:5 直接导入。 |
| CRT-026 | **REVIEW** | unused-export | `idea_chat.project_document_kind` | medium | medium | 25 | 仅静态无引用证据，尚未获准执行副本删除验证；不得直接清理。 |
| CRT-027 | **REVIEW** | unused-export | `Projects.remove_internal_links` | medium | medium | 19 | 仅静态无引用证据，尚未获准执行副本删除验证；不得直接清理。 |
| CRT-028 | **REVIEW** | unused-export | `workflow_process_registry.cancel_process_slot_request` | medium | medium | 10 | 仅静态无引用证据，尚未获准执行副本删除验证；不得直接清理。 |

## Evidence by candidate

### CRT-001 — KEEP

- Location: `asset_reference_import.py`
- Category: `orphan-file`
- Potential size: 115 LOC / 8.0 KB
- Status reason: 动态入口：ui_plugin_registry.py:11、desktop.py:5800。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: asset_reference_import, asset_reference_import.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-002 — KEEP

- Location: `blender_previs_template.py`
- Category: `orphan-file`
- Potential size: 64 LOC / 3.3 KB
- Status reason: 运行模板：previs_batch_service.py:41 明确要求复用，不按导入模块判定。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: blender_previs_template, blender_previs_template.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-003 — KEEP

- Location: `desktop_launcher.py`
- Category: `orphan-file`
- Potential size: 28 LOC / 935 B
- Status reason: 桌面启动入口：app.py:1449 动态加载。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: desktop_launcher, desktop_launcher.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-004 — KEEP

- Location: `script_skill_report.py`
- Category: `orphan-file`
- Potential size: 79 LOC / 3.6 KB
- Status reason: script_contract.py:1099/1105/1137 动态 import_module 调用。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: script_skill_report.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-005 — KEEP

- Location: `storyboard_catalog.py`
- Category: `orphan-file`
- Potential size: 17 LOC / 869 B
- Status reason: 仍有 asset_context.py:54 等调用，且兼容窗口未结束。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: storyboard_catalog.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-006 — KEEP

- Location: `tests/architecture/_canary/audit20_cache_violation.py`
- Category: `orphan-file`
- Potential size: 2 LOC / 100 B
- Status reason: 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: audit20_cache_violation, audit20_cache_violation.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-007 — KEEP

- Location: `tests/architecture/_canary/audit21_platform_violation.py`
- Category: `orphan-file`
- Potential size: 2 LOC / 33 B
- Status reason: 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: audit21_platform_violation, audit21_platform_violation.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-008 — KEEP

- Location: `tests/architecture/_canary/audit22_violation.py`
- Category: `orphan-file`
- Potential size: 2 LOC / 33 B
- Status reason: 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: audit22_violation, audit22_violation.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-009 — KEEP

- Location: `tests/architecture/_canary/audit24_violation.py`
- Category: `orphan-file`
- Potential size: 2 LOC / 64 B
- Status reason: 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: audit24_violation, audit24_violation.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-010 — KEEP

- Location: `tests/architecture/_canary/audit25_event_violation.py`
- Category: `orphan-file`
- Potential size: 1 LOC / 53 B
- Status reason: 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: audit25_event_violation, audit25_event_violation.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-011 — KEEP

- Location: `tests/architecture/_canary/audit26_violation.py`
- Category: `orphan-file`
- Potential size: 2 LOC / 54 B
- Status reason: 架构审计 canary：test_coverage_audit_ratchet.py:11,81 按目录发现。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: audit26_violation, audit26_violation.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-012 — KEEP

- Location: `tests/architecture/_canary/audit27_secret_violation.py`
- Category: `orphan-file`
- Potential size: 13 LOC / 261 B
- Status reason: 安全审计 canary：test_secret_sink_audit.py:15,89。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: audit27_secret_violation, audit27_secret_violation.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-013 — KEEP

- Location: `tests/performance_contract.py`
- Category: `orphan-file`
- Potential size: 15 LOC / 524 B
- Status reason: 测试契约：tests/test_baseline_history.py:13 导入。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: performance_contract, performance_contract.py, tests/performance_contract, tests/performance_contract.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-014 — KEEP

- Location: `tests/skip_reasons.py`
- Category: `orphan-file`
- Potential size: 21 LOC / 1.1 KB
- Status reason: 跳过原因常量：tests/test_app_icon.py:8 等导入。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: skip_reasons, skip_reasons.py, tests/skip_reasons, tests/skip_reasons.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-015 — KEEP

- Location: `维护记录/基准脚本/benchmark_history.py`
- Category: `orphan-file`
- Potential size: 100 LOC / 4.1 KB
- Status reason: 维护辅助库：基准_启动与页面.py:13 导入。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: benchmark_history, benchmark_history.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-016 — KEEP

- Location: `维护记录/基准脚本/install_git_hooks.py`
- Category: `orphan-file`
- Potential size: 37 LOC / 1.1 KB
- Status reason: AGENTS.md §2.6 指定的 hooks 安装 CLI。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: install_git_hooks, install_git_hooks.py, 维护记录/基准脚本/install_git_hooks, 维护记录/基准脚本/install_git_hooks.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-017 — KEEP

- Location: `维护记录/基准脚本/round_claim.py`
- Category: `orphan-file`
- Potential size: 373 LOC / 16.2 KB
- Status reason: AGENTS.md §2.5 指定的中央轮次 CLI，本轮使用。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: round_claim, round_claim.py, 维护记录/基准脚本/round_claim, 维护记录/基准脚本/round_claim.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-018 — KEEP

- Location: `维护记录/基准脚本/round_gate.py`
- Category: `orphan-file`
- Potential size: 55 LOC / 2.5 KB
- Status reason: 维护门禁 CLI，命令行操作不要求静态入站导入；未证明已废弃，保守保留。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: round_gate, round_gate.py, 维护记录/基准脚本/round_gate, 维护记录/基准脚本/round_gate.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-019 — KEEP

- Location: `维护记录/基准脚本/worktree_ledger.py`
- Category: `orphan-file`
- Potential size: 220 LOC / 10.2 KB
- Status reason: AGENTS.md §2.5 指定的 worktree 台账 CLI。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: worktree_ledger, worktree_ledger.py, 维护记录/基准脚本/worktree_ledger, 维护记录/基准脚本/worktree_ledger.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-020 — KEEP

- Location: `维护记录/基准脚本/基准_内存长跑.py`
- Category: `orphan-file`
- Potential size: 357 LOC / 15.8 KB
- Status reason: 独立内存基准 CLI，文件内提供手动用法；零导入不等于废弃。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability.

### CRT-021 — KEEP

- Location: `维护记录/基准脚本/基准_启动与页面.py`
- Category: `orphan-file`
- Potential size: 202 LOC / 7.7 KB
- Status reason: 独立启动性能基准 CLI。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: 基准_启动与页面, 基准_启动与页面.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-022 — KEEP

- Location: `维护记录/基准脚本/基准_长列表.py`
- Category: `orphan-file`
- Potential size: 122 LOC / 6.0 KB
- Status reason: 独立长列表性能基准 CLI。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: 基准_长列表, 基准_长列表.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-023 — KEEP

- Location: `维护记录/基准脚本/扫描_代码质量.py`
- Category: `orphan-file`
- Potential size: 125 LOC / 4.6 KB
- Status reason: 独立静态扫描维护脚本；旧测试目录识别值得另轮评估，不能据此删除。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability.

### CRT-024 — KEEP

- Location: `维护记录/基准脚本/探针_阶段门禁端到端.py`
- Category: `orphan-file`
- Potential size: 151 LOC / 7.4 KB
- Status reason: 独立阶段门禁端到端探针 CLI。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: 探针_阶段门禁端到端, 探针_阶段门禁端到端.py, 维护记录/基准脚本/探针_阶段门禁端到端, 维护记录/基准脚本/探针_阶段门禁端到端.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-025 — KEEP

- Location: `附加工具/ComfyUI_批量首帧_Klein4B/batch_frames.py`
- Category: `orphan-file`
- Potential size: 189 LOC / 11.2 KB
- Status reason: 启动批量首帧.pyw:5 直接导入。
- Evidence: No resolved static inbound import was found. The file is not a detected package or conventional entry point. Repository text contains possible string/name references: batch_frames, batch_frames.py.
- Caveats: Dynamic loading, reflection, external consumers, or incomplete framework detection can hide reachability. Possible string reachability prevents high-confidence deletion.

### CRT-026 — REVIEW

- Location: `idea_chat.py:459`
- Category: `unused-export`
- Potential size: 25 LOC / 1.3 KB
- Status reason: 仅静态无引用证据，尚未获准执行副本删除验证；不得直接清理。
- Evidence: Supplementary AST and tracked-source/text reference scan found only the definition of project_document_kind, lines 459-483.
- Caveats: Public function: dynamic/external consumers remain possible. Symbol-only proposal; never delete its containing module. No removal proof executed.

### CRT-027 — REVIEW

- Location: `projects.py:316`
- Category: `unused-export`
- Potential size: 19 LOC / 1.1 KB
- Status reason: 仅静态无引用证据，尚未获准执行副本删除验证；不得直接清理。
- Evidence: Supplementary AST and tracked-source/text reference scan found only the definition of remove_internal_links, lines 316-334. Projects.delete uses recycle_paths instead.
- Caveats: Public method may have external consumers. Keep shared remove_project_link_node import: still used at line 360. No removal proof executed.

### CRT-028 — REVIEW

- Location: `workflow_process_registry.py:70`
- Category: `unused-export`
- Potential size: 10 LOC / 334 B
- Status reason: 仅静态无引用证据，尚未获准执行副本删除验证；不得直接清理。
- Evidence: Supplementary AST and tracked-source/text reference scan found only the definition of cancel_process_slot_request, lines 70-79.
- Caveats: Keep live project-level cancellation and queue functions. Public API may have external consumers. No removal proof executed.

## Cleanup approval checklist

No cleanup has been applied. To continue, select exact candidate IDs and review their paths, evidence, proof, and residual risk. Manifest or lockfile changes require separate explicit approval.

```text
Approved candidate IDs: ____________________
Approved files / manifest entries: __________
Approved verification commands: _____________
```

## Scope and limitations

- Scanned 562 source files, 123,183 LOC, 6.1 MB.
- Discovery used the bundled scanner with an in-memory git-tracked allowlist walker, excluding private, episode, writing, configuration, logs, data, assets, runtime, caches and report histories. Supplemental symbol reference checking included tracked Markdown histories. No user project data was read.
- The original scanner summary describes 25 file candidates only; three manually appended Python symbol candidates add 54 LOC and 2790 normalized UTF-8 bytes. All three require symbol-level disposable-copy proof; bundled whole-file removal is not appropriate.
- Static analysis cannot prove absence of dynamic, reflective, operational, platform-specific, or external use.
- JavaScript/TypeScript and Python import resolution is intentionally conservative and does not implement every alias or framework convention.
- Unused dependencies and exports are leads only until project-native tooling and focused proof support removal.
- No project code, package command, or dependency was executed by this scanner.
