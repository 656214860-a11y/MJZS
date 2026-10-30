# R2110 桌面模型长任务改附件＋短指令（REQ-S01-70／DES-S01-70）（功能轮）

- 本轮类型：功能轮（§3.1）。日期：2026-10-30。分支 `claude/distracted-gagarin-2ffc8e`（工作树 `happy-jennings-48da69`），起点 `8a330a78`。
- 测试与基线：定向测试、受影响冒烟、默认冒烟均通过（见下）；架构门禁只跑了相关两项，需求锚定门禁有 1 项历史红（REQ-S01-68，非本轮引入）。全量未运行（分支不累计欠账）。
- `project_status.md` 欠账：未减少；分支不改状态页，合入 master 后补记。

## 起因

用户用 Gemini 桌面程序（模型池 `desktop-app`，显示名 Google Gemini 4 Argon）执行剧本准备时，Gemini 报「出了点问题 (1)」。核查 `摄影侠_20260930/工作流任务/writing/ef775d7730930081f4f8.md`：助手把 170 KB、77,010 字的完整任务整篇粘进了输入框（`done()` 读任务文件全文进剪贴板），Gemini 对这么长的单条输入直接报错。

## 改动

- 需求先行：`docs/stages/S01_剧本准备.md` 新增 REQ-S01-70、DES-S01-70，锚定表加 `test_desktop_attachment_send`。
- `desktop_send_choice.py`：新增 `ATTACH_THRESHOLD = 8000` 与 `attachment_payload(engine, task_file, text)`。`desktop-app` 且正文超过 8,000 字、任务文件存在时，返回短指令（点名附件文件名、要求读完附件、附件没上传成功先说明、附交付方式）和任务文件路径；否则原样返回。
- `desktop_idea_chat.py`：`done()` 复制剪贴板前调用 `attachment_payload`；`_deliver_desktop_app` 增加 `attachment`，并把原 `paste`＋`delivery` 两个开关合并为 `delivery`（调用方在 `desktop_paste` 为假时传 `'clipboard'`），以满足复杂度棘轮的参数上限。新增 `_attachment_hint()`：不自动粘贴、未找到程序或粘贴失败时，补充「把任务文件作为附件上传」的说明并经 `platform_tools.open_path` 打开任务文件所在文件夹。
- `codex_paste.py`：抽出 `_run(payload, deadline)`，新增 `paste_attachment(title, prompt, attachment, *, program, app_name, deadline_seconds=45)`；`paste_existing` 签名不变。
- `codex_paste.ps1`：载荷有 `attachment` 时，聚焦输入框后先 `Clipboard.SetFileDropList` 并 Ctrl+V 粘贴文件，等 1.5 秒，再粘贴短指令；回执提示「请确认附件已出现再手动发送，没有出现就把任务文件拖进对话框」。
- `tests/test_client_profiles.py`：`_deliver_desktop_app` 的 3 处调用随签名去掉位置参数 `True`（`delivery='clipboard'` 保留）。断言未动。
- 新测试 `tests/test_desktop_attachment_send.py`（6 条，REQ-S01-70）：长任务转短指令＋附件；短任务、Claude Desktop、任务文件缺失时不变；自动粘贴走 `paste_attachment` 且不调 `paste_existing`；粘贴失败与仅复制时提示上传并打开文件夹；附件路径进入 PowerShell 载荷，`paste_existing` 载荷不含该字段。

## 验证（本轮实际运行，经 `工作流任务/gui_hidden.py`）

- `run_selftests.py -k complexity_ratchet desktop_attachment_send`：10 条，0 个文件有红。
- `run_selftests.py -k desktop_attachment_send desktop_idea_chat_desktop_paste desktop_send_ledger client_profiles codex_paste requirement_traceability complexity_ratchet workflow`：185 条，唯一红项为 `test_requirement_traceability` 的 REQ-S01-68（见下）；本轮测试文件修正一处 `captured` 未清空后复跑通过。
- `smoke_test.py --affected desktop_idea_chat codex_paste desktop_send_choice client_profiles`：9/9 通过。
- `smoke_test.py`（默认）：8/8 通过。
- 先红后绿：首次跑复杂度棘轮红（`paste_existing` 8 > 7、`_deliver_desktop_app` 11 > 10），按上述方式收拢后绿。
- 未运行：真实 Gemini 窗口里「粘贴文件即成附件」的端到端效果（需要用户在 Gemini 里实测一次）；`--architecture` 全部门禁；全量。

## 历史欠账（未处理，范围外）

- `test_requirement_traceability`：REQ-S01-68 ✅ 无测试锚定。原因是 R2105 合并时 R2098 的需求从 REQ-S01-62 改号为 68，`test_download_inbox`／`test_idea_download_import` 的 docstring 仍写 REQ-S01-62。本轮改动前即存在。

## SKILL 引用瘦身评估（只评估，未改）

`workflow_settings._skill_blocks()` 把阶段 SKILL 里每个直接 Markdown 链接的**整份文件**内联，既不看链接上的锚点，也不看正文里的「仅……时追加」条件。以本次 77,010 字的任务为例，SKILL 引用 11 段约 6 万字：

1. 条件不满足仍被内联：项目是国内剧、原创，但 `sd-overseas-engine`（6,111 字）、`sd-jieshuo-engine`（7,471 字）、`sd-recon-engine`（5,739 字）全文都在，合计约 1.9 万字。
2. 只要一节却内联全文：`sd-decision-engine` 只需「四、工作流程」（全文 3,910，该节 611）；`sd-script-engine` 只需「六阶段链」「长剧批次合同」（全文 9,545，两节约 1,300）；`dialogue-speed-check` 只需「三、五步自检流程」（内置版全文 7,523，该节 319）。按锚点截节约可再省 1.5～2 万字。
3. 两项合计任务约可从 7.7 万字降到 4 万字左右。与 R2103「SKILL 变强制完整」的决定相冲突，需用户拍板后另开一轮。

## 提交

见提交记录（`dev.py commit`）；未 push。
