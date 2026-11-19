# R3753：A15 ASR 可选环境供应链投影
<!-- round-evidence: {"commit_base": "adcc27f3", "credential_hits": 0, "evidence_sha256": "b9348e4effb9dfa6", "exit": 0, "failed": 0, "passed": 58, "round": 3753, "tests": "run_selftests.py -k sbom distribution_build dynamic_import_registry"} -->

## 三问

1. 类型：AGENTS §3.9 供应链兼容轮；把独立 ASR 环境纳入同一 SBOM，不新增第二套清单生成器。
2. 验证：SBOM 3/3、分发构建 16/16、动态入口 39/39；完整锁与许可证登记集合必须逐项相等。
3. 欠账：模型文件按需下载且不随包，真实模型供应商条款/下载验收仍是发布门；Skill `剧本锻造` 许可证仍阻断正式发布。

## 事实与修正

- 主程序运行时和 ASR venv 是两个隔离环境，但都属于产品能力。旧 SBOM 只列主程序六包，会遗漏 ASR 的 47 个传递包。
- 新登记基于 2026-11-19 对锁定版本的 PyPI 元数据复核，统一保存 SPDX 风格许可证标识；来源使用版本化 PyPI 页面，不依赖安装时动态查询。
- 文档原称 SBOM 含全部 `.py` 文件摘要，实际逐文件摘要属于 `分发清单.json`。已更正职责，避免两个清单重复且漂移。

## 实现与验证

- `voice_engine/supply_chain.lock.json` 登记 47 个精确包许可证和版本化来源模板；包名规范化后必须与 `requirements.lock` 完全闭合。
- CycloneDX 条目标 `scope=optional` 和独立 venv 属性；人读 notices 同步包含这些组件。
- 当前源码生成 59 个组件，其中 optional ASR 47 个；唯一 `NOASSERTION` 仍是 `剧本锻造`，没有被新登记掩盖。
