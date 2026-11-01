# R601｜性能轮：剧本 Agent 续发提示词去重

## 本轮结论

- 剧本准备桌面 Agent 的续发不再重复构造完整 `script_prompt`；改为携带短续接约束和本轮创意素材。
- 当前配置的 SKILL 与阶段交付契约仍由 `prompt_with_settings()` 注入，项目续接摘要仍由 `continuation_instruction()` 注入，因此没有削弱剧本阶段边界或四角色/API 路径质量要求。
- 回归增加“续发短于首次提示词”的断言，防止以后重新把整份工作流塞入已建立的 Agent 会话。

## 改动文件

- `workflow_tasks.py`：`script_followup()` 的 writing 分支改为短续接任务。
- `tests/test_workflow.py`：补充长度回归断言。

## 验证

- `tests.test_workflow`：82/82 通过。
- `python smoke_test.py --affected workflow_tasks desktop`：9 项通过，定向自检 7 条、0 红。
- `python smoke_test.py --architecture`：101/101 通过。
- `python smoke_test.py`：8/8 通过。

## 后续

- 附件首次入库仍须读取并验证用户选择的文件；将其后台化须同时处理“未完成上传不得发送”的 UI 状态，不能仅把 I/O 丢进通用 `async_()` 后与模型请求竞争同一请求票据。
