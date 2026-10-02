# R627 功能轮——桌面引擎优先策略的可见性 + architecture.md 修正

## 开头三问（AGENTS.md 第 7 节）

- 本轮是功能轮还是整理轮？**功能轮**（AGENTS.md 3.1）。
- 测试跑了吗？三个基线过了吗？新增专项 **3/3**、默认冒烟 **8/8**、架构门禁 **102/102** 通过；全量安全自检已启动但其父进程未返回最终汇总，不能宣称通过。
- `project_status.md` 的欠账少了吗？**没有减少产品债务**；只完成了用户可见性与文档契约同步。

编号自检：R626 已存在，R627 原先未占用，故本轮新增 R627；完成后台账按连续性规则推进至 R628 待执行。

## 改动文件与摘要

- `workflow_settings.py`：新增只读 `desktop_route_notice()`。它仅在调用时读取已保存阶段设置并复用 `find_program()`，GPT 映射 Codex、Anthropic 映射 Claude；不写盘、不改变 `current()`。
- `skill_panel.py`：模型下方新增提示标签。仅用户通过模型/供应商下拉主动改选，或主动套用预设后，调用上述查询；面板构造与 `load()` 不调用它。
- `architecture.md`：删除“桌面引擎不参与 API 自动抢占”的相反描述，改为 GPT/Anthropic API + 对应本机程序可启动时本机优先，启动失败回退 API。
- `PROJECT_MAP.md`：把“本机优先、兼容 API 回退”明确到 GPT/Anthropic 的触发条件。
- `tests/test_workflow.py`、`tests/test_skills.py`、`tests/architecture/test_agents_md.py`：增加回归与文档契约检查；原模型标签测试改为按既有 R625 的显示标签器比较，不改变模型池候选语义。
- `project_status.md`：台账从 R626 推进至 R628，满足轮次连续性守卫。

## 标注与按需探测

提示文案为：`已检测到本机 GPT 程序：运行时会优先由本机程序执行；若启动失败，将回落到所选 API。`（Claude 同理）。本机程序不可用、探测异常或 DeepSeek 时为空；不会遮挡模型名，也不禁用选择。

新提示没有添加启动期或面板加载期扫描：`Panel.__init__` 和 `load()` 均不调用 `desktop_route_notice()`；测试以 mock 验证打开面板后调用数为 0，用户主动 `choose_model()` 后才为 1。R625 既有的桌面模型“未安装”显示标签器未在本轮修改。

## 文档前后对比

- 之前：`architecture.md` 称桌面引擎“显式选择的本机 Agent，不参与 API 自动抢占”。
- 之后：明确 GPT/Anthropic API 在对应本机程序可启动时会优先交给本机程序，启动失败才按兼容 API 回退；阶段配置会在用户主动改选时显示这一结果。

## 新增回归断言

1. GPT API + 可用 Codex：查询返回本机 GPT/回落 API 提示，且 `skill_config.json` 字节不变。
2. GPT API + 探测异常：提示为空；DeepSeek：提示为空。
3. Anthropic API + 可用 Claude：返回本机 Claude 提示。
4. 新建阶段面板不调用提示查询；主动改选模型后调用一次并显示提示。
5. 架构测试要求文档含 GPT/Anthropic、本机可启动、启动失败 API 回退，并要求实现仍保留 GPT/Anthropic 到 codex/claude 的映射。

专项命令：

```powershell
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_workflow.DesktopModelPoolTests.test_desktop_route_notice_only_describes_available_gpt_or_anthropic_api_without_writing tests.test_skills.PanelTests.test_model_route_notice_is_lazy_and_visible_only_after_user_selects tests.architecture.test_agents_md.AgentsMdConsistencyTests.test_desktop_route_documentation_matches_current_contract
```

原始汇总：`Ran 3 tests in 0.291s`，`OK`。

## 验证

- `python -B smoke_test.py`：通过 8 项、失败 0 项。
- `python -B smoke_test.py --architecture`：首次 102 项中 1 项失败，原文为 `AssertionError: 626 != 627`（`test_round_number_continuous`）；原因是 R626 结果已在而台账仍为 626。推进台账后重跑：`Ran 102 tests in 24.251s`，`OK`。
- `python -B smoke_test.py --affected skill_panel workflow_settings`：121 条中两条既存失败，均非本轮：
  - `test_the_skill_boxes_follow_the_flow_order`：实际额外发现 `pipeline-audio-subtitle`。
  - `test_every_tool_in_the_registry_is_known`：18 个既有未注册工具，如 `asset.plan`、`audio.synthesize`。
- `python -B run_selftests.py --all --safe`：已按要求启动，输出确认“211 个测试文件 / 562 路工作单元（串行）”；调用环境未提供最终汇总，故本报告不将其记为通过。

## 手工启动观察

已用项目内置解释器启动 `app.py`。当前自动化运行面没有暴露原生 Tk 窗口（仅返回浏览器表面），因此无法代替用户点击“剧本准备 → 阶段配置 → GPT-4o”读取屏幕文字；未将此限制误报为已人工确认。专项 UI 回归验证了同一交互路径的标签赋值。请在本机确认：主动选择 GPT-4o 后，模型下方出现上述本机优先说明。

## 用户数据未改动确认

未写入任何用户项目文件；`desktop_route_notice()` 的回归对临时项目的 `skill_config.json` 进行改选前后字节相等断言。未触碰用户项目、配置或密钥。

## J 后续

- 待办 C：诊断并决定 `token_saver`、`codex_paste`、`codex_tasks` 的可见性，避免让未使用 Codex 的用户误解入口。
- 待办 D：是否需要“禁用本机优先”的显式开关，等待真实用户反馈后再设计，不能暗改默认。
- 先重跑架构门禁与全量安全自检，收集其最终汇总；既存 SKILL 顺序/工具注册红项另立修复轮。

## 自审

- 只改 UI 显示、纯查询与文档契约；`current()` 路由未修改。
- 复用既有 `find_program()`，未添加启动期或页面加载期的新扫描。
- 未修改用户项目数据、`skill_config.json`、密钥或执行行为。
