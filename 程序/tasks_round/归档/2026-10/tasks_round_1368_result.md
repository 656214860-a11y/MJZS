# R1368：O41 取消状态同时解释本机与远端，并保全迟到／已返回结果

类型：功能轮（§3.1；本项「事实／建议」→ 取消语义说明＋迟到结果隔离与保全）。承接 R1267 清单 O41（O01—O40 已完成）。中央轮次 1368（原领 1368；主树含他人已暂存 WIP，故在干净临时工作树 `o41-claim` 调用 `round_claim.py next` 领取）。本轮 1368 − 1367 = 1 < 5，无五轮欠账；改动未命中 §5，收口仍按流程在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_cancellation_status.py` 13/13；定向 `-k cancellation_status desktop_automation desktop writing_cancellation writing_response_preservation writing_api writing_restart script_agent_delivery` 131/131；关联 `-k desktop_automation desktop_automation_service cancellation_status writing_api writing_cancellation writing_response_preservation writing_restart idea_chat` 253/253（含 Tk `after` 噪声，0 红）；架构门禁 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均为 0 红。全量见「全量判定」。
- 欠账：O41 关闭，清单剩 O42—O48；1368 − last_full_safe_all_round(1367) = 1 < 5，无五轮欠账；未命中 §5；收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O41）
- 证据：[desktop_automation_service.py:95](D:/漫剧制作助手/程序/desktop_automation_service.py:95)（`BackgroundTaskLifecycle`）以代次拒绝迟到 UI 回调，不强杀线程；R1266 已为剧本迟到正文增加保全。
- 建议：显示“本机停止等待／远端取消已确认／远端仍可能执行”，保存可查询编号；推广迟到结果隔离和安全保全到有成本任务。取消不应被显示成确定未计费。
- 验收：取消后切项目／模型、旧请求晚返回、退出重启不污染新界面／正式采用状态，也不丢已返回可保全结果。
- 前提核对（结论）：清单证据成立。「可查询编号」在既有实现里只对**本机代次（ticket）**存在，付费／远端任务编号分散在 `local_video`（ComfyUI `prompt_id`）与 `pet_llm.RequestLedger`（`remote_task_id`），桌面取消入口此前不区分本机与远端、也不提计费口径——本轮补齐这层说明与迟到内容保全，未改远端接口行为。项目里没有可调用的「远端取消」接口，故不伪称「远端已取消」。

## 实现
### desktop_automation_service.py（L3）
- `BackgroundTaskLifecycle.submit(ticket, *, remote_task_id=None, costly=False)`：登记当前代次，同时记下远端任务编号与「有成本」事实；`_seen` 有界保留最近 `LATE_RESULT_LIMIT`(=8) 个已提交代次。
- `BackgroundTaskLifecycle.cancel(ticket=None, *, costly=False, remote_task_id=None, remote_cancel_requested=False, remote_cancel_confirmed=False)`：**取消只代表本机停止等待**；有成本或远端信息时记一条 `_cancel` 事实。普通任务（无成本、无远端）行为与快照逐字不变。
- `BackgroundTaskLifecycle.cancellation_status(ticket=None)`：返回 `{ticket, remote_task_id, costly, remote_cancel_requested, remote_cancel_confirmed, local, remote, text}`。`remote` ∈ `confirmed`（远端取消已确认）／`pending`（已请求远端取消、未确认）／`not-requested`（未向远端发取消请求）／`unknown`（无远端编号、无法确认）；`text` 是给界面直接用的三态说明，含「本机已停止等待这一批结果」「远端仍可能继续执行」与成本提示「远端确认前不能当作未计费，最终用量以远端账单为准」，并给出可查询编号（本机批次 ticket、远端任务 remote_task_id）。无成本且无远端时返回 `None`（保留旧语义）。
- `BackgroundTaskLifecycle.finish(ticket, *, succeeded)`：被拒绝的迟到结果不再静默丢弃——按已提交代次记入有界的 `late_results()`（上限 8），且**不改** `snapshot()`／`_last`（与既有「迟到结果不得改变当前代次事实」一致）。
- 新增模块常量 `LATE_RESULT_LIMIT = 8`。

### stage_execution_service.py（L3）
- 新增 `publish_response_archive(project, text)`：把已返回的可见正文经 `publish_stage_text` 原子归档到 `01剧本准备/responses/<时间戳>_<唯一标识>.txt`，只归档、不登记阶段成果、不改采用状态；空正文不建文件（换行统一为 LF，避免 Windows 重复回车）。
- `reply_to_writing(...)` 新增注入 `archive=publish_response_archive`（桌面唯一入口）。

### writing_api.py（L3）
- `reply(..., archive=None)` 新增可选归档通道；新增 `_archive_returned_response`／`_archive_note`／`_archive_then_require_active`：在检查取消**之前**先给已返回的可见正文留档，取消时把归档位置附在取消错误里（「原始响应已保存（responses/ 归档，不等于正式采用）：<路径>」），把 R1266 只对阶段①②③的保全推广到阶段④自然剧本／普通对话这类有成本的生成。归档写盘失败（`OSError`）只降级为不建档，不阻断本轮正文交付。
- 覆盖 `reply()` 的两条正文出口：受控工具（messages）路径与普通对话路径。默认 `archive=None`：直连 `writing_api.reply` 的调用方（含既有取消测试断言 `publish` 未被调用）行为逐字不变；只有经 L3 `reply_to_writing` 才启用归档。
- 四角色（`_hollmwood_reply`）路径本轮未改：其角色日志写 `logs/`、角色失败时经 `publish_reports` 出「未采用候选稿」，保全沿用既有机制。

### desktop.py（L4）
- `interrupt_script_agent`：取消本机代次时按「是否在调用 API」标 `costly`，状态栏合并三态说明与可查询编号，并写明「已返回正文会归档到 responses/ 供核对；本机不再把这次回复写入界面或正式采用」；只收本地进程（无 API 在途）时不提计费、不提归档。
- `_tick_async_result`：改为「先经 `BackgroundTaskLifecycle.finish` 判定归属（迟到结果只登记、不交付），再确认仍是当前代次」——与旧判定顺序等价，但让迟到结果进入 `late_results()`。
- `close()` 的「仍在处理」确认框补一句：中断不会撤销远端调用；若在调用付费模型或线上任务，仍可能继续执行并按实际用量计费。

## 契约变化与同步
- `BackgroundTaskLifecycle.cancel()` 记录取消事实（`_cancel`），但 `snapshot()` 的字段与取值**不变**；普通任务的 `cancellation_status()` 返回 `None`。
- `BackgroundTaskLifecycle.finish()` 对非当前代次新增副作用（写入 `late_results()`）；返回值与 `snapshot()` 不变，与既有 `test_desktop_automation_service` 断言一致。
- `writing_api.reply` 新增仅关键字参数 `archive`；`stage_execution_service.reply_to_writing` 新增注入。
- 未新增顶层模块／裸 `json.loads`／L2 直写／`skipTest`；`tests/architecture/_layers.py` 未动。`维护记录/架构统一基数.json` 与 `维护记录/TODO注释快照_20261003.json` **未改**：把新函数放到 `stage_execution_service.py` 末尾、把 `desktop.py` 改动压成等行数单行，避免既有行号位移，首次全量前的架构门禁因此回到 312/312。

## 测试（`tests/test_cancellation_status.py`，13 条）
- 三态与编号：普通取消保持旧快照且 `cancellation_status()` 为 `None`；有成本／远端取消给出 `not-requested`／`pending`／`confirmed` 与「远端仍可能继续执行／不能当作未计费」；未知远端记 `unknown` 且不显示成「没有产生费用」；状态绑定到自己的 ticket。
- 迟到隔离与保全：被拒的迟到 `finish` 记入 `late_results()` 且 `snapshot()` 不变；登记有界（8 条）；未提交过的 ticket 不登记。
- 桌面：`interrupt_script_agent`（API 在途）状态含「本机已停止等待／远端仍可能继续执行／可查询编号：本机批次 7／归档到 responses/」且不含「没有产生费用」；只收本地进程时不提计费／归档；`_tick_async_result` 的迟到结果只登记、不改界面与 `worker`。
- 有成本正文保全：取消后已返回正文经注入 `archive` 留档、路径写进取消错误、不改正式采用；未注入 `archive` 时既有 `publish` 断言不变（`publish` 未被调用）。
- 定向 `-k cancellation_status desktop_automation desktop writing_cancellation writing_response_preservation writing_api writing_restart script_agent_delivery` 131/131；关联 253/253；架构 `--layer architecture --all` 312/312；默认冒烟 8/8。

## 边界
- 项目里没有可调用的「远端取消」接口：本地云端视频经 `local_video`／`video_progress` 以任务编号查询取回，取消本机等待**不撤销远端任务**。故本轮不伪造远端退款或远端取消，只把三态与编号如实展示；「远端取消已确认」只有在调用方拿到远端确认时才为真（当前生产路径恒为 `pending`／`unknown`，测试覆盖 `confirmed`）。
- 四角色（hollmwood）取消路径未接归档通道；其角色日志与「未采用候选稿」保全沿用既有 `logs/`／`publish_reports`，本轮未改。
- 未实机点击桌面「中断」按钮或在真实 Tk 里验收文案换行；桌面用例用注入替身，与服务层同源。
- 「已返回可保全结果」的磁盘保全只覆盖 `reply()` 的普通对话与受控工具两条正文出口（不再只限阶段①②③）；不含远端媒体任务（其成果由各自下载／落盘路径负责）。

## 全量判定
- 1368 − last_full_safe_all_round(1367) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径／Tk 控件生命周期／删除语义／层级登记表；`interrupt_script_agent` 只改状态栏文案与取消标记，未改控件生命周期）。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据为 round=1367、tree=1d7630f1…（2026-10-12，7 日内），但本轮改了 `desktop.py`／`desktop_automation_service.py`／`writing_api.py`／`stage_execution_service.py` 并新增测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：第 1 次在干净 master 谱系工作树 `o41-fullsafe-master`（`git worktree add --detach 467843e`，已预置 4 个嵌套仓库与 3 个被忽略运行文件、`git status` 干净）跑 `--all --safe`：**4872/4872、0 红、524.6 秒**，但该工作树是 detached HEAD，`run_selftests.is_master_checkout()` 为假，按设计**未写绿凭据**。把该工作树 HEAD 指向 `refs/heads/master`（仍停在 `467843e`、树干净）后跑**第 2 次全量** `--all --safe`：**4872/4872、0 红、537.3 秒**并写凭据。`.git/full-safe-receipts.json`：`round=1368`、`tree=dd48d82b7729c8ce00b80a9b8e5ebc1c99b8efd8`（＝内容提交 `467843e:程序`）、`at=2026-10-12T16:15:24`、`last_full_safe_all_round=1368`；`test_desktop_startup_perf`（14 条）／`test_perf_baseline`（9 条）两轮均绿，未出现阈值抖动。

## 提交
- 本轮改动：`程序/desktop_automation_service.py`、`程序/writing_api.py`、`程序/stage_execution_service.py`、`程序/desktop.py`、`程序/tests/test_cancellation_status.py`（新）、`程序/tasks_round/tasks_round_1368_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`。
- 内容提交 `5752dfe`（只含 5 个程序文件：`desktop.py`／`desktop_automation_service.py`／`stage_execution_service.py`／`writing_api.py`／`tests/test_cancellation_status.py`；未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。
- 提交状态：内容提交 `5752dfe`（5 个程序文件：`desktop.py`／`desktop_automation_service.py`／`stage_execution_service.py`／`writing_api.py`／`tests/test_cancellation_status.py`）、`467843e`（`tasks_round_1368_result.md`＋`project_status.md`＋`.agent-handoff/*`）；收尾提交记入全量结果与提交号（沿用同一轮次 R1368，中央 `last_claimed` 仍为 1368）。
