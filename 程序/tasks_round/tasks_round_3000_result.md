# R3000 结果：修复轮——离线 ASR 安装链路两处必现缺陷（funasr_onnx 钉版＋Python 版本上限）
<!-- round-evidence: {"commit_base": "6ecbfd5f", "credential_hits": 0, "evidence_sha256": "45c2a538b3f44881", "exit": 0, "failed": 0, "passed": 57, "round": 3000, "tests": "run_selftests.py -k offline_asr"} -->

## 三问

1. **轮次类型**：修复轮（§3.2）。起因：用户实机点麦克风报「语音输入未能启动（离线识别环境未安装）」；排查发现除环境未安装外，安装链路本身有两处必现缺陷，按根因最小改动收口。
2. **测试跑了吗、三个基线过了吗**：跑了。新增 `test_main_rejects_python_above_max`；`run_selftests.py -k offline_asr` 57 条全绿；默认冒烟 8/8；守卫对 Python 3.14 实测直接拒绝（exit 2、不建 venv）；本机已用 CPython 3.12.11＋funasr_onnx 0.4.11 完成真实安装并端到端转写验证（证据见下）。
3. **欠账少了吗**：是。requirements 钉版与 README/bootstrap 版本口径对齐真实可装范围（3.10–3.12）；`data/voice_asr_venv`、`data/voice_models` 属 gitignore 运行数据区，不产生源码欠账。

## 根因（改前失败证据）

| # | 缺陷 | 实测证据 |
|---|---|---|
| 1 | `requirements.txt` 钉 `funasr_onnx==0.4.1`：其 `__init__.py` 无条件 `from .sensevoice_bin import SenseVoiceSmall` → `import torch`；torch 是未声明依赖（2GB+ 级），干净 venv 里 `import funasr_onnx` 必抛 `ModuleNotFoundError`，`bootstrap.verify_imports` 恒失败 | Python 3.12 上依赖装完后 `import numpy, onnxruntime, funasr_onnx, jieba, modelscope` 报 `No module named 'torch'`；PyPI 元数据 `requires_dist` 无 torch |
| 2 | 基座 Python 无上限校验：funasr_onnx 全系列钉 `numpy<=1.26.4`，numpy 1.26.4 仅有 cp310–cp312 预编译轮子；3.13/3.14/3.15 上 pip 回退源码编译，Windows 实测数分钟后 Meson `UnicodeDecodeError` 崩溃 | Python 3.14 跑 bootstrap：pip 选 `numpy-1.26.4.tar.gz` 源码构建失败（exit 3） |

## 本轮交付

| 文件 | 改动 |
|---|---|
| `voice_engine/requirements.txt` | `funasr_onnx==0.4.1` → `==0.4.11`：0.4.11 全包零 torch 引用；`Paraformer`/`Fsmn_vad`/`CT_Transformer` 构造参数（`batch_size`/`device_id`/`quantize`/`intra_op_num_threads`）与调用签名逐文件比对一致；附原因注释 |
| `voice_engine/bootstrap.py` | 新增 `MAX_PYTHON=(3,12)` 与 `main()` 上限守卫：基座 >3.12 直接 `fail`（exit 2）并给中文指引，不再走到 numpy 源码编译；docstring 版本口径同步为 3.10–3.12 |
| `voice_engine/README.md` | 首次使用注释改「Python 3.10–3.12 完整版」，注明 3.13+ 会被 bootstrap 拒绝 |
| `tests/test_offline_asr_engine.py` | `BootstrapTests` 新增 `test_main_rejects_python_above_max`：mock `probe_python` 返回 3.14.7 → `EXIT_ENV_ERROR`＋中文原因 |

## 验证证据

- `python -B run_selftests.py -k offline_asr`：57 条用例 0 红（`test_offline_asr_engine` 38、`test_offline_asr_client` 19）。
- `python -B smoke_test.py`：8/8 通过。
- 守卫实测：worktree 内 `bootstrap.py --python <Python314>` 输出 `{"type":"error","message":"基座 Python 3.14 超出支持范围：离线识别依赖 numpy<=1.26.4 仅提供 Python 3.10–3.12 预编译轮子…"}`，exit 2，未创建 venv。
- 真实安装端到端（主工作区 `程序/data/` 运行数据区，非源码改动）：uv 管理 CPython 3.12.11 建 `data/voice_asr_venv`，venv 内 `funasr_onnx` 0.4.11，三模型下载至 `data/voice_models`（502MB）；`domain.offline_asr_client.acquire({})` 2.4s 到 `ready`；SAPI 合成中文语音（8.46s→16kHz PCM）走 `start/audio/stop` 协议识别出两句带标点文本「你好，这是离线语音识别的测试。」「今天天气不错，我们继续制作剧本。」；`speech_api.missing_reason()` 返回空串，用户侧报错消除。

## 边界与说明

- 本机 venv 内 `funasr_onnx` 系手工升级至 0.4.11；本提交合入后重跑 bootstrap 结果一致（requirements 已对齐）。
- `verify_imports` 未改：0.4.11 下 `import funasr_onnx` 不再需要 torch。
- 修复轮不改阶段行为，REQ/DES 文档（§2.7）不适用；`project_status.md` 轮次头由合并轮在 master 同步。
