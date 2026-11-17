# R3201 结果（零依赖边界与媒体预览任务书 M6：离线语音识别可选与下载入口）
<!-- round-evidence: {"commit_base": "4be88550", "credential_hits": 0, "evidence_sha256": "b7ff20960363db5a", "exit": 0, "failed": 0, "passed": 82, "round": 3201, "tests": "run_selftests.py -k test_offline_asr_setup test_offline_asr_client test_speech_api test_offline_asr_engine test_shared_input_voice"} -->

- 轮次类型：功能轮（任务书 M6，REQ-S01-97；实领 **R3201**，分支 `codex/wip-R3201`）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮：离线 ASR「无环境＋无云端密钥」分支改可执行引导；「模型管理 › 语音识别…」新增「下载离线语音包」入口（进度／取消／续传／半成品清理）。
2. **测试跑了吗、三个基线过了吗？** 跑了。冒烟 9/9；`run_selftests.py -k offline_asr speech voice dialog_voice` 115 条 0 红（新增 `test_offline_asr_setup` 11 条）；`architecture.test_layers` 等 22 条 0 红（新模块 L2 登记）。首轮 2 条新用例红（FakeProc.wait 超时属测试桩缺陷），修桩后全绿。
3. **欠账少了吗？** 减少：新用户语音输入两条出路都走通；老用户默认语义未动（不静默切云）。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `domain/offline_asr_client.py` | `environment_problem` 分流：显式 `offline.python` 失效仍点名设置值（原契约）；默认 venv 缺失改发「请在「模型管理 › 语音识别…」下载离线语音包，或为语音识别配置云端密钥」——不贴内部路径、不说「缺少 python.exe」。 |
| `domain/offline_asr_setup.py`（新） | L2 下载控制器：`base_candidates`/`_probe`/`resolve_base_python`（`VOICE_ASR_PYTHON`＞显式设置＞`py -3.12/-3.11/-3.10`＞PATH，只收 3.10–3.12 并取真实 `sys.executable`）；`OfflineSetupRunner` 后台线程两阶段——`voice_engine/bootstrap.py` 建 `data/voice_asr_venv` → venv 内 `-m voice_engine.download_models`（`--cache` 取 `offline.cache_dir` 或 `data/voice_models`）；经 `platform_tools.launch_text_process` 拉起、逐行解析 JSON Lines 转发 `progress|done|error|cancelled`；`cancel()` 杀当前子进程；`cleanup_incomplete_venv` 只清「目录在、解释器缺失」的半成品，已建 venv 与模型分块保留续传；`models_ready`（hub 下存在 onnx）为完成判据，失败/取消均不穿透异常。 |
| `ui/speech_settings_ui.py` | 弹窗新增「离线语音包」行：状态（已安装／环境已建模型未完／未安装）＋「下载离线语音包…／取消下载」按钮＋逐行进度标签；事件经 `win.after` 消费不阻塞界面；窗体暴露 `_pet_speech_setup` 测试句柄。 |
| `tests/test_offline_asr_setup.py`（新） | 11 条：候选顺序与版本窗、探测拒绝、默认缺失引导文案（无内部路径）、显式解释器点名、`models_ready`、半成品清理、无基座报错、两阶段命令与进度事件、venv 失败清理、取消杀进程且保留可续传状态、重入拒绝。全假进程/假目录，不建真 venv、不联网。 |
| `tests/architecture/_layers.py` | `offline_asr_setup` 登记 L2（实际依赖：stdlib＋`contract.platform_tools`＋`domain.offline_asr_client`）。 |
| `docs/stages/S01_剧本准备.md` | REQ-S01-97 🟡→✅（R3201）；DES-S01-97 记录实现口径。 |

## 决策与边界

- **默认不改**：`backend` 默认仍 `offline`；离线缺失＋有云端密钥时既有 `missing_reason`/`create_session` 降级走云端（验收②原本已满足，未新增机制）；已装离线环境且未显式写 `backend` 的用户行为不变。
- **不重复造下载**：复用 `voice_engine/bootstrap.py` 与 `download_models.py`（modelscope 分块校验＋断点续传即「校验和/续传」验收的权威实现）；`data/voice_asr_venv`、`data/voice_models` 位置不动。
- **半成品口径**：模型分块由 modelscope 原子落盘；venv 侧仅缺解释器的目录被清，其余保留＝可续传。
- **基座解释器**：随包 Python 3.14 超出依赖轮子范围，探测真实 3.10–3.12；找不到时给「装 Python 或用云端」指引而不是静默失败。

## 验证

- `smoke_test.py`：9/9。
- `run_selftests.py -k offline_asr speech voice dialog_voice`：115 条 0 红（`test_offline_asr_setup` 11 条、`test_offline_asr_client` 19 条、`test_speech_api` 4 条、`test_offline_asr_engine` 39 条、`test_voice_*`/`test_shared_input_voice`/`test_dialog_voice_input` 全绿）。
- `run_selftests.py -k layers`：22 条 0 红（新模块 L2 登记生效）。
- 联网下载本身不在 CI 断言内（假进程覆盖事件流与清理语义）。

## 遗留

- M7 登录后模型池为空开模型管理；M8 收尾。
