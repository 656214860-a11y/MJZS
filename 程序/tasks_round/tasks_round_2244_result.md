# R2244 结果：配音与字幕音频脚本选 API 模型时直连调用（功能轮）

对应：REQ-S11-50、DES-S11-50。第二步（第一步初步分镜见 R2205）；其他阶段与 Qwen 代码不动，TTS 原生路径不动。

## 做了什么
- 文档先行：S11 文档新增 REQ-S11-50、DES-S11-50，模块表与测试锚定表补行。
- 新增 `audio_direct_api.py`（L3）：一次请求让模型按分隔行同时回 `配音脚本.md` 与整集 SRT；`validate_reply` 校验编号连续、时间码、结束>开始、不重叠、不超分镜总时长、每句对白在 SRT 与配音脚本都出现、配音脚本含每个有对白镜头的编号。不合格带问题清单重试一次，仍不合格不落盘并报原因。合格经 `stage_publication.publish_stage_bundle` 写入 `音频/配音脚本.md` 与 `字幕/配音_<集号>_<6位>.srt`；已有配音脚本先备份到 `音频/历史版本/`，只留 2 份（超出经 `recycle_paths`）；发布后刷新声明产出清单（失败只记日志）。
- 复用 R2205 骨架，未另立第二套：`direct_model`、`_ask`、`Job`／`launch`、取消登记与强制停止均沿用；`storyboard_direct_api._Batch` 改为接收 `profile=(阶段, 规则)`，`Job` 增加 `execute()`／`busy_text`，`launch` 增加 `job_class`（分镜行为不变，其 6 条用例原样通过）。
- 新增 `desktop_audio_direct.py`（L4）：后台线程、进度播报、完成／失败／停止状态。
- 分流点唯一：`_FlowAgentLaunch.build()` 增加 `stage=='audio'` 分支（引擎 qwen、模型在模型池且非 Desktop，且宿主有 `current_frame_json`）；三虎无音频入口，不涉及。
- 门禁登记：`_layers.py`、`architecture.md`、覆盖率基线重测（335 模块 / 51 覆盖，8 组目标全绿）、runbook §11 数字同步。

## §7.3 三问
- 唯一入口：分流只在 `_FlowAgentLaunch.build()`；发布只走 `publish_stage_bundle`；停止只走 `workflow_engines.terminate`→`cancel_project_requests`。
- 无新增第二入口，Qwen 路径未删。
- 不碰数据边界、不改模型池配置；未调用真实 API（测试全用假适配器）。完成仍以 REQ-S11-04 的人工确认音轨清单为准，文字稿与字幕不算完成证据。

## 红灯输出（实现前）
```
  test_audio_direct_api          7 条     0.4 秒  ✗ 7
共 7 条用例，1.1 秒；1 个文件有红
ModuleNotFoundError: No module named 'audio_direct_api'（7 条同因）
```

## 测试
- `run_selftests.py -k audio_direct storyboard_direct flow_agent idea_chat audio_subtitle subtitle media_pages requirement_trace`：271 条，0 红。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：本轮引入的 3 类红（复杂度参数数、静默异常、覆盖率基线）已修；仍有 5 项红，均在本轮未碰的文件，改前即存在：`model_pool.py`（原子写 562 行、体量上限 1135>1117、`old.unlink` 删除登记，来自 R2233 快照）、`scripts/release_watch.py` 裸 json.loads 债务、`test_agents_md` 的 performance_history 错误（工作树缺未入库文件）。未处理，另行安排。
- 断言未动：现有测试均未修改；没有测试断言「音频走 Agent／qwen」。
- 未做：真实 API 联调（需用户指定模型）；全量 `--all --safe` 未跑（分支不累计欠账）；非 chat 线路无法在请求中途中断（停止后丢弃结果不落盘）；三虎自动化未接入音频脚本直连。

## 提交
分支 `codex/wip-R2244`（领号时由工具自动切出）；commit 见下方提交信息。
