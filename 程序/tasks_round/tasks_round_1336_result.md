# R1336：O13 剧本准备把“对话、工作稿、正式采用”显示为明确状态

类型：功能轮（§3.1），承接 R1267 清单 O13（O01—O12 已完成）。中央轮次 1336。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 139/139（`writing`）、关联 46/46（`idea_inline_brief writing_response_preservation`）、桌面 115/115（`ui_edges`）、架构相关 22/22（`todo_comment_snapshot unification_ratchet layers writing_publication_boundary writing_api_json_boundary writing_preparation_path_boundary dynamic_import_registry no_circular_import import_error_boundaries`）、默认冒烟 8/8，全 0 红。
- 欠账：O13 关闭，清单剩 O14—O48；本轮号 1336 − 上次绿全量 1330 = 6 ≥ 5，收口安全全量已跑：干净 master 工作树第 1 次 4542/4542、385.8 秒、0 红，凭据 round=1336、tree=d934dd21，last_full_safe_all_round 刷到 1336。

## 问题
- 剧本准备的模型回复只把原始正文放进对话气泡；气泡里有字，但用户分不清它到底是「已归档的未采用原始响应」「待确认的阶段工作稿」还是「已发布的正式剧本」。
- 未采用（格式不合格、截断、正文为空）、模型调用失败、版本变化未采用、取消后迟到这几类回复，落点和下一步只散落在 `error` 字符串里，界面没有统一说法，容易被当成已经采用。
- `responses/` 归档目录与正式阶段／自然剧本目录没有在提示里区分。

## 实现
- `writing_api.preparation_reply_state(result)`：一次剧本回复的唯一状态判据，返回 `{state, file, reason, next_step}`，四态为「已采用／阶段稿待确认／原始响应已保存／因版本变化未采用」；无显式标签时按 `natural_script_path → preparation_path → response_path` 既有键回退。
- `writing_api.preparation_reply_message(result)`：把状态、落点与下一步合成一句可显示的话；无明确状态时返回空串，调用方沿用原提示。
- `_preparation_step` 在各类返回上打标：格式不合格／截断／正文为空／模型调用未成功＝`preparation_status='原始响应已保存'`＋`preparation_reject` 原因；成功发布阶段稿＝`阶段稿待确认`；版本变化被 `_versioned_publisher` 拒绝＝`因版本变化未采用`。`saved` 文案改为「原始响应已保存（responses/ 归档，不等于正式采用）：<path>」，取消后迟到抛出的错误也带这句。
- `desktop` 剧本回复处理器（`received`）改用同一判据：未采用／版本变化、阶段稿待确认、自然剧本已发布三处状态栏都走 `preparation_reply_message`，没有明确状态时才回退旧文案。气泡仍显示原始正文（那是「对话」），状态栏负责说清它是归档还是正式采用。
- 不补写、不采用历史稿：`responses/` 归档只落盘、不登记阶段台账；未采用分支不碰 `preparation_state.json`。

## 验证
- 新增 `tests/test_writing_response_preservation.py::PreparationReplyStateTests` 3 条：状态判据区分四态且无状态时消息为空串；确认成功后状态为「阶段稿待确认」且消息含路径／待确认／确认；取消后迟到的错误消息含「原始响应已保存」「不等于正式采用」与归档路径，且台账文件未变。
- 扩展既有 2 条：格式不合格／截断的响应带 `原始响应已保存` 与原因标签、消息点明 `responses/` 归档不等于正式采用；版本变化经 `reply_to_writing` 返回的结果带 `因版本变化未采用`。
- 定向 `-k writing` 139/139、0 红；关联 `-k idea_inline_brief writing_response_preservation` 46/46、0 红；桌面 `-k ui_edges` 115/115、0 红；架构相关 22/22、0 红；默认冒烟 8/8。
- 台账：`desktop.py` 新增 1 行，`TODO注释快照_20261003.json` 的 desktop.py 注释行号 2748→2749 同步；`writing_api.py` 未触碰 `json.loads`（第四项 point 486 不变），`stage_execution_service.py` 未改。

## 收口
- 收口安全全量（干净 master 工作树 `o07-fullsafe-master`，`run_selftests.py --all --safe`）：第 1 次 4542 条用例、385.8 秒、0 文件红，`test_desktop_startup_perf` 与 `test_perf_baseline` 均通过；内容树全量凭据已刷新 round=1336、tree=d934dd219a8ff155f7330220e12081af3f4efabc，`last_full_safe_all_round` 刷到 1336。
- 首跑即绿，无需定向修复；本收口文档提交在绿凭据之后，文档树与凭据树不同树（同 O09／O10 口径）。

## 风险与边界
- 状态判据只说明「这一次回复落在哪里」，不是采用凭据；正式采用仍由 `preparation_state.json`／`natural_script_selection.json` 决定，本项不自动采用任何归档。
- 「已采用」标签对应已发布的自然剧本文件（`natural_script_path`）；是否定为本集当前采用稿仍看选择台账，消息里已说明要在剧本列表里确认采用。
- 未重启应用、未真实点击界面；单元与静态验证不等于真实交互验收。Tk 状态栏只是文案改动，不命中 §5 强制全量条件，但本轮已到五轮周期，收口仍补一次全量。

[TASK_COMPLETE] 剧本准备回复有唯一状态判据与可显示消息（已采用／阶段稿待确认／原始响应已保存／因版本变化未采用），带落点文件与下一步；未采用（格式不合格／截断／正文为空／模型失败）都落在 responses/ 归档并明确不等于正式采用，取消后迟到与版本变化的错误消息同样带这句；不补写、不采用历史稿；定向 139/139、关联 46/46、桌面 115/115、架构 22/22、默认冒烟 8/8，0 红。
