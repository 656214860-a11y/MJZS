# R3002 合并轮结果
<!-- round-evidence: {"commit_base": "33a36a9c", "credential_hits": 0, "evidence_sha256": "5cfe67bdaf3d61e0", "exit": 0, "failed": 0, "passed": 0, "round": 3002, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/fix-asr-venv-pin` 到 master。
- 说明：R3000 离线ASR安装链路修复：funasr_onnx钉版0.4.11（0.4.1的__init__无条件import torch致干净环境装不上）＋bootstrap基座Python上限3.12守卫与README版本口径
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
