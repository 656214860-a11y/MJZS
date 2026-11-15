# 发布包签名与 SBOM 方案（T6，先出方案待批准）

- 日期：2026-11-15｜状态：**方案，未实现**
- 范围：发布包（`distribution_build.py` 产物）的签名验证与物料清单；不动发布流程、不加运行时依赖。

## 1. 目标与非目标

- 目标：发布副本可验真（谁打的包、内容未被换）、组件可追溯（SBOM 清单）。
- 非目标：不做在线自动更新签名校验；不引入第三方运行时库；不做代码签名证书采购（证书选型需用户决策）。

## 2. SBOM（物料清单）

- 产物：`sbom.json`（CycloneDX 1.5 JSON）＋ `sbom.txt`（人读清单），随分发包输出到 `dist/`。
- 内容：随附解释器 `运行环境/Python`（版本与哈希，复用 `external_tools.lock.json` 数据）、全部产品 `.py` 的相对路径＋sha256、gitlink 技能包的来源仓库与固定提交（读 `维护记录/外部技能包哈希.json`）、ffmpeg 等外部工具条目。
- 生成器：`scripts/sbom.py`（stdlib-only），`distribution_build.py` 末尾可选调用；`distribution_selfcheck` 校验 `sbom.json` 与清单一致。
- 决策点：①格式选 CycloneDX（SPDX 亦可，CycloneDX JSON 生态更顺手）；②gitlink 包列到包级还是文件级——建议包级＋固定提交，文件级清单会让 SBOM 体积×10。

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

## 5. 待用户拍板

1. SBOM 粒度：包级 vs 文件级（建议混合：产品文件逐文件、外部包到包级）。
2. 签名方案 A/B/C 选型与密钥保管位置（构建机本地 vs 服务器）。
3. 是否把 SBOM/签名挂进 `distribution_build.py` 默认流程还是先独立脚本。
