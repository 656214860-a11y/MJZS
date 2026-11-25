# L0–L5 制作链路集成 A 卡验收记录



## 实现与代码位置

| 验收点 | 实现位置 | 口径 |
| --- | --- | --- |
| project/run/task/attempt 定位 | `domain/tts_api.py`；`domain/task_center_service.py` | 逐句配音每句在发送前登记随机 `request_id`、同号 `cost_request_id` 与 `execution.stage/run_id/task_id/attempt_id`；同一批次共享 `run_id`，每句 `task_id` 为 `<镜头>#<序号>`，attempt 即请求号。任务中心投影时补 `project_id`。 |
| 成功句重启保持 | `domain/tts_api.py`；`tests/test_tts.py` | 沿用判定仍走 `line_done` sha256／旧清单非空回退；回归断言续跑 `(1, 1, 0)` 且生成器未被调用，新增付费提交为零。 |
| 408／未知句可定位 | `domain/task_center_service.py`；`tests/test_runtime_projection.py` | 扫描 `音频/配音分句/<批次>/时间轴.json`，逐句投影批次、句序、台词预览、状态、请求号、费用请求号、执行身份、成品引用与失败说明；旧版 `failed + TTS 请求失败（HTTP 408）` 且未人工放开的记录归一为 `reconcile`，不误判为可自动重试。 |
| 查单能力 | `domain/task_center_service.py` | 视频标为 `queryable`（现有云端适配器有 `poll(task_id)`）；OpenAI 兼容 `/audio/speech` 是同步请求，无按请求号查单接口，音频标为 `manual` 并指向服务商账单／控制台人工核实，不假装能查。 |
| 原请求取回 | `domain/task_center_service.py` | 视频版本读取对应 `task_receipt.json` 与 `request.json`；回执的 shot/local_request/version 与版本记录不匹配时记错误并弃用该回执，避免串号。展示层给出原请求或回执路径。 |
| 可执行操作 | `domain/task_center_service.py`；`ui/task_center_ui.py` | 任务中心「运行状况」保留正常入口，新增查询框；可按镜头、句序、批次、台词片段、请求号、费用请求号、远端号、运行号做大小写不敏感部分匹配。每行输出查单能力与下一步：成功句不重发、未知句先人工核实、已放开失败句可在配音页续跑。 |
| 任务中心到配音页定位 | `ui/task_center_ui.py`；`ui/desktop_audio_direct.py`；`ui/desktop_media_pages.py` | 「打开配音页定位」只在当前查询唯一匹配一句配音时经正常 `page_of('audio')`／`go` 导航；多条匹配不猜测、要求先缩小查询。配音页显示批次、句序、镜头/任务、台词、请求号、费用请求号和下一步的定位卡。该动作只导航与展示，不调用逐句配音、不放开未知句、不提交任何新请求。 |
| 费用请求号 | `domain/task_center_service.py` | 音频优先 `cost_request_id`、回退 `request_id` 后关联费用台账；资产兼容版本记录／回执里的 `money_request_id` 或 `cost_request_id`；视频保留既有 `money_request_id`。展示估算、已核对、差额、币种与请求号。 |
| 资产与视频视图保留 | `domain/task_center_service.py`；`tests/test_runtime_projection.py` | 原资产台账与视频版本投影保留，仅补充回执校验、原请求路径、费用请求号兼容与查单能力字段。 |
| 损坏记录可见 | `domain/task_center_service.py`；`tests/test_runtime_projection.py` | 资产台账、视频版本、批次.json、时间轴.json 损坏或类型不符都进入 `errors`，不隐藏其他来源；配音成品路径越出项目范围时不读取成品并记录错误。 |
| 复杂度返工 | `domain/task_center_service.py` | `project_snapshot` 已拆为模块级读取与适配函数：权威 JSON 读取 `_source/_source_list`、资产扫描 `_scan_assets`、视频逐项适配 `_adapt_video_version` 与 `_scan_video_file`、配音批次读取 `_scan_audio/_scan_audio_batch`、逐句投影 `_append_audio_line`。路径越界防护、回执串号校验、历史 `legacy` attempt 与「历史未登记」语义保留。 |
| 账号切换隔离 | `domain/tts_api.py`；`tests/test_tts.py` | 保存密钥时写入随机本机 `key_account`（uuid，不是密钥或密钥散列）：同密钥沿用，换密钥轮换。句子身份纳入该标记；两边都有标记且不同则缓存失效。无标记历史成功句不因升级自动重发，避免为兼容付出重复费用。 |
| 契约与分层登记 | `docs/stages/S11_配音与字幕.md`；`tests/architecture/_layers.py` | REQ/DES/IF 已登记 `key_account`、请求号、执行身份、任务中心只读恢复口径与页内定位不提交语义；`task_center_service → tts_api` 复用边按架构规则登记。 |

## 回归测试位置

新增或更新的测试：

- `tests/test_tts.py`
  - `test_run_lines_records_shared_run_attempt_and_cost_request`：同批 run、逐句 attempt/task、请求号与费用请求号。
  - `test_key_account_switch_invalidates_sentence_cache`：账号标记变化后缓存与批次复用失效。
  - `test_unmarked_legacy_success_is_not_resent_after_account_marking`：无标记历史成功句升级后沿用，生成器调用为零。
  - `test_save_key_keeps_random_account_only_for_same_key`：同密钥沿用、换密钥轮换，设置文件不落密钥。
- `tests/test_runtime_projection.py`
  - `test_reopen_correlates_authorities_without_writing_or_resubmitting`：资产、视频重启投影、远端号、原请求路径、费用请求号；两次快照一致且文件零写入。
  - `test_video_mismatched_receipt_is_reported_and_not_used`：回执串号可见且不使用错误远端号。
  - `test_audio_restart_projects_success_and_legacy_408_without_writes`：成功句、旧 408 句、批次、句序、请求号、查单能力、操作文案与零写入。
  - `test_audio_corrupt_timeline_is_visible_and_does_not_hide_video`：损坏时间轴可见且不遮蔽视频记录。
- `tests/test_task_center.py`
  - 既有：任务中心正常入口查询框，支持 `S00` 部分匹配到 `S001`。
  - `test_audio_focus_action_opens_audio_page_without_submission`：查询 `tts:408` 后点击「打开配音页定位」，断言携带第 1 句/reconcile/请求号并导航配音页，且不触发生成入口。
  - `test_audio_focus_action_rejects_ambiguous_rows_without_navigation`：多句匹配时不猜测、不导航、不携带焦点，要求先缩小到一句。
  - `test_recovery_focus_render_warns_unknown_without_submitting`：定位卡展示批次、句序和“不发送请求／未知句不自动重提”提示。
- `tests/architecture/_layers.py`：除既有 `task_center_service → tts_api` 外，登记本轮新增的 `desktop_audio_direct → ui_widgets` 同层边。

Control 指定复核项还包括：

```powershell
..\运行环境\Python\python.exe -B run_selftests.py -k tts task_center runtime_projection
..\运行环境\Python\python.exe -B run_selftests.py -k layer_relations complexity function_size
..\运行环境\Python\python.exe -B smoke_test.py --affected task_center_service tts_api task_center_ui desktop_audio_direct desktop_media_pages
..\运行环境\Python\python.exe -B smoke_test.py
```


## 边界与未满足项

1. TTS 当前实现使用 OpenAI 兼容同步 `/audio/speech`；没有可恢复的供应商异步任务号，也没有按请求号查单接口。任务中心只提供本地请求号、费用请求号与人工核实路径。
2. 任务中心是只读恢复投影；「打开配音页定位」只导航并显示目标句，不在任务中心或定位卡中直接重发配音、重提视频或人工放开未知句。人工放开仍走配音页既有确认入口，避免绕过扣费安全文案。
3. 沿用历史成功句不会补写旧条目的执行身份；无 `execution` 的旧记录在任务中心以 legacy 指纹作为 attempt 展示，`run_id` 如实显示「历史未登记」。
4. `key_account` 是随机本机隔离标记，不代表供应商账号 ID；同一密钥沿用标记，换回旧密钥会生成新标记，属于保守隔离。
5. 无账号标记的历史成功句按兼容口径仍允许沿用；这优先满足“升级后成功句保持、新增付费提交为零”，不是严格的账号所有权证明。
6. 整段配音尝试账尚未纳入任务中心逐句投影；本轮覆盖任务书验收点名的逐句配音进度与历史格式。
7. 未执行真实付费服务、未读取真实账号凭据、未进行真实供应商查单；所有回归均设计为本地假数据／假生成器。

集成验证由 Control 使用随附解释器执行，命令、结果与真实环境边界见 [R4516 独立验收](tasks_round_4516_result.md)。
