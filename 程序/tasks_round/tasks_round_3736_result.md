# R3736：A15 随附二进制供应链锁
<!-- round-evidence: {"commit_base": "37d54f35", "credential_hits": 0, "evidence_sha256": "4c47f1553380f1d7", "exit": 0, "failed": 0, "passed": 1, "round": 3736, "tests": "run_selftests.py -k tools_lock"} -->

## 三问

1. 类型：AGENTS §3.9 兼容/供应链轮；只收口随附解释器与 FFmpeg 的真实版本、来源、许可证和摘要。
2. 验证：新增工具锁契约改前 1 红、改后 1/1；`tools_lock --check` 三项通过。
3. 欠账：工具锁漂移清零；Python 包 SBOM、干净安装、ASR 独立环境、更新恢复与签名发布门仍待后续 A15 轮次。

## 事实与修正

- 旧锁声称 Python 3.15.0、SHA256 `727b92…`；实际随包文件为 Python 3.14.7、SHA256 `4942b8…`，PSF Authenticode 有效。锁更新不是只换哈希，同时更正版本并登记官方来源与 PSF-2.0。
- `ffmpeg.exe`、`ffprobe.exe` 为 Gyan 9.0.1 essentials build；二进制未做 Authenticode 签名，SHA256 分别为 `72a489…`、`19202b…`。
- 构建参数含 `--enable-gpl --enable-version3`，原清单“LGPL 构建”不成立；已按 `GPL-3.0-or-later` 更正，不把可自备替换误写成 LGPL 合规证明。

## 实现与验证

- `external_tools.lock.json` 升级为 version 2，三项均含 bytes、version、source、license、sha256。
- `scripts/tools_lock.py` 更新/检查覆盖三项；缺文件、缺锁项、摘要漂移、来源/许可证漂移均拒绝通过，不再因工作树没运行环境而静默跳过。
- `tests/test_tools_lock.py` 固定三项闭包及供应链字段。红测先证明旧实现只锁 Python，改后 1/1。

本轮不生成签名、不宣称发布已签名；无签名的 FFmpeg 风险由哈希锁与后续 SBOM/发布门披露。
