# R4623 结果：C17 统一扫描排除集合至 `tests/architecture/_scan.py`
<!-- round-evidence: {"commit_base": "704373351", "credential_hits": 0, "evidence_sha256": "c8d505c195cbd5da", "exit": 0, "failed": 0, "passed": 14, "round": 4623, "tests": "run_selftests.py -k static_hygiene coverage_baseline"} -->

1. **轮次类型**：架构治理／单源重构轮（卡 C17，分支 `codex/opt-c17-scan-excludes`，工作树 `.wt/opt_c17`）。
   - 在 `tests/architecture/_scan.py` 提取共享基集 `NON_CODE_EXCLUDED_PARTS`（不含 `tests`，供全仓静态卫生扫描与生产扫描共用），并使 `EXCLUDED_PARTS = NON_CODE_EXCLUDED_PARTS | frozenset({"tests"})`。
   - 将 16 个 `tests/architecture/` boundary/hygiene 测试及 `scripts/coverage_report.py` 中共 18 处重复排除集合／内联 `'voice_asr_venv'` 判断统一改为引用 `_scan.py`（同时将 5 处误用绝对 `path.parts` 改为 `path.relative_to(ROOT).parts`，消除在 `.wt/` 工作树下被 `.wt` 排除项误跳过的隐患）。
   - 在 `tests/architecture/test_static_hygiene.py` 追加 `ScanExcludesSingleSourceTests`（3 条单测，先红后绿）防回归；未动任何既有测试断言。
2. **测试与三基线**：
   - `smoke_test.py`：9/9 通过（exit 0）。
   - `smoke_test.py --architecture`：717/717 通过（exit 0，259.8s）。
   - `run_selftests.py -k boundary coverage static_hygiene`：100 个测试文件 / 387 条用例全过，0 跳过（exit 0，41.4s）。
   - 覆盖率／模块规模／结构三基线未放宽、未弱化；`scripts/coverage_report.py` 与 `_scan.production_runtime_files()` 严格共享同一口径。
3. **欠账变化**：
   - 消除 `tests/architecture/` 与 `scripts/coverage_report.py` 中 18 处重复扫描排除集合（归零，并加 `ScanExcludesSingleSourceTests` 门禁防止复发）。
   - 无新增欠账。
