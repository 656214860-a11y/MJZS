# R1697 修复轮（含全量基线验证）：清掉后台全量那条偶发红 + 9 条与本机模型池相关的红

> 执行者：opencode flash。只改文件、跑测试；**未提交 git、未改 `project_status.md`、未领轮次**（轮次 1697 由 Claude 领取，验收与提交由 Claude 做）。

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（含全量基线验证）。两组红都按「先复现 → 定位根因 → 最小修复 → 复测失败项 → 适用回归」处理；改动**全部落在 `程序\tests\` 三个测试文件**，未动任何生产源码（`程序\*.py` 一行未改），故未跑 `smoke_test.py --architecture`（任务书「验证」第 3 条：只有改了生产模块才跑）。
2. **测试跑了吗？三个基线过了吗？** 过了。默认冒烟 `smoke_test.py` 通过（**通过 9 / 失败 0**）；`smoke_test.py --gate` 通过（**ALL TESTS PASSED，通过 9 / 失败 0，退出码 0**）；定向 `run_selftests.py -k test_idea_chat test_workflow` → **ALL TESTS PASSED**（实际跳过 0 条，退出码 0）；`run_selftests.py -k asset_thumbs` **连跑 10 次 → 10/10 全绿**。
3. **project_status.md 的欠账少了吗？** 未减少。本轮只改测试、不改生产源码，按 §5「改过源码的轮次」口径不新增全量欠账；后台全量那条偶发红已在本轮闭环，但欠账计数归属由 Claude 验收时裁定（我未写状态页）。

## A 根因

### 组一：`test_asset_thumbs` 偶发红（后台全量唯一红，1 条）
**一句话根因**：用例结束时后台缩略图 worker 进程仍在读临时目录里的 `cache/jobs/<hash>.json`，`TemporaryDirectory.cleanup()` 先把目录删掉 → `PermissionError [WinError 32]`。

**证据**
- 权威堆栈（`程序\logs\auto_full_safe.log` 第 3603–3632 行，标题即「### test_asset_thumbs（1 条红）」）：
  - `test_the_same_picture_is_only_built_once (test_asset_thumbs.ThumbnailTests...)`
  - `PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问。: '...\tmpogp8z7cx\cache\jobs\7157b04399af61bbe339.json'`
  - 触发点：`tempfile.py:975 cleanup → ... → shutil._rmtree_unsafe os.unlink`。
- 该用例结尾是「同一张图只建一次」——会留下一个待收的后台任务；单跑时进程/缓存状态简单，所以**未复现**（见 C：修前单跑 5/5、连跑 30/30 全绿）；只有在后台全量（多模块并行、worker 存活更久）下才撞上删目录。
- `asset_thumbs` 已具备收尾口：`forget()`（清内存缓存 + `after_cancel` 轮询定时器，`asset_thumbs.py:464`）与 `reset_worker()`（`terminate()+wait()` 回收后台进程，`asset_thumbs.py:480`）；`setUp` 里本来就用这两个换缓存目录（`:140-141`），只是**退出时没再收一次**。故修复是补测试收尾，不是改生产代码。

### 组二：9 条红（`test_idea_chat` 7 条 + `test_workflow` 2 条，共因）
**一句话根因**：这些用例读到了**本机真实模型池**（`配置/宠物/配置.json`），其中没有内建 `deepseek-v4-flash` / `deepseek-v4-pro`，于是阶段引擎从 qwen/deepseek **回落成 codex**、模型身份解析成「自定义」、请求被**误路由进 Agent 路径**（该路径 `desktop_idea_chat.py:1308` 才读 `result['receipt']` → `KeyError: 'receipt'`）。

**证据**
- 本机真实池 id（`配置/宠物/配置.json`，12 条，**无内建 `deepseek-v4-flash` / `deepseek-v4-pro`**）：
  `['chatgpt-desktop','claude-desktop-app','gpt-6-astra','claude code cli','claude-opus-5.5','deepseek-flash','deepseek-v4.1-flash-free','deepseek-v4-pro-0813','Google Gemini 4 Argon','Qwen-3.8-Max','qwen-image-3.0','qwen3.8-max']`。
  内建池 `model_pool.BUILTIN` / `default_pool()`（`model_pool.py:89-128`）里才有 `deepseek-v4-flash`。
- 修前失败原文（本轮 `-k test_idea_chat test_workflow` 复现输出，9 个 `=====` 失败头；临时产物已清理）：
  - `test_deepseek_api_model_never_falls_back_to_codex` / `test_summary_uses_the_same_stage_model_route_as_dispatch`：`AssertionError: 'Qwen Code（阿里云） · deepseek-v4-flash' not found in '调用：ChatGPT / Codex · ChatGPT / Codex · short-drama-storyboard'`（期望 qwen，实得 codex 回落）。
  - `test_saved_reply_uses_provider_and_model_subdirectories`：`Tuples differ: ('自定义', 'DeepSeek V4 Flash') != ('DeepSeek', 'DeepSeek V4 Flash')`（模型不在池里 → 身份解析成「自定义」）。
  - `test_model_history_is_stored_by_stable_id_and_imports_legacy_rows`：稳定 ID 目录断言失败（同样源于池里没有该内建模型）。
  - `test_process_poll_preserves_waiting_api_request` / `test_queued_request_does_not_follow_project_switch` / `test_interrupt_removes_only_its_queue_ticket`：`Lists differ: [(<function IdeaChatMixin.open_flow_agent...>)] != []`（请求没进「排队等直接 API」，反而去调了 `open_flow_agent`，即被误判成 Agent 路由）。
  - `test_direct_model_failure_ends_an_active_script_stage`：`Lists differ: [] != [('stage.failed', {...'error': '模型调用未完成：模型未生成导演正文'})]`（没走直连 API，故没发出 `stage.failed`）。
  - `test_direct_reply_failure_shows_the_error_and_next_request_is_accepted`：`File "desktop_idea_chat.py" ... pending.pop()({'ok': False, 'error': '模型未返回可显示正文'}) → KeyError: 'receipt'`。
- `KeyError: 'receipt'` 溯源（任务书要求的 `git log -S`）：
  - `git log -S "receipt" --format="%h %ad %s" -- 程序/desktop_idea_chat.py` → `7ed80c3a`(R1593)、`28dad35f9`(R1592)、`4aea70d9`(R1490，拆分 desktop.py 时随方法迁入)。
  - 读源码：Agent 路径在 `desktop_idea_chat.py:1302-1304` 明确 `result=prepare_task(...); result['receipt']=receipt; ... return result`——**真实运行时 result 必带 receipt**；只有测试 mock 的 `pending.pop({'ok': False, 'error': ...})` 不带。即该异常是「请求被误路由到 Agent 路径」的**连带现象**，不是源码回归；池隔离修好后用例走直连 API 路径，不再读 receipt。**故未改源码**（如 Claude 认为真实缺池环境下该更宽容，需另开修复轮，见 D）。

## B 改动（逐文件，全部在 `程序\tests\`，共 +29 行 / -0 行）

1. **`程序\tests\test_asset_thumbs.py`（+5 行）** — `ThumbnailTests.setUp`
   在 `CACHE_ROOT` 还原那次 `addCleanup`（`:142`）之后追加两次注册：
   ```python
   # 收尾口（addCleanup 后进先出，故注册在 CACHE_ROOT 还原之后、TemporaryDirectory 清目录之前）：
   # 先撤下本拍待收任务、取消轮询定时器，再 terminate+wait 收掉后台进程。否则后台进程可能仍按着
   # cache/jobs/*.json 在读，临时目录清理会撞上 WinError 32「另一个程序正在使用此文件」。
   self.addCleanup(asset_thumbs.reset_worker)
   self.addCleanup(asset_thumbs.forget)
   ```
   利用 `addCleanup` 的**后进先出**：执行顺序为 `forget()` → `reset_worker()` → `CACHE_ROOT` 还原 → `tmp.cleanup()`，即**先撤待收任务、再收后台进程、最后才删临时目录**。用的是生产已有的 `forget()`/`reset_worker()`，没加 `ignore_cleanup_errors`、没吞错。

2. **`程序\tests\test_idea_chat.py`（+17 行）** — 5 处加「注入内建模型池」隔离：
   - `SavingTests.test_saved_reply_uses_provider_and_model_subdirectories`（`:364`）
   - `SavingTests.test_model_history_is_stored_by_stable_id_and_imports_legacy_rows`（`:569`）
   - `SendMessageTests.queued_api_request` 辅助方法（`:1369`，覆盖 `test_process_poll_preserves_waiting_api_request`/`test_queued_request_does_not_follow_project_switch`/`test_interrupt_removes_only_its_queue_ticket` 3 条）
   - `SendMessageTests.test_direct_reply_failure_shows_the_error_and_next_request_is_accepted`（`:1523`）
   - `SendMessageTests.test_direct_model_failure_ends_an_active_script_stage`（`:1548`）
   每处同一句（`patch` 已在本文件 `:21` 导入）：
   ```python
   import model_pool
   self.enterContext(patch('model_pool.pool', return_value=model_pool.default_pool()))
   ```
   即把「读本机真实池」换成「读内建池」，`enterContext` 在用例结束时自动还原。

3. **`程序\tests\test_workflow.py`（+7 行）** — 2 处同样隔离：
   - `DesktopModelPoolTests.test_deepseek_api_model_never_falls_back_to_codex`（`:1072`）
   - `DesktopModelPoolTests.test_summary_uses_the_same_stage_model_route_as_dispatch`（`:1089`）
   ```python
   import model_pool
   self.enterContext(patch.object(model_pool, 'pool', return_value=model_pool.default_pool()))
   ```

未改任何生产模块、未改 `skills/`、`docs/`、`architecture.md`。

## C 验证（命令与实测数字）

| 命令 | 修前 | 修后 |
| --- | --- | --- |
| `run_selftests.py -k test_idea_chat test_workflow` | **9 条红**（本轮复现输出内 9 个失败头） | **ALL TESTS PASSED**；实际跳过 0 条；退出码 0 |
| `run_selftests.py -k asset_thumbs` | 单跑 **5 次 → 5/5 PASS**；再连跑 **30 次 → 30/30 PASS**；偶发只在后台全量出现（见 A 组一堆栈） | **连跑 10 次 → 10/10 PASS** |
| `smoke_test.py` | — | **通过 9 / 失败 0**，退出码 0 |
| `smoke_test.py --gate` | （早前基线 gate 输出 = 恰好 9 条已知红） | **ALL TESTS PASSED，通过 9 / 失败 0**，退出码 0；本轮 `test_pet_ui` 未复现 |
| `smoke_test.py --architecture` | 未运行 | **未运行**（未改生产模块，按任务书第 3 条不升级） |
| `run_selftests.py --all --safe` | 未运行 | **未运行**（任务书明令不跑） |

补充说明：
- 本轮 `--gate` 的增量台账已被前面的 `-k` 跑刷新，故 gate 的**增量集合不含** `test_idea_chat`/`test_workflow`/`test_asset_thumbs`（台账认为这三个文件已是最新）。这三个文件的可信绿以**上面的定向 `-k` 结果**为准；gate 作为门禁整体仍全绿。
- 修前复现口径按任务书如实记录：`-k asset_thumbs` 单跑**没有**复现偶发（5/5、30/30 全绿），偶发的唯一权威证据是后台全量日志的 `PermissionError [WinError 32]`；修复后单跑 10/10 全绿，且修法直接消除该堆栈的触发条件（后台进程不再越过临时目录清理）。

### 断言未动

**没有改动、弱化或删除任何既有断言，没有新增任何 skip**。本轮的改动只有两类：(1) `test_asset_thumbs` 的 `setUp` 追加两个 `addCleanup` 收尾口；(2) `test_idea_chat`/`test_workflow` 共 7 处 `enterContext(patch(model_pool.pool → default_pool()))` 的**测试隔离**——把「读本机真实用户配置」换成「读内建池」。这属于任务书硬规矩明确允许的「测试隔离（把读真实用户配置的地方改成注入临时配置）、补等待/收尾」，断言形式与期望值一字未动。修后 9 条全部由**红转绿**，且此前为绿的用例保持绿（`-k test_idea_chat test_workflow` 全量 ALL TESTS PASSED，0 跳过）。

## D 留给 Claude 裁决

1. **`KeyError: 'receipt'` 未改源码。** 我的判断是：它是「本机池缺内建模型 → 请求被误路由进 Agent 路径」的连带现象，非 `writing_api`/`desktop_idea_chat` 的真实回归（真实 Agent 路径 `:1304` 必写 `receipt`）。故只做测试隔离。**若 Claude 认为真实缺池环境（用户从「模型管理」删掉了内建 `deepseek-v4-flash`/`deepseek-v4-pro`）下 `dispatch` 应容忍缺失 receipt**，则需另开修复轮改源码——这超出本轮「测试隔离」的授权范围，我没动。
2. **本机模型池缺内建模型是否算产品缺陷**：真实池 12 条里没有 `deepseek-v4-flash`/`deepseek-v4-pro`（内建池有）。我不确定这是用户有意删除还是环境漂移；只记录，未改。
3. **`test_pet_ui.ReplyBoxTests.test_the_reply_box_sends_what_the_user_typed` 是本轮范围外的偶发红**：带我的改动时，早前两次 `--gate` 里它曾以**临时目录清理竞争**失败（`OSError [WinError 145] 目录不是空的`／`PermissionError [WinError 32]` 落在 `...\p\model_diagnostics\*.tmp`）；但**基线**（改动还原到 HEAD 的 gate 输出）里它**没红**，本轮新跑的 `--gate` 也**没红**。单跑 `-k test_pet_ui` = 599 条 0 红。它不涉及我改的三个文件或它们的生产模块，判为**范围外预存偶发**（该用例不 `drain` 异步 `cloud.submit()`，同文件的 `test_the_reply_box_is_locked_while_the_pet_is_thinking` 会 drain）。**未修**，交 Claude 决定是否另轮处理。
4. **`--gate` 的增量集合覆盖**：如上述，本轮 gate 未覆盖我改的三个文件（台账已刷新）。若 Claude 验收要求 gate 必须覆盖这三个文件，可先 `--affected idea_chat workflow` 或重置台账后再跑——但这会改动共享增量状态，超出本轮只读/改测试的范围。

## E 提交

**未提交，由 Claude 验收后提交。** 我未动 git 状态（未 `add`/`commit`/`stash`）、未改 `project_status.md`、未领轮次。改动文件（`git status --porcelain` 应显示为已修改）：
- `程序\tests\test_asset_thumbs.py`
- `程序\tests\test_idea_chat.py`
- `程序\tests\test_workflow.py`
