# R2663 结果：简报必填校验前置到输入框，缺字段实时置灰发送（REQ-S01-86）
<!-- round-evidence: {"commit_base": "19e5b068", "credential_hits": 0, "evidence_sha256": "6d6cd344833bba9b", "exit": 0, "failed": 0, "passed": 12, "round": 2663, "tests": "run_selftests.py -k test_idea_send_gate test_script_composer"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1，文档先行）。任务源：优化项 1——「输入创作简报时实时校验必填项，
   缺字段时禁用发送按钮并提示缺哪些字段」。原实现只在发送瞬间经
   `send_message → inline_required_missing` 弹缺字段对话框，用户要发送后才知道
   缺什么；本轮把同一份判据前置到输入框。分支 `codex/wip-R2663`
   （R2648–R2662 为中央计数器空号/他车道）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **9/9** 通过；`smoke_test.py --affected desktop_idea_chat
     desktop_writing_page` 自检门禁 **325 条 / 0 个文件有红**（串行）。
   - 先红后绿：新测 `test_idea_send_gate` 5 条（缺字段置灰＋状态行点名、
     必填齐启用、制作锁计入判据、附件值可满足字段、完整简报追问不拦截、
     防抖合并、附件变更触发刷新）在实现前缺失方法即红，转绿。
   - 门禁抓出一次真实回归：`test_script_composer.
     test_submit_switches_between_send_and_stop`——新项目空草稿被正确置灰后，
     内联发送键 `idea_submit` 转发 `idea_send.invoke()` 被吞。按 §2.4 契约变更
     更新测试（预落 `brief_complete.json` 走已完成简报追问路径），并让
     `_apply_idea_send_state` 改经 `update_script_interrupt_button` 同步内联键，
     保证运行中它仍是可用终止键、不会被置灰。
   - `test_idea_send_gate`＋`test_script_composer` 定向 12/12 绿。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账）。
   - 备注：Tcl `invalid command name "..._apply_idea_send_state"` 属隐藏桌面
     teardown 期 `after` 回调噪音，与既有 `check`/`poll` 同类，非功能失败。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；优化项 1 落地，盘点清单剩余优化 3（段落级采用）、4（快照与对比）、
   规则类改动按队列续排。

## 实现

- `IdeaChatMixin.refresh_idea_send_state()`：`win.after(250)` 防抖，重复刷新
  取消旧回调只留最新（`test_refresh_debounces_through_after` 锁定）。
- `_apply_idea_send_state()`：`_idea_live_missing()` 缺字段→
  `idea_send.state(['disabled'])`＋`status` 写「还缺必填：…」；否则启用并回「就绪」。
  随后调 `update_script_interrupt_button()`——内联发送/终止合一键的状态唯一入口，
  空闲时它本就跟随 `idea_send` 禁用态（既有同步），运行中保持终止可用。
- `_idea_live_missing()` 与 `send_message` 同判据：`preparation_continuation`
  先行短路（已完成简报后的追问/重试不拦），否则 `inline_required_missing`
  合并 `_idea_live_attachment_fields()`——附件参考与 `workflow_lock` 配置值，
  按附件路径集合缓存避免每键重读文件。
- `send_message` 原有缺失弹窗保留为兜底（Enter/程序化调用路径）。
- 挂钩：页面构建尾部、`idea_input` 修改事件、`idea_attachment_paths` setter。
- `test_script_composer` 契约更新：发送/终止切换用例先落完整简报（§2.4，
  断言未弱化）。

## 文档先行（§2.7）

`docs/stages/S01_剧本准备.md`：REQ-S01-86、DES-S01-86、锚点行（`test_idea_send_gate`）。

## 改动清单

- `程序/desktop_idea_chat.py`：实时校验三方法＋附件字段缓存＋发送键状态同步。
- `程序/desktop_writing_page.py`：构建尾部与 `on_modified` 两挂钩。
- `程序/tests/test_idea_send_gate.py`：新测 5 条。
- `程序/tests/test_script_composer.py`：切换用例预置完整简报（契约变更）。
- `程序/docs/stages/S01_剧本准备.md`：REQ/DES/锚点。
- `程序/tasks_round/tasks_round_2641_result.md`：删除——R2642 提交时被扫入的
  空号残留（真身是 `tasks_round_2642_result.md`），本轮顺手清理。

## 提交

`dev.py commit` 一批一轮，凭据见 `tasks_round/evidence/R2663.json`。
