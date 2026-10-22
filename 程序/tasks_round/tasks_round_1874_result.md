# R1874 结果：测试瘦身第 2 批 d（整理轮）

- 本轮类型：整理轮。只改测试，产品代码一行没动。
- 依据与做法同 R1869／R1870／R1872：先把差分测试独占的产品行补成普通行为测试，用 `Temp/audit/verify.py`（不进仓库）确认这些行被替代测试跑到，再删差分测试。

| 删掉的差分测试 | 独占行 | 替代测试（新增或扩充） |
|---|---|---|
| test_tick_async_result_equivalence | 9 | `tests/test_desktop_async_tasks.py` 加 `TickResultTests`：本机已放弃等待的当前票据释放 worker 并接着跑队列；创意请求失败时撤销请求、解锁发送按钮；待恢复的结构剧本被拒时状态栏说明“暂缓” |
| test_send_message_equivalence | 13 | `tests/test_model_call_error_kind.py` 加 `IdeaApiReceivedTests`：直连 API 失败按 kind 选文案与弹窗标题（含“请求校验未通过”），空回复说明原因，剧本已保存时刷新列表、播报、显示质检，自然剧本落盘后状态栏给路径 |
| test_app_tick_equivalence | 17 | `tests/test_video_result_polling.py` 加 `TickBranchTests`：后台消息分流到进度行或日志；界面刷新、提示词轮询、自动提交扫描、后台跟踪各自出错都不打断下一次 tick（含日志控件已销毁）；本地提交失败记账并弹窗，静默轮询失败只写日志；成功回调出错写“成片目录打开失败” |
| test_run_background_equivalence | 22 | `tests/test_workflow_engines_run.py` 加 `BackgroundRunTests`：Codex 输出写进运行日志、非 0 退出码报错；Claude JSON 回复成功才转正响应并写制作报告，空正文、未授权、非 0 退出码都报错且不留临时文件；进程槽位每次都释放 |
| test_open_flow_agent_equivalence | 41 | 新文件 `tests/test_flow_agent_launch.py`（`desktop_idea_chat` 没有单一主测试文件）：剧本阶段校验技能并判定过期会话改开新会话；Qwen 窗口标题；Codex 技能同步失败不领号；白模预演打开 Blender 后粘贴到 GPT 桌面；重复任务可安全重试或复用；Qwen 续发；排队取槽报位次后被拒；全自动下提示到 Claude Desktop 手动发送 |

- verify.py 对 run_background 报 3 行“源码已变”：`workflow_engines.py` 的 `_run(...)`、`_run_claude_json(...)` 这 3 处调用在 495889e5 之后加了 `timeout` 参数，按行文本映射不到当前文件。新用例的 `fake_run` 断言收到 `timeout=42`，这 3 处调用确实被跑到；其余 19 行 0 漏。另外 4 个文件都是 0 行漏掉。
- skip 台账：5 个被删文件都没有登记项；新用例不含跳过位，台账不变。
- 断言未动：现有用例的断言一条没改，只新增用例。
- 轮次号：本轮领到 1874，1873 已被其他会话领走。
- 验证：替代测试在隐藏桌面实测通过：test_desktop_async_tasks 4/4、test_model_call_error_kind 17/17、test_video_result_polling 14/14、test_workflow_engines_run 5/5、test_flow_agent_launch 8/8。冒烟通过（隐藏桌面）。架构门禁 394 条只红 `test_round_baselines.test_round_number_continuous`，原因同 R1870／R1872：`project_status.md` 按约定只在 master 上改，合入时补齐。全量放在 17 个都做完之后统一跑。
- 剩余：asset_batch_window，以及 `test_script_structure_page_equivalence`。
