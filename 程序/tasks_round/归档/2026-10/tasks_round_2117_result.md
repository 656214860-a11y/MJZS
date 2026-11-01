# R2117 结果：修掉 R2110 留下的两项架构红（修复轮）

## 问题
- `desktop_idea_chat.py` 1152 行，超出 `test_module_size_ratchet` 的 OVERSIZE_CAPS 上限 1148。
- `test_unification_ratchet` 第四项（裸 `json.loads`）报 `codex_paste.py` 新增一处。实际是 R2110 把解析移进新函数 `_run`，定位键变了，不是新债务。

## 改动
- `desktop_idea_chat.py`：删掉 R2110 新增的 `_attachment_hint`、`_deliver_desktop_app`，派发处改为懒导入 `desktop_send_choice.deliver_desktop_app`。行数 1152 → 1106。
- `desktop_send_choice.py`（同为 L4）：原样接收两个函数，改为公开名 `attachment_hint`、`deliver_desktop_app`，行为不变。行数 186。
- `维护记录/架构统一基数.json`：`codex_paste.py` 那一项的 point 更新为 `_run:json.loads:f6ad03d8d214f995:1`，处置仍为 exempt（外部进程输出解析，非文件读）。
- `tests/architecture/test_complexity_ratchet.py`：参数上限键改为 `('desktop_send_choice.py', 'deliver_desktop_app'): 10`，上限值未动。
- `tests/test_client_profiles.py`：`DeliveryFallbackTests` 三处调用改走 `desktop_send_choice.deliver_desktop_app`，导入同步。断言未动，仅同步调用路径。

## 验证（本轮运行，经 gui_hidden）
- `run_selftests -k client_profiles desktop_attachment_send desktop_send idea_chat script_composer complexity module_size unification`：207 条，全通过。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：410 条，剩 1 项既有红 `test_performance_history_is_declared_as_historical_only`（worktree 下基准历史.json 未入库），非本轮引入。

## 未验证
- 未在真机复测 Desktop 程序粘贴发送；代码为原样搬移。
