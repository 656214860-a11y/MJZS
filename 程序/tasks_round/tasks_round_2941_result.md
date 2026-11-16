# R2941 结果：语音离线化·轮1——独立离线 ASR 子进程引擎 + 模型自动下载
<!-- round-evidence: {"commit_base": "0581308b", "credential_hits": 0, "evidence_sha256": "d63f3f80f604924f", "exit": 0, "failed": 0, "passed": 32, "round": 2941, "tests": "run_selftests.py -k offline_asr"} -->

## 三问

1. **轮次类型**：功能轮（任务书《语音输入离线化与VocoType集成》轮 1：纯后端引擎，不接主程序 UI）。
2. **测试跑了吗、三个基线过了吗**：跑了。新增 `tests/test_offline_asr_engine.py` 32 条用例全绿；默认冒烟 8/8 绿；受影响的递归扫描类架构门禁（覆盖率基线/审计棘轮/子进程超时/删除权威/出站 HTTP/原子写/静态卫生）复测全绿；覆盖率基线重测 **507 模块／70 覆盖**。`--architecture` 全量门禁见「验证记录」，其中 `test_round_baselines` 在功能分支上因 `project_status.md` 只能由 master 提交（pre-commit 硬规则）而呈已知分支态红，合入时状态页同步后转绿，如实记录不粉饰。
3. **欠账少了吗**：是。离线识别引擎、模型自动下载、独立运行环境引导全部落地并有测试锚定；主程序仍零第三方依赖，未引入 sounddevice/keyboard/pyperclip/DirectML。

## 本轮交付（任务书轮 1 验收对照）

| 验收项 | 落地 |
|---|---|
| 独立进程启动/加载模型/逐句返回 | `voice_engine/offline_asr_server.py`：stdio JSON Lines 协议（§4.1 全指令），启动即并行加载 Paraformer+FSMN-VAD+CT-punc（ONNX/CPU，`funasr_onnx`），模型常驻内存；`FunASRServer` 移植保留线程并行加载、quantize 优先、每 10 次转录内存清理。 |
| 逐句 VAD 断句 | `Segmenter`：PCM 尾段滚动送 FSMN-VAD，句末保留 500ms 尾随静音才判稳定，稳定段切 PCM→临时 WAV→ASR→CT-punc→即时 `{"type":"sentence"}`；`stop` 强制冲刷剩余分句后 `done`；超长窗口（120s）截断保护并记日志。 |
| 中文错误与可辨退出码 | 模型加载失败→`{"type":"error","message":"中文原因"}`＋退出码 2；运行期单命令异常→error 行不退出；未捕获异常→exit 3；缺依赖/下载失败/超时分别映射中文提示。 |
| 首次自动下载/二次离线命中/可重试 | `download_models.get_model_cache_path`：`MODELSCOPE_CACHE` 指到 `程序/data/voice_models/`（`VOICE_ASR_MODEL_CACHE` 可覆盖），先查 `hub/models/<org>/<short>` 本地 ONNX 文件，再 `local_files_only=True`，最后在线 `snapshot_download`（revision v2.0.5，可 `FUNASR_*` 环境变量换模型）；下载中断下次重跑自然续传。 |
| 引擎不 import 主运行时/主树无三方包 | `voice_engine/` 仅标准库顶部 import，numpy/funasr_onnx/modelscope 等全部函数内延迟导入；`requirements.txt` 只供独立 venv；`bootstrap.py` 建 `data/voice_asr_venv/`（ensurepip/pip，无 get-pip 出站请求）。 |
| 协议编解码/逐句切分/模型缺失分支测试 | `tests/test_offline_asr_engine.py` 32 条：WAV 头、base64 编解码、VAD 嵌套分段归一化、尾随静音稳定判据、final 冲刷、去重推进、短段丢弃、标点降级、窗口截断、会话生命周期、后端结果解析、模型缓存三分支（本地命中/离线命中/在线兜底）、bootstrap 各错误分支——全部 mock/假模型，零真实下载。 |

## 许可与署名

- `voice_engine/README.md` 保留 VocoType（vocotype-cli）Apache-2.0 版权与许可声明，注明移植范围（funasr_config/download_models/FunASRServer 要点）与 FunASR/ModelScope 模型署名；`_vocotype_src/` 仅只读参考，未入 Git、未入暂存区。
- 模型二进制与第三方包不进源码树与 Git；模型缓存落 `程序/data/voice_models/` 用户数据区，升级安装保留。

## 架构门禁适配（如实）

- `tests/architecture/test_coverage_audit_ratchet.py`：P21 平台适配白名单登记 `bootstrap`（独立运行环境的一次性引导工具，与 `engine_probe` 同类）；`维护记录/覆盖率审计判据_20261001.md` 第 21 项补登记说明。
- `offline_asr_server._preimport_funasr` 由 `importlib.import_module(变量)` 改为函数内静态 import，消除第 24 项动态导入误报（语义不变：固定五个 funasr_onnx 子模块预导入防 ModuleLock 死锁）。
- `维护记录/覆盖率基线.json` 按 9 组定向用例重测刷新（507 模块）；`runbook.md` §11 数字同步（507/70/437）。

## 验证记录

- `python -B -m unittest tests.test_offline_asr_engine`：32/32 绿。
- `python -B smoke_test.py`：8/8 绿。
- 定向架构门禁（覆盖率基线、覆盖率审计棘轮、子进程超时、删除权威、出站 HTTP、原子写、读 JSON 定义、静态卫生、静态名字）：全绿。
- `python -B smoke_test.py --architecture`：470 项实测 **469 绿／1 红**——唯一红 `test_round_baselines.test_round_number_continuous`（状态页 `当前轮次` 2939 vs 最新结果 2941+1=2942）：`project_status.md` 按 pre-commit 硬规则只能在 master 提交，功能分支上属结构性分支态，合入 master 同步状态页后转绿；其余 469 项（含覆盖率基线、审计棘轮、事件总线、技能引用、静态卫生）全绿。
- 未实测：真实 FunASR 模型加载与中文语音识别（需独立 venv＋500MB 模型下载，属轮 2 对接后的整机验收；引擎协议/分句/降级路径已由假模型全覆盖）。

## 通信选型记录（任务书 §4.1 要求写明）

选 **stdio JSON Lines**：主程序以 `platform_tools` 文本进程拉起引擎 venv 解释器，stdin/stdout 逐行 JSON；未发现 Windows 子进程二进制 stdin 受限证据，不启用 127.0.0.1 socket 备选。

## 下一步（轮 2）

`domain/speech_api.py` 后端抽象（offline/cloud 统一事件接口）＋`domain/offline_asr_client.py` 子进程生命周期/降级；`data/语音识别.json` 增 `backend`/`offline` 节；设置弹窗加后端选择。
