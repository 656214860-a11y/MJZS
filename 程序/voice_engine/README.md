# voice_engine — 离线语音识别独立运行时

本目录是「漫剧助手」离线语音输入的独立 ASR 子进程引擎。它**不进入主程序随附
运行时**：主程序（零第三方依赖）经 stdio JSON Lines 与
`offline_asr_server.py` 通信；本目录的脚本只在独立 Python 环境（venv）中运行，
依赖见 `requirements.txt`（numpy / onnxruntime / funasr_onnx / jieba / modelscope /
librosa / soundfile）。

## 组成

| 文件 | 作用 |
| --- | --- |
| `offline_asr_server.py` | 常驻引擎：模型常驻内存，FSMN-VAD 逐句断句 → Paraformer ASR → CT-punc，逐句下发 |
| `funasr_config.py` | 模型名/版本配置（可用 `FUNASR_*` 环境变量覆盖） |
| `download_models.py` | ModelScope 模型解析：先 `local_files_only` 命中本地缓存，再在线下载；缓存到 `程序/data/voice_models/`（`VOICE_ASR_MODEL_CACHE` 可覆盖） |
| `bootstrap.py` | 一键创建独立 venv 并安装依赖（仅标准库） |

## 协议（stdio JSON Lines）

主程序 → 引擎：`{"cmd":"start","sample_rate":16000,"hotword":"..."}`、
`{"cmd":"audio","data":"<base64 pcm>"}`、`{"cmd":"stop"}`、`{"cmd":"shutdown"}`。
引擎 → 主程序：`{"type":"ready"}`、`{"type":"log","message":...}`、
`{"type":"sentence","text","start_ms","end_ms"}`、`{"type":"done"}`、
`{"type":"error","message":"中文原因"}`。详见任务书 §4.1。

## 首次使用

```powershell
# 在 程序/ 目录下，用系统 Python（建议 3.10+ 完整版）创建独立环境并装依赖
python voice_engine/bootstrap.py --python <python.exe路径>
# 产物：程序/data/voice_asr_venv/  与  程序/data/voice_models/
# 两者都在 data/ 用户数据区，升级安装不会覆盖。
```

模型（Paraformer-large + FSMN-VAD + CT-punc，约 500MB）在引擎首次加载时自动
从 ModelScope 下载到 `data/voice_models/`；之后 `local_files_only` 命中不再联网。
也可单独预下载：`python -m voice_engine.download_models --cache <目录>`。

## 许可与署名

- 引擎架构移植/改写自 **VocoType（vocotype-cli）**，版权归原作者，按
  **Apache License 2.0** 授权（全文见 <https://www.apache.org/licenses/LICENSE-2.0>）。
  移植范围：`funasr_config.py`（模型配置）、`download_models.py`（缓存解析）、
  `FunASRServer` 的并行加载/内存清理/ONNX 加载要点（`offline_asr_server.py`）。
- 识别模型为 FunASR / ModelScope 发行的 ONNX 模型
  （Paraformer-large、FSMN-VAD、CT-Transformer  punctuation），
  许可归属以 ModelScope/FunASR 官方页面为准；模型二进制不进 Git。
