# R2051 登录闸期间三虎不弹窗（功能轮）

轮次类型：功能轮。日期：2026-10-25。

- 现象：未登录时启动登录闸还盖着界面，三虎的缺口播报与一键执行提议却弹在登录表单上。
- 改动：
  - `pet_ui_popup.login_locked()`：宿主 `login_gate_active` 为真即锁；`can_pop()` 随之为假，自动播报、招呼（会自行重排）、心跳都不再弹。
  - `pet_ui_voice.speech_blocked`：闸门期间把话压住（`bstate.hold`），闸门过后由 `pump` 补说；`open_chat` 闸门期间不建云朵。
  - `pet_cloud.Cloud.show`：唯一显示出口加闸门判断，播报／进度／提议／对话框任何入口都弹不出（拖动推迟与它并成一个条件，不增行数）。
  - `desktop_login_gate.show_login_gate`：闸门出现时若云朵已露着，顺手收起。
- 测试：新增 `tests/test_pet_login_quiet.py`（3 条：闸门期间各入口不弹且压住、闸门过后补说、已露着的云朵被收起）。
- 验证：`run_selftests -k pet cloud offer broadcast login` 仅剩 test_pet_ui 已知 5 条红（登录闸拦住自动分镜／无人值守用例，与本轮无关）；默认冒烟通过；`--architecture` 剩 2 条红：`test_agents_md` 在 master 同样红，`test_skill_reference_injection` 因本工作树缺未跟踪的 skill 文件（master 通过）。size 上限未动（pet_cloud 1357、pet_ui_voice 1201 持平）。
- 断言未动。未运行 `--all --safe`、真实界面目测。未 push。
