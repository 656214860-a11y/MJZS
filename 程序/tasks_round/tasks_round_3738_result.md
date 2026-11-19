# R3738：A15 SBOM 与正式发布门
<!-- round-evidence: {"commit_base": "827353cd", "credential_hits": 0, "evidence_sha256": "fb698e8e47f47709", "exit": 0, "failed": 0, "passed": 16, "round": 3738, "tests": "run_selftests.py -k sbom distribution_build"} -->

## 三问

1. 类型：AGENTS §3.9 供应链兼容轮；只建立依赖/工具/外部 Skill 的发布清单和许可证门。
2. 验证：SBOM 2/2、分发构建 14/14；未知生产包和许可证为 `NOASSERTION` 的外部 Skill 都有拒绝路径。
3. 欠账：代码签名密钥、隔离生产解释器、ASR 环境和更新恢复仍待后续 A15 轮次；本轮不宣称正式发布就绪。

## 事实与修正

- 分发构建现在生成 CycloneDX 1.5 `sbom.cdx.json` 与 `THIRD_PARTY_NOTICES.txt`，并把二者纳入分发摘要；来源、版本、许可证或工具摘要缺失会直接失败。
- `剧本锻造` 固定上游未提供可确认的再分发许可证，登记为 `NOASSERTION`。普通完整性校验可以通过，但 `release_ready` 必须为假，`distribution_selfcheck --release` 必须阻止正式发布。
- 实际安装根与本功能分支不是同一基线：安装根生产锁已新增 `psutil`、`nvidia-ml-py`，但工具锁尚无 R3736 的 `source` 字段。真实根试构建因此被供应链门拒绝，不能把这种混合基线结果包装成发布验证。
- 已登记 `psutil`、`nvidia-ml-py` 的 BSD-3-Clause 与上游来源；任何其他未登记生产依赖仍失败。

## 实现与验证

- `scripts/sbom.py` 从精确生产锁、二进制工具锁和外部技能哈希生成机器/人工两份清单。
- `scripts/distribution_build.py` 同时验证清单摘要、CycloneDX 格式与发布阻断项；技术完整性 `ok` 和法律/发布资格 `release_ready` 分开表达。
- `scripts/distribution_selfcheck.py` 新增 `--release` 严格门，不影响开发诊断模式。
- 定向测试共 16/16；`git diff --check` 通过。真实发布副本留到隔离运行时建成且分支合并后复验。
