# R4028 开发规格与审查流程接入
<!-- round-evidence: {"commit_base": "6e3300c8", "credential_hits": 0, "evidence_sha256": "a0d6083c55b5204d", "exit": 0, "failed": 0, "passed": 0, "round": 4028, "tests": "docs-only"} -->
开发工具文档轮。仅取已验收的 6e3300c8 中 .agents/skills/spec-context-review 与 开发者工具/AI开发流程 两个目录，从 master 独立建车道。复用 GitHub Spec Kit 三模板及许可证、Superpowers 子代理技能及许可证，保留 ADR-0006 原 REQ/DES 与轮次机制。
上轮主控在相同文件内容上完成两套上游对象比对（4/4、16/16）、本地链接解析、task-brief 单任务抽取、review-package 和 R4027 回放。此轮独立车道运行默认冒烟。架构检查由正式出口 CI 执行，未运行全量。本轮仅合入上述工具及必要轮次记录，排除 R4026 暂存、R4027 提交器修改。
归属核对：同路径同 blob 已在 R4025 引入；车道快进至原 R4025，保留原提交与审查历史，并用本轮独立凭据收口，避免重复添加。默认冒烟实测 9/9。
