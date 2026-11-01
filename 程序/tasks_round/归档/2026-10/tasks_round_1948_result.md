# R1948 结果：三虎弹窗节制——有待办才弹、停留随操作伸缩、主动关闭逐次加长安静期（功能轮）

## 背景
（本轮先领到 R1946，提交前中央计数器已被其他会话推到 1947，按领号脚本重领为 R1948。）

用户 2026-10-23 原话：不需要用户每次切换页面都弹窗，只有存在待办任务时才弹窗提醒，尽量能不弹窗就不弹窗，减少性能损耗与页面加载消耗；弹窗后停留偏久，要结合用户操作——零操作时停久一点，频繁操作时短暂停留，主动关闭要减少对用户的打扰。

查到的现状：
- 换页必弹：`desktop.py` 每次换页都挂 150ms 定时器调 `pet.enter_stage()`；提示档／暂停时一律播“当前进度”，半自动档 `force_prompt=True` 绕过了第 45 期的 `stage_needs_user` 判据。
- `pet_cloud_timing._arm_hold` 忽略传入的 hold，一律 `PET_CLOUD_AUTO_CLOSE_MS = 10000`。
- 单击收起只静音 `CHAT_MUTE_SECONDS = 30` 秒，反复关闭也不加长。

## 改动
- 新增 `pet_ui_popup.py::PetPopupMixin`（Pet 第 5 个 Mixin，只读内存，不读盘不建控件）：
  - `stage_has_todo(index)`：待办只认三种——全自动档本阶段尚未派发；本阶段有失败待确认；阶段状态为 `failed`／`blocked`（`STAGE_TODO_STATES`）。暂停、免打扰、刚点掉云朵的安静期一律不算（全自动派发除外）。
  - `note_activity()`／`cloud_dwell_ms()`：最近 `PET_ACTIVITY_WINDOW_SECONDS`（20 秒）内的切页与按钮点击（复用 `_busy_taps`）——0 下停 `PET_CLOUD_IDLE_CLOSE_MS`（15 秒），满 `PET_ACTIVITY_BUSY_COUNT`（4）下停 `PET_CLOUD_BUSY_CLOSE_MS`（5 秒），其余 10 秒。
  - `dismissed()`：`PET_DISMISS_WINDOW_SECONDS`（10 分钟）内第 1／2／3 次起主动点掉云朵，安静 30 秒／2 分钟／5 分钟（`PET_DISMISS_MUTE_SECONDS`）。
- `pet_ui_stages.enter_stage`：先问 `stage_has_todo`，没有待办直接返回空串。
- `desktop.py` 换页：先经 `desktop_pet_bridge.pet_stage_wanted()` 记一笔切页并问待办，没有就不挂播报定时器；取消旧定时器的几行收紧，Desktop 类行数不变。
- `pet_cloud_timing._arm_hold`：空闲收起时长改问 `pet.cloud_dwell_ms()`，宠物没有该方法或抛异常时退回 10 秒。
- `pet_ui.py`：单击收起的 `mute` 回调改走 `dismissed`；`Pet` 继承 `PetPopupMixin`。
- `ui_tokens.py`：新增上述 7 个常量；`pet_ui_support.py`：`STAGE_TODO_STATES`。
- 登记：`tests/architecture/_layers.py`（L4）与 `_scan.PET_UI_PARTS` 加入 `pet_ui_popup`；`architecture.md` 补一句；覆盖率基线用原 8 组目标重跑刷新（306→307 模块），`runbook.md` §11 数字同步。
- 顺手修 R1945 遗留：`tests/test_page_paint_freeze.py` 的 skip 常量用了 `as` 别名，卫生门禁认不出，改为直接引用 `PLATFORM_WINDOWS_ONLY`；6 条 skip 补登 `维护记录/skip台账.json`（只追加）。

## 契约变更（测试同步说明）
- `test_pet_ui.StageEntryTests`：提示档、半自动档两条用例先压一条剧本阶段失败待确认（新增 `pend_script_failure`），原断言未动。
- `test_pet_ui.StageEntryTests.test_auto_runs_the_stage_once_and_asks_to_confirm_script_result`：第二次进页原断言“等于最近一句进度”，按新契约改为返回空串（已派发且无待办时不开口）。这一条是期望值随契约变更，已在用例里注释。
- `test_pet_ui.FadeAndReadTests.test_the_armed_hold_matches_the_reading_time`：先 `note_activity()` 落到“正常操作”档，断言（等于 10 秒配置）未动。
- `test_page_cache.test_navigation_cancels_old_stage_announcement`：mock `pet_stage_wanted=True`，断言未动。

## 测试（经 `工作流任务/gui_hidden.py` 隐藏桌面运行，本轮实跑）
`run_selftests.py -k pet_ui pet_popup_policy pet_cloud pet_chat page_cache page_paint_freeze desktop_startup_perf architecture complexity function_size`：1074 条，红 8 条，全部与本轮无关：
- `test_pet_ui` 5 条“需要登录账号”：R1913 起的已知旧红。
- `architecture.test_copy_entry_boundary`：`desktop_account_page.py`（R1925 引入，本轮未碰）。
- `architecture.test_round_baselines`：状态页轮次头只在 master 改，分支上必红，合并轮同步。
- 新增 `tests/test_pet_popup_policy.py` 10 条全过；复杂度／函数体量门禁通过（未抬登记值）。

未运行：smoke_test、全量 selftest、真机观感。

## 待用户
真机确认：换页无待办不弹；零操作时云朵停得久、连点时停得短；连续点掉云朵后安静期变长。本分支叠在 R1945 之上，合并轮一起做。
