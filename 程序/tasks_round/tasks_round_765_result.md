# R765 结果｜修复轮：剧本准备启动 tick 与聊天键盘导航

## 结论

#5 的回归在修复前失败，故不是“3343／3361 已兜住”的假设：首帧完成后，自动续开在 40ms 内切页会命中延后建页守卫并把启动 tick 永久留在暂停状态，创意简报队列也无法消费。已在守卫返回前调用既有幂等解冻入口。#8 已修复，只读聊天记录区的导航键不再被吞；未新增功能、未修改用户项目数据或其他生产模块。

## 根因与改动

- `desktop.py:3798-3810`：延后建页的守卫直接 `return`，而唯一的 tick 解冻调用位于守卫之后。现在返回前调用 `_request_tick_resume_after_first_paint()`；它只在首帧已完成时排入既有恢复任务，不新增轮询。
- `tests/test_desktop_startup_perf.py`：以真实 Tk 临时项目构造“自动续开后 40ms 内切页”，断言 `_startup_tick_paused` 变为 false，且 `_brief_load_results` 被消费一次。修复前该断言失败，修复后通过。
- 实际 `KeyPress` 绑定位于 `desktop.py:3978`（不是鼠标拖动的 3969）。`desktop.py:1033-1049` 在非编辑态放行 Up/Down/Left/Right、Prior/Next、Home/End、Tab 与 Shift+Tab（Tk 的 `ISO_Left_Tab`）；普通字符仍返回 `break`，编辑态的正文边界防护未变。
- `tests/test_idea_chat.py`：保留非编辑态普通字符拦截与既有编辑边界测试，并新增导航键不返回 `break` 的回归。

## 验证

- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop`：9/9，14 条／0 红。
- `python run_selftests.py -k desktop_startup_perf desktop_idea_chat --safe`：0 红（本仓运行器按匹配名选中 `desktop_startup_perf`；聊天回归另以 `tests.test_idea_chat` 直接执行并由完整安全全量覆盖）。
- `python smoke_test.py --architecture`：138/138。
- `python run_selftests.py --all --safe`：本轮因 Tk 事件绑定改动强制执行；3,496 条／0 个文件有红／884.9 秒，`ALL TESTS PASSED`。`last_full_safe_all_round` 已从 R764 推进至 R765。

## J. 整改路线

继续保留真实用户机器的完整冷启动复验挂账：本轮关闭了已可复现的 tick 饿死支路，但不把自动化环境替代为用户现场证据。后续只按缺陷台账处理可观察失败链。

## K. 测试迁移计划

启动守卫与异步结果消费约束归入 `tests/test_desktop_startup_perf.py`；聊天只读态的键盘事件与编辑边界约束归入 `tests/test_idea_chat.py`。两者均使用临时目录／Tk fixture，不访问真实用户项目。
