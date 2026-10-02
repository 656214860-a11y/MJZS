# R608｜只读诊断轮｜Claude 与 DeepSeek/Qwen 的剧本响应处理差异

## A. 结论

代码中不存在“把自然语言回复判为问题或剧本，并据此切换 Claude / DeepSeek / Qwen 行为”的协议分流器。三者的共同前置是本地简报门禁；简报完整后，三者均进入 HOLLMWOOD 四角色链并仅由该链成功后的统一入口写 `script_raw.md`。

因此，“DeepSeek/Qwen 直接把响应当剧本落盘、Claude 会追问”的现象不能由当前 `/v1/messages` 与 `/chat/completions` 响应解析代码直接证明。可确认的实际差异是：Claude Messages 有受控 `tool_use` 循环和 thinking/空正文续写；Chat Completions 仅提取首个 `message.content`（并支持流式），没有同等工具循环。

## B. 路径对照

| 检查项 | Claude Messages（`/v1/messages`） | DeepSeek/Qwen Chat（`/chat/completions`） |
| --- | --- | --- |
| 响应处理模块 | `model_router.py:155` 的 `ModelAdapter.chat()` 调 `token_saver.anthropic_text()`（`model_router.py:186`，实现见 `token_saver.py:316`）；剧本普通对话再由 `writing_api.py:217` 的 `_reply_with_project_tools()` 处理。 | `model_router.py:155` 的同一 `ModelAdapter.chat()`；Chat 分支在 `model_router.py:196` 起读取 `choices[0].message.content`。`stream()` 仅对 `wire_api == 'chat'` 启用（`model_router.py:236-246`）。 |
| 判断“问题 vs 剧本” | 没有语义判断。`writing_api.py:61` 只识别 content block 的 `type == tool_use`；`token_saver.py:316-339` 只保留 `text/output_text`，排除 thinking/signature。 | 没有语义判断。只读取可见 `content`，记录 `finish_reason`、reasoning 字段和长度为诊断元数据（`model_router.py:180-232`）。 |
| `stop_reason` / `tool_use` | 有：`_record_empty_response()` 记录 `stop_reason` 和 block 类型（`writing_api.py:79-96`）；`tool_use` 会执行 `writing_tools.execute()`，回传 `tool_result` 后继续请求（`writing_api.py:233-280`）。`stop_reason` 本身不控制 UI 或“剧本/问题”分类。 | 没有 Claude 的 `tool_use` 循环；只记录 Chat 的 `finish_reason`。`idea_chat.py:727-744` 仅把 `finish_reason == length` 用于空正文的错误说明，不用于成果分类。 |
| SKILL 怎么传 | 两处均从 `workflow_settings.skill_prompt(settings)` 拼入系统提示：普通路径在 `writing_api.py:301-309`；完整简报的 HOLLMWOOD 路径在 `writing_api.py:195-201`。Messages payload 把它放在顶层 `system` 并带 cache control（`model_router.py:143-148`、`token_saver.py:295-300`）。 | 同一份 `skill_prompt`。Chat payload 把系统提示插入 `messages[0]`（`model_router.py:122-125,149-152`）；完整简报同样传给 HOLLMWOOD。 |
| SKILL 是否过滤“询问步骤” | 否。`workflow_settings.py:392-411` 只拼接每项 SKILL 的引用指令；对 `claude/qwen` 生成“完整读取本地技能文件 path”，未解析或删改 SKILL 正文。 | Qwen 同样走本地路径引用；其他 engine（包括非 qwen/claude 的配置）生成 `[$name](path)` 引用（`workflow_settings.py:407-411`）。两条分支都没有“过滤询问步骤”的代码。 |
| 多轮交互在哪 | 与协议无关，均由 `desktop.py:1391` 的 `Desktop.send_message()` 和 `idea_chat.py:599` 的 `receive_brief()` 实现。缺字段时本地生成 `brief_followup()`，追加到聊天记录并直接 return（`desktop.py:1428-1444`）。 | 相同；在选择 direct API 模型前已执行 `receive_brief()`，因此不会先请求 DeepSeek/Qwen 再由它们决定是否追问。 |
| 正式剧本落盘 | 完整简报会进入同一 `_hollmwood_reply()`；四角色全部成功后，`writing_api.py:169-181,210-214` 调 `_write_script_raw()` 写 `script_raw.md`。Messages 的工具写文件仅存在于“无完整简报”的普通工具对话分支，写入权限由 `writing_tools.py:12-82` 控制。 | 完整简报同样进入 `_hollmwood_reply()` 并从同一 `_write_script_raw()` 落盘；Chat 的一次普通响应不会在 `writing_api.reply()` 末尾自动写为剧本。 |

## C. 剧本准备 UI 的实际交互与保存

1. 用户发送后，`Desktop.send_message()` 先调用 `idea_chat.receive_brief()`（`desktop.py:1403-1420`）。缺必填项时，`idea_chat.brief_followup()`（`idea_chat.py:589-596`）生成固定追问，UI 记录用户消息和本地追问后返回；此时没有模型 API 调用。
2. 简报齐全且选了 direct API 模型时，UI 用异步请求 `writing_api.reply()`，将可见回复追加到会话（`desktop.py:1449-1490`）。只有返回 `script_raw_path` 才刷新成果列表并报告“四角色剧本已保存”。
3. 普通聊天回复不会自动下载。`idea_chat.looks_like_script()`（`idea_chat.py:702-707`）仅决定“下载剧本”按钮是否可用（`desktop.py:1664-1670`）；用户点击后才由 `download_script()` 调 `idea_chat.save_reply()`（`desktop.py:1672-1687`）。
4. 未选择 direct API 模型时走桌面 Agent 工作流 `start_script_workflow()`（`desktop.py:1317-1331`），不属于本报告的 HTTP Messages/Chat 两条路径。

## D. HOLLMWOOD 与差异成因核验

- `writing_api.reply()` 在发现 `brief_complete.json` 后不看 `wire_api`，直接调用 `_hollmwood_reply()`（`writing_api.py:283-301`）。
- `hollmwood_roles.run()` 将同一份 SKILL 指令附到导演、编剧、编辑、演员和导演审核的 system 中（`hollmwood_roles.py:231-260`）；最终只取 actor 输出为 `outputs['script']`（`hollmwood_roles.py:278-307`）。
- HOLLMWOOD 唯一的文本判定是导演审核回复是否以 `APPROVED` 开头（`hollmwood_roles.py:178-180`），用于角色修订门禁，不用于“用户问题 vs 剧本”的 UI 分支。

## E. 根因判断与证据边界

**已证实：** Claude 与 Chat 的响应处理不对称主要来自 Claude 专属的工具/内部思考处理，以及 Chat 专属的流式输出与 `finish_reason` 诊断；两者没有统一的“问题/剧本”分类器。

**已证实：** 当前剧本准备的“看到问题 → 回答 → 再看到问题”是 `brief_complete` 前的本地字段追问，挂在共享 UI/`idea_chat` 门禁，不挂在 Claude Messages 专属路径。

**不能由静态代码证明：** 某一具体模型实际会不会遵守 SKILL 中的询问步骤、或某次线上响应为何看起来像直接剧本；这取决于该模型返回内容与当前项目配置。代码没有将 SKILL 正文按“询问步骤”过滤，也没有把模型可见正文自动语义判为剧本后立即落盘。

## F. 本轮变更与验证

- 未修改任何 `.py` 文件；未运行 smoke test（本轮为只读静态诊断）。
- 仅新增本结果文件。
