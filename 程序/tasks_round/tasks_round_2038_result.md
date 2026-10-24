# R2038 三虎对话框精简：去重复、去噪前缀、短提议（修复轮）

轮次类型：修复轮。日期：2026-10-25。

## 起因
用户反馈三虎对话框“没有可读性，重复过多，看着很累”。截图 5 行里，缺口播报和一键提议交替出现，第 2/4 行、第 3/5 行完全相同；开机招呼前还挂着“【步骤 1/1】”。

## 根因
- `pet_cloud._body_text` 只合并**相邻**的重复行，缺口与提议交替时一条也合并不掉。
- 开机招呼经 `_prefix_output` 取不到阶段时退回 `Broadcaster.step(1, 1, …)`；`Cloud.append` 只剥“【阶段 n/n】”，不剥“【步骤 n/n】”。
- 提议句“还差：…。要我「一键执行」不花钱的部分吗？回「好」开工，「先不用」先放着。”冒号重复，措辞冗长。

## 改动
- `pet_cloud.py`：
  - 云朵框显示时，同一句不论是否相邻只留最后一次（`self.lines` 历史不改）。
  - `append` 同时剥掉“【步骤 n/n】”前缀；日志里仍保留前缀。
- `pet_ui_voice.py`：提议句改为“三虎：还差 X等 N 件事，要我一键执行免费的部分吗？回「好」开工／「先不用」。”
- 开机招呼原文是用户亲定的，有测试锁定（`test_pet_ui.py:3159`），未改。

## 测试同步
- `tests/test_pet_cloud_r1449.py`：原用例锁的是“只合并相邻重复”（`['same','same','different','same']` 期望出现 2 次），与本轮契约变更相反。改为期望出现 1 次，并把用例名改为 `test_tokens_and_exact_deduplication`。新断言同样严格；其余断言未动。
- `tests/architecture/test_complexity_ratchet.py`：`Cloud` 类行数上限按门禁提示由 1113 下调到 1112（只降不升）。

## 验证（本轮实跑）
- `run_selftests -k pet cloud offer broadcast`（隐藏桌面）：
  - 新增的红只有 r1449 那 1 条，已按上文同步，复跑 `-k r1449 offer_brevity broadcaster` 全绿。
  - `test_pet_ui` 另有 6 条红：5 条 `DesktopPetSeamTests`（被登录闸“需要登录账号”拦下）＋ 1 条 `CloudTests.test_the_cloud_stands_left_of_the_pet…`。把本轮两个源文件还原后复跑，同样是这 6 条红，属既有红，与本轮无关。
- 默认冒烟通过。
- `--architecture`：
  - 复杂度棘轮已绿。
  - 余下 3 条与本轮文件无关：`test_round_number_continuous`、`test_script_stages_name_only_their_approved_00_references`、`test_performance_history_is_declared_as_historical_only`。

## 未运行
`--all --safe`、真实界面目测。未 push。
