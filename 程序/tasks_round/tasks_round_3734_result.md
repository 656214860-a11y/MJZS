# R3734：A15 分发构建基线复验
<!-- round-evidence: {"commit_base": "c16b9141", "credential_hits": 0, "evidence_sha256": "47cc3f94b4400f23", "exit": 0, "failed": 0, "passed": 0, "round": 3734, "tests": "docs-only"} -->

## 三问

1. 类型：AGENTS §3.10 验证基线轮；修正分发清单事实并在实际安装根构建隔离临时副本。
2. 验证：构建器 13/13；实际根计划 keep 4201、excluded 371608、undecided 0；构建/摘要/排除/随附解释器 `-I` 入口导入全部通过。
3. 欠账：分发闭包基线已绿；Python 工具锁哈希漂移、SBOM/许可证来源清单、ASR 独立环境与更新恢复仍待后续 A15 轮次。

## 事实修正

- `distribution_manifest.md` 开头不再称构建器是“未来工具”：当前 `scripts/distribution_build.py` 已实际消费清单。
- `.gitmodules` 是源码供应链映射，不进运行副本；Skill 内容从已初始化并固定 SHA 的子模块复制。
- 功能工作树不含 `运行环境/`，在该树运行自检会正确报告缺解释器；正式验证必须显式以实际安装根 `D:/漫剧制作助手` 为源，不能把工作树假红解释成发布包缺陷。

## 真实验证

- `run_selftests.py -k distribution_build`：13/13。
- 实际安装根计划：4,201 个保留文件、371,608 个排除文件、0 个未决文件。
- `distribution_selfcheck.run(Path('D:/漫剧制作助手'))`：临时副本校验无问题；不含排除项，逐文件 SHA256 自洽，随附解释器存在，并以 `-I -B` 成功导入 `app_logging`、`diagnostic_capture`、`model_pool`、`desktop`、`app`。
- 工作树根自检的“缺运行环境”失败已保留为环境边界证据，没有复制开发机解释器到 Git 工作树。

## 尚未放行

- `scripts/tools_lock.py --check`：`运行环境/Python/python.exe` 锁值 `727b92…`，当前实际 `4942b8…`，A15 尚不能宣称工具完整性通过。
- `docs/review/发布签名与SBOM方案_T6.md` 仍是未实现方案；许可证、来源和组件摘要还未形成随包 SBOM。
- 离线 ASR venv/model cache 属目标机运行期生成物，尚未在干净隔离环境验证；签名需要外部密钥，继续作为发布门而非伪造通过。

本轮只建立 A15 可复现分发基线，不宣称 A15 完成。
