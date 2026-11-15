# R2538 结果
<!-- round-evidence: {"commit_base": "490d4177", "credential_hits": 0, "evidence_sha256": "372d15e436b3004e", "exit": 0, "failed": 0, "passed": 116, "round": 2538, "tests": "run_selftests.py -k gate_selfaudit type_check_baseline skill_package_pins fault_injection_chain environment_check server_pre_receive round_evidence commit_round test_selftests"} -->

1. 轮次类型：功能轮（工程闸门落地清单批次 4：G2／G5／G6／G7／G8／E1／E2／E3），附带一处 AGENTS 阈值文字同步。
2. 测试：定向 `test_gate_selfaudit`、`test_type_check_baseline`、`test_skill_package_pins`、`test_fault_injection_chain`、`test_environment_check`、`test_server_pre_receive`、`test_round_evidence`、`test_commit_round`、`test_selftests` 全绿；证据文件 `tasks_round/evidence/R2538.json`。`tests/test_selftests.py` 两处字面量 7／8 改为随 `FULL_SAFE_ROUND_INTERVAL` 取值（等强，契约有意变更）。架构门禁里 `test_round_number_continuous` 在工作分支上必红（状态页只能在 master 更新），与本轮无关。断言未动。
3. 欠账：无新增。后台全量在本轮开工时已有 25 个源码轮次无凭据，且 HEAD d382166 上一次后台全量红 13 个文件（含 `test_static_names`，已由 R2527 修复 `master_import_service.py` 缺 import）；合入后会按新阈值自动补跑，需另行看结果。

## 改动

- G2：`run_selftests.FULL_SAFE_ROUND_INTERVAL` 8→5、`FULL_SAFE_RISK_GRACE` 3→2（依据批次 3 基线：7 天内被修复的轮次约 69%；同步 AGENTS §5、runbook §4，`test_round_baselines` 仅改 docstring，断言未动）。
- G5：`维护记录/基准脚本/server_hooks/pre-receive` 与 `test_server_pre_receive`；`.gitattributes` 固定 LF。未连接服务器，部署命令在脚本头，由用户执行。
- G6：`scripts/typecheck_baseline.py`、`维护记录/类型检查基线.json`（pyright 1.1.414 basic，141 个模块、3023 处，只许减少）、`test_type_check_baseline`。生产代码没有未定义变量类错误。
- G7：`tests/architecture/test_gate_selfaudit.py`（路径权威、删除权威、静默异常、秘密出口、分层）。
- G8：`tests/test_fault_injection_chain.py`。范围说明：计划写“从 `stage_handler_registry.start()` 驱动”，实际链路取计量（`chat_metered`）→适配器分类→`emit_verified_completion`，未起整套阶段编排（那需要 Tk 与整页桩）；不变量见测试。
- E1：`scripts/skill_package_pins.py`、`维护记录/外部技能包哈希.json`（3 个 gitlink 包：提交＋git 内容树哈希，比逐文件 sha256 更稳，不受换行符影响）、`test_skill_package_pins`。
- E2：`environment_check.MIN_VERSIONS`（FFmpeg／FFprobe ≥4.4、Blender ≥3.6，建议值）与 `apply_versions`；仅「环境自检」按钮探测版本，`run_checks()` 默认不启动程序。
- E3：`round_evidence.stamp_result`，`dev.py commit` 在结果文件标题行后写一行机器可读证据头。
