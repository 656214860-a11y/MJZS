# R3756：A15 无许可证组件退出正式分发
<!-- round-evidence: {"commit_base": "92457297", "credential_hits": 0, "evidence_sha256": "d166884fdaeb8a44", "exit": 0, "failed": 0, "passed": 21, "round": 3756, "tests": "run_selftests.py -k sbom distribution_build"} -->

## 三问

1. 类型：AGENTS §3.9 分发兼容轮；不删除源码审计材料，只把无再分发授权的外部 Skill 从正式副本收口。
2. 验证：SBOM 3/3、分发构建 18/18；排除后组件不进入发布 SBOM，`release_ready` 转为真。
3. 欠账：代码签名证书/私钥和真实 ASR 模型下载仍需外部资源，作为发布门保留；不伪造签名或模型验收。

## 事实与修正

- 2026-11-19 当前固定提交的 `剧本锻造` 没有 LICENSE 或可确认的再分发授权。继续随包发布有法律风险，不能仅靠 `NOASSERTION` 提示后放行。
- 仓库中的 gitlink 继续保留，便于开发审计和未来取得授权；`distribution_manifest.md` 精确排除其正式副本路径。
- SBOM 现在按实际入包文件筛选 Skill。源码工作树物料审计仍能看到 `NOASSERTION`，正式副本则不会虚列一个未携带组件。

## 真实副本证据

- 当前分支程序文件与真实随附运行时组合，在中文和空格目录构建 2,770 文件、293,416,946 字节；摘要、排除项和必需入口校验通过。
- 构建从副本裁剪 15 个非生产 distribution、2,330 个独占文件；副本解释器 `-I -B` 下只发现锁定六包，主要入口 `app_logging/diagnostic_capture/model_pool/desktop/app` 离线导入通过。
- 上述真实构建发生在排除规则落地前，唯一发布阻断正是 `剧本锻造`；新增隔离用例证明同一组件排除后 SBOM 无该条目且 `release_ready=True`。最终合入候选将在 A16 重建复验。

A15 的可在仓库内完成项已收口；外部签名和真实模型供应商验证保持显式发布门。
