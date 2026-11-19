# 发布包签名与 SBOM 方案（T6，先出方案待批准）

- 日期：2026-11-19｜状态：**SBOM 已实现；发布签名待外部密钥/证书**
- 范围：发布包（`distribution_build.py` 产物）的签名验证与物料清单；不动发布流程、不加运行时依赖。

## 1. 目标与非目标

- 目标：发布副本可验真（谁打的包、内容未被换）、组件可追溯（SBOM 清单）。
- 非目标：不做在线自动更新签名校验；不引入第三方运行时库；不做代码签名证书采购（证书选型需用户决策）。

## 2. SBOM（物料清单）

- 产物：`sbom.cdx.json`（CycloneDX 1.5 JSON）＋ `THIRD_PARTY_NOTICES.txt`（人读清单），由现有分发构建器写入输出根并纳入逐文件 SHA256。
- 内容：主程序精确生产依赖、离线 ASR 独立环境的完整传递锁（标为 optional）、随附解释器/FFmpeg 工具锁，以及 gitlink 技能包的来源仓库、固定提交和树哈希。逐文件完整性由同包 `分发清单.json` 负责，不在 SBOM 重复生成巨型文件组件表。
- 生成器：`scripts/sbom.py`（stdlib-only），`distribution_build.py` 默认调用；`distribution_selfcheck --release` 校验 SBOM 并阻断 `NOASSERTION`。
- 已采用：CycloneDX 1.5；产品 Python 依赖按包级，随附二进制按文件 SHA256，gitlink 包按包级＋固定提交/树哈希，避免重复一份巨型文件清单。

## 3. 发布包签名

- 方案 A（最小）：分发目录产出 `SHA256SUMS`＋`SHA256SUMS.sig`（GPG detached 签名）。构建机持有构建私钥；用户用公开的指纹验证。零依赖（gpg 只在构建机需要）。
- 方案 B（更顺手）：`minisign`/`signify` 同款——单文件公钥放进 `安装信息.json` 旁，验证工具一行命令。
- 方案 C（最重）：Windows Authenticode 代码签名——需要 OV/EV 证书成本与年续费，首期不建议。
- 建议：**先 A**（GPG 或 minisign，构建机一条命令），Authenticode 待订阅商业化上线再评估。
- 验证入口：`dev.py release` 或 `distribution_selfcheck.py --verify-sig` 读取 `SHA256SUMS.sig` 与公钥指纹比对。

## 4. 与现有机制的关系

- `external_tools.lock.json`（R2569）已钉外部工具哈希——SBOM 直接复用其数据，不重复登记。
- `skill_package_pins`（R2538）已钉外部技能包提交与树哈希——SBOM 引用其登记值。
- `tools_lock` 启动自检保持"只告警不阻断"；签名验证也只放发布与自检通道，不进启动路径（规则 33）。
- ASR 供应链登记在 `voice_engine/supply_chain.lock.json`，其包名集合必须与 `requirements.lock` 完全相等；少登记、多登记或非精确版本均拒绝生成 SBOM。

## 5. 剩余发布门

1. `剧本锻造` 上游固定提交没有 LICENSE；源码工作树继续以 `NOASSERTION` 审计，正式分发清单已排除该目录。取得授权前不得重新纳入发布副本。
2. 签名方案与密钥保管仍需真实构建机资源；当前不生成假签名。首发建议 minisign/GPG，商业发行再评估 Authenticode。
