# R4038 修复合并调用方的暂存语义
<!-- round-evidence: {"commit_base": "85b39dc7", "credential_hits": 0, "evidence_sha256": "ff39090353d9eaf1", "exit": 0, "failed": 0, "passed": 25, "round": 4038, "tests": "run_selftests.py -k merge_round"} -->
R4037 已通过出口 CI，旧合并入口因只把元数据传给显式提交而拒绝。改为先精确暂存两个本轮文件，再经原提交器提交完整合并索引。两条分支均有回归，暂存失败直接返回。首次交付时从已验收车道加载本版合并脚本，使用主干工作树和常规出口 CI、检查、锁及钩子。
