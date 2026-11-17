# R3162 结果（零依赖边界与媒体预览任务书 M2：默认后端改云端与可选程序降级）
<!-- round-evidence: {"commit_base": "8733f0f4", "credential_hits": 0, "evidence_sha256": "257c7b12c73e15d9", "exit": 0, "failed": 0, "passed": 495, "round": 3162, "tests": "run_selftests.py -k video white_model local_video projects animatic previs"} -->

- 轮次类型：功能轮（任务书 M2；领号时 3160/3161 已被其它工作树占用，本轮实领 **R3162**，分支 `codex/wip-R3162`）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（默认）：默认后端取值变更＋可选依赖的降级引导，先改契约默认值与测试，再动 UI/服务层。
2. **测试跑了吗、三个基线过了吗？** 跑了。冒烟 9/9 通过；任务书指定 `-k video white_model local_video projects` 扩到 `animatic previs` 共 45 文件 495 条用例，首轮仅 `test_white_model_identity` 1 红（R3093 遗留的 `contract.project_stages.STAGES` 失效导入，见「附带修复」），修复后复跑 25 条全绿。全量 `--all --safe` 按 §5 攒到合入 master 前发布点统一跑。
3. **欠账少了吗？** 减少：M2 全部落地——新建项目与读取缺省均为云端、显式 `comfy` 项目不动、云端未配置有既有引导、白模/预演/ComfyUI 缺失均给可操作提示、环境自检标注可选依赖；另顺手清掉一条 R3093 遗留的失效导入欠账。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `domain/projects.py` | 新建项目 `video_backend` 由 `'comfy'` 改 `'cloud'`（唯一写入点；`ffmpeg`/`ffprobe` 不再入项目配置为 R3159 已带）。 |
| `local_video.py` | `open_studio` 读取缺省 `video_backend` 由 `'comfy'` 改 `'cloud'`；配置里**显式**写 `'comfy'` 的项目仍返回 `LocalStudio`，用户选择不动。 |
| `orchestrator/previs_automation.py` | Blender 缺失报错改为引导文案：「需要 Blender：未检测到本地 Blender。请安装 Blender，或在白模设置里指定路径（<settings>）；只准备脚本不受影响」。 |
| `orchestrator/stage_animatic_gateways.py` | `run_animatic` 与 `generate_animatic_reference` 的 ComfyUI 等待改为「5 秒探测 → 未就绪则 `open_comfy()` 拉起桌面程序 → 再等 45 秒」；找不到桌面程序时 `open_comfy` 自带「去设置」引导，不再干等超时。 |
| `ui/local_previs.py` | 白模预演页环境行：Blender 缺失时状态显示「需要 Blender · 未安装 · 去设置」，并露出「去设置」按钮（只在缺失时出现）；按钮打开 `white_model_settings.json`（不存在先写 `{"blender": ""}` 模板），装好后自动收起。 |
| `environment_check.py` | ComfyUI/Blender 缺失行的下一步提示补「可选依赖：」前缀，明示可选档（WARN/提示档本已是「可选」语义）。 |
| `domain/white_model_service.py` | **附带修复（历史欠账）**：`_reroot` 仍 `from contract.project_stages import STAGES`，R3093 已把该名字收编为 `stage_dirs()`——项目改名/移动后调用即 ImportError（`test_white_model_identity` 红）。改为 `stage_dirs()`，断言未动。 |
| `tests/test_projects.py` | 新建项目配置断言补 `video_backend == 'cloud'`（任务书要求的新断言），并顺带锚定 M1 的 ffmpeg/ffprobe 不入项目配置。 |
| `程序/config.json`（本机运行配置，不入库） | `video_backend` 由 `'comfy'` 改 `'cloud'`；`smoke_test.py` 5 处锚点只验字段存在，仍通过。 |

## 决策与边界

- **显式选择不动**：`local_video_settings_service.py:32` 与 `local_video.py` commit() 保存本地设置时仍写 `'comfy'`（用户主动选择）；`ui/cloud_video.py` 保存云端会话仍写 `'cloud'`。已有项目的显式 `video_backend` 一律不覆盖。
- **云端未配置引导**：视频页既有路径已满足任务书——`video_home` 选「线上生成」未配置时显示「首次使用线上生成，请先配置服务商、模型和API Key」＋「配置线上视频 API」按钮；`confirm_rows` 显示「尚未配置；在『阶段配置』→『接口』里配」；`cloud_video` 保存时逐项校验。未新增 UI。
- **提交路径**：`Studio.client()` 先 `configured_key` 校验、`submit()` 先查 `live_enabled`（新项目为 False →「当前为离线模式」可读报错），未配置云端不会 KeyError 穿透。
- 未新增 pip 依赖、未新增模块；`open_comfy()` 无参调用与 `local_video` 既有用法一致（读 `desktop_settings.json` 的 `comfy_exe`）。

## 验证

- `smoke_test.py`：9/9 通过（含 5 处 `video_backend` 字段锚点）。
- `run_selftests.py -k video white_model local_video projects animatic previs`：45 文件 / 495 条用例，修复 `_reroot` 后全绿（复跑 25 条确认）。
- `run_selftests.py --all --safe` 全量：未运行（按 §5 攒到合入 master 前发布点执行）。

## 提交

- 待提交（`dev.py commit`，功能轮，含 `--tests` 证据）。
