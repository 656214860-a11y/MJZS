# R4338 · UX-B2API：接口模型发送一律不开命令行窗口（REQ/DES-S01-118）
<!-- round-evidence: {"commit_base": "930a05fc4", "credential_hits": 0, "evidence_sha256": "73824a81cd0b4e67", "exit": 0, "failed": 0, "passed": 157, "round": 4338, "tests": "run_selftests.py -k shared_input skill_command flow_agent_launch idea_transcript"} -->

## 开头三问

- （一）本轮类型：功能轮（AGENTS.md §3.1，先文档后码）。车道 `codex/ux-b2api-v2`，基准 `930a05fc`。队列卡 UX-B2API，落实用户 2026-11-23 裁决「API 模型不开命令行窗口」。
- （二）测试跑了吗、三个基线：定向 `run_selftests.py -k shared_input skill_command flow_agent_launch idea_transcript` 157/157 绿（退出码 0）；文档门禁 `-k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 34/34 绿（退出码 0）；`smoke_test.py --architecture` 702 条全绿（退出码 0）。默认冒烟与全量回归未跑（卡面未要求；全量以 `full-safe-receipts.json` 凭据为准）。
- （三）欠账少了吗：未新增欠账。

## 缺陷与复现方式

剧本页 `/技能名` 发送在接口模型（直连 API）下仍走 `_open_flow` → `use_cli` → `prepare` → `launch_cli` → `launch_interactive` 开 Qwen Code 命令行窗口：`desktop_shared_send._send_skill` 对 `stage=='script'` 只有命令行链；`ui/desktop_direct_dispatch.dispatch` 无接口模型兜底分支，`resolve_for_send` 给池内接口模型取 `engine='qwen'` 后即落命令行链；`_skill_prompt` 只写「请读取本地技能文件：路径」，接口模型读不了本机文件；其他阶段入口同样没有拦截。裁决：接口模型一律走应用内请求，命令行引擎模型行为逐字不变。

## 改前红（先写测试）

上一会话按卡面先写测试再见红后改码；改前红的原文输出随宿主机重启未能留存，以下红因按基线 `930a05fc` 代码与本轮 diff（全部新增行）逐条核对：

- `tests/test_flow_agent_launch.py` 新增 9 条：
  - `test_skill_send_api_route_api_model_never_opens_cli`：基线 `dispatch` 无 `config['api']` 分支，接口模型配置落回 CLI 链，`host.async_` 会被调用、`status.set` 拿不到「接口模型不使用命令行窗口」→ 断言失败（3 个 stage 子用例同因）。
  - `SkillSendApiRouteTests` 中 6 条直接调 `shared_send.send_skill_request` 或以 `patch.object` 打桩该函数：基线无此函数 → AttributeError。
  - `test_skill_send_api_route_notice_stays_out_of_model_context`：基线 `idea_transcript.load(model)` 无 notice 过滤，notice 行会进按模型加载结果 → 断言失败。
  - `test_skill_send_api_route_cli_model_unchanged`：命令行引擎对照组，基线上即绿（防回归设计）。
- `tests/test_shared_input_stages.py` 新增 2 条：`patch.object(shared_send, 'send_skill_request')` → AttributeError。

定向条数 146 → 157（= 改前 + 新增 11），改后无回归。

## 改动（文件:行号）

- `程序/desktop_shared_send.py:492-601`：新增 `_skill_send_notices`、`_skill_send_refusal_text`、`_skill_send_notice`、`send_skill_request`；`desktop_shared_send.py:619-622` `_send_skill` 对 `stage=='script'` 先交 `send_skill_request` 应用内请求，返回 False（非接口模型）回落原 `_open_flow` 命令行链逐字不变。`send_skill_request` 复用 `send_message` 同一请求链：`resolve_for_send(direct_api=True, model_snapshot=…, adjust=…)` 只冻结本条点名技能装进请求；`skill_injection` 带 `skipped`/`degraded` 或引用含 `status=='resource'` 时照常发送已装下部分并补 notice＋状态栏各一次；`resolve_for_send` 抛错按类别说明（缺上下文长度／正文超预算）不发送；取消、重复发送拦截、`skill_injection` 历史与 `requesting` 状态同自由文本。
- `程序/ui/desktop_direct_dispatch.py:32-36`：`config['api']` 非空时 `host.status.set('接口模型不使用命令行窗口')` 并返回 True，兜底 `open_flow_agent` 全部入口；`api` 为空返回 False，命令行引擎与其他阶段既有直连分支逐字不变。
- `程序/domain/idea_transcript.py:168-179`：`load(model)` 过滤 `role='notice'`，不进模型上下文拼接与按模型导出；`model` 为空的全量读取仍含它供界面显示。
- `程序/ui/desktop_idea_bubbles.py:327-338`：notice 行画成居中灰字小提示条（`bubble_notice_<index>` tag 不带气泡序号），不署模型名、不进 `_bubble_full`/`_bubble_rows`，不参与复制/删除/重发。
- `程序/tests/test_flow_agent_launch.py`（+9 条，含 `SkillSendApiRouteTests` 类与 `test_skill_send_api_route_*` 前缀用例）、`程序/tests/test_shared_input_stages.py`（+2 条接口模型对照用例）：如上；命令行引擎既有断言保持原样。
- `程序/docs/stages/S01_剧本准备.md`：新增 REQ-S01-118（🟡）、DES-S01-117（四个落点）与测试锚点表行。
- `程序/docs/specs/08_对话式交互与输出排版.md` §8：新增「接口模型的命令去向（REQ-S01-118）」段并更新 01 剧本准备行。
- `程序/docs/records/对话需求追溯.md`：「API 模型不开命令行窗口」由待用户裁决改为已裁决（用户 11-23），落点指到 REQ/DES-S01-118。

## 改后命令输出尾部

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k shared_input skill_command flow_agent_launch idea_transcript`（退出码 0）：

```
共 157 条用例，7.0 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（退出码 0）：

```
共 34 条用例，1.3 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：

```
Ran 702 tests in 245.786s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证

- 真实 Tk 界面上 notice 提示条的视觉效果未人工查看；渲染分支经隐藏桌面测试与静态断言覆盖，未做截图核验。
- 真实模型调用未跑（卡面禁止网络请求）；`submit_idea_api_request`/`stream_call`/`resolve_for_send` 全程打桩。
- 「连点发送两次」与「发出后取消」未新增专项用例：`requesting` 拦截与 `begin_request(cancellable=True)` 复用 `send_message` 同一控制器链路，桩断言已覆盖拦截分支。
- 改前红的原文输出随宿主机重启未能留存，红因按基线代码与 diff 核对推断（上文已标注）。

## 卡外发现（只记录，不修）

- `desktop_idea_chat.py` 已触文件行数上限，`send_skill_request` 按 DES-S01-117 落在 `desktop_shared_send.py`（文档已注记 self→宿主形参的取舍）。
- 其他阶段（分镜、配音、视频提示词、资产、白模预演）在接口模型下丢弃用户键入 prompt 的既有缺陷另立项，本轮未动其直连逻辑。

## 回滚

`git revert` 本轮提交。
