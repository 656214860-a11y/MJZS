# R3745：A15 隔离生产解释器闭包
<!-- round-evidence: {"commit_base": "fc77888e", "credential_hits": 0, "evidence_sha256": "61a0d48f59fbe04d", "exit": 0, "failed": 0, "passed": 19, "round": 3745, "tests": "run_selftests.py -k release_runtime distribution_build"} -->

## 三问

1. 类型：AGENTS §3.9 分发兼容轮；只让新建发布副本的 Python 依赖闭包等于生产锁。
2. 验证：运行时策略 4/4、分发构建 15/15；源目录不修改，共享文件不误删，缺 RECORD 拒绝裁剪。
3. 欠账：合入候选生成后的离线/中文空格路径启动、ASR 独立环境和更新恢复仍待 A15 后续轮次。

## 事实与修正

- 共享安装根不是干净发布运行时。只读盘点发现生产锁本身无缺包/错版，但还装有 `annotated-types`、`apted`、`gallery-dl`、`greenlet`、`pip`、`playwright`、`pydantic`、`pydantic-core`、`ruff`、`tree-sitter`、`tree-sitter-python`、`typing-extensions`、`typing-inspection`，共涉及 2292 个 RECORD 文件。
- 这些包同时包含开发工具和未声明传递依赖；把它们加入白名单会掩盖污染。构建器现在只在新输出目录省略其独占文件，不卸载、不清理共享解释器。
- `psutil`、`nvidia-ml-py` 已存在于安装根当前生产锁，因此只读盘点保留；当前功能分支合并时仍须以最终 `requirements.txt` 为唯一口径复验。

## 实现与验证

- `scripts/release_runtime.py` 只读解析精确锁和 dist-info/RECORD，不导入第三方包；缺包、错版、越界 RECORD 或未知包无 RECORD 均失败。
- `scripts/distribution_build.py` 复制前排除未知 distribution 的独占文件，摘要记录裁剪包和文件数；复制后再次验证闭包恰好等于生产锁。
- 同一文件若也被允许包声明，则不会随未知包误删。定向测试 19/19，`git diff --check` 通过。
