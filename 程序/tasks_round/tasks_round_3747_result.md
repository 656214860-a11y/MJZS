# R3747：A15 离线 ASR 独立环境锁
<!-- round-evidence: {"commit_base": "bae0a9f6", "credential_hits": 0, "evidence_sha256": "b3c815c559ca0d23", "exit": 0, "failed": 0, "passed": 93, "round": 3747, "tests": "run_selftests.py -k offline_asr_engine offline_asr_setup dynamic_import_registry"} -->

## 三问

1. 类型：AGENTS §3.9 独立进程兼容轮；只收口离线 ASR venv 的依赖、模型配置和就绪判据。
2. 验证：ASR 引擎 43/43、宿主安装控制器 11/11、动态进程边界 39/39；Windows CPython 3.10 与 3.12 目标轮子闭包均由 pip dry-run 解析通过。
3. 欠账：当前机器无 3.10–3.12 解释器，未伪造真实数百 MB 安装/模型下载；许可证投影、真实安装和模型供应商下载列为后续发布门。

## 事实与修正

- 原 `numpy>=1.26,<3`、`onnxruntime>=1.17,<2` 会随安装时间漂移，不是依赖锁；现固定为 `numpy==1.26.4`、`onnxruntime==1.20.1`。
- 仅固定七个顶层包仍不足：pip 会动态选择约 48 个传递包。新增 `requirements.lock` 固定完整闭包，bootstrap 默认安装该文件；3.10/3.12 分别解析后选择两者兼容的较低版本。
- 原 `models_ready` 只要缓存里任意一个 ONNX 文件就返回真，会把 ASR、VAD、标点模型缺失误报为可用。现在三项锁定模型必须全部存在。
- 模型名称和 revision 原散落在 Python 常量；现由 `models.lock.json` 作为共享机器可读源，环境变量覆盖规则保留。

## 实现与验证

- bootstrap 安装后导入校验补齐 `librosa`、`soundfile`，不再只验证部分依赖。
- 动态进程登记同时覆盖顶层清单、完整锁和模型锁，三份资源随整个 `voice_engine` 分发。
- 目标平台解析使用 Windows x86-64、CPython 3.10/3.12；`jieba` 上游仅提供源码包，验证时先按其源码构建通用 wheel，再完成闭包解析。这是可安装性证据，不替代真实模型下载验收。
