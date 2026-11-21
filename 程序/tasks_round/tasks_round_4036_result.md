# R4036 集成提交器中断回归
<!-- round-evidence: {"commit_base": "bf609f0c", "credential_hits": 0, "evidence_sha256": "037396e76ad56087", "exit": 0, "failed": 0, "passed": 27, "round": 4036, "tests": "run_selftests.py -k commit_round"} -->
将全部 14 个接续场景归入原提交器测试模块，与原 13 项回归一起通过同一入口发现。回执直接从受锁文件流解析，重验保留所有原场景；沿用既有目录治理基线。
