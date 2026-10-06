# R1082 Codex 粘贴诊断与冷启动等待

- 类型：修复轮。用户任务书编号 R1079 已被既有报告占用，使用中央领取的 R1082，不覆盖历史。
- 验证：定向 4/4、受影响冒烟 9/9、默认冒烟 8/8；架构仅完整安全全量欠账失败。正式安全全量被脏树前置阻断。
- 欠账：未减少，TASK_BLOCKED；不把本轮诊断能力交付当作自动粘贴成功或正式全量通过。

## 改动与安全边界

Python 透传 deadline_seconds（默认 15），新任务为 45 秒；PowerShell 支持参数和 payload.deadline，保留 450ms 稳定节奏。失败 reason 追加结构化摘要，返回可选 diagnostics，界面追加展示且避免重复。诊断只输出窗口序号、计数和类别，不输出标题、Name、正文或项目路径。

保留原发送函数和粘贴安全块，经与 HEAD 逐字对照一致：不粘贴旧剪贴板、粘贴派发后不重试、不重复 Send、不按 Enter 兜底、保留用户草稿。不改 prepare_task 和投递架构，不放宽 Name 或窗口身份判据。

使用 minimal-diff-fix 与 diagnosing-bugs：先新增失败回归，再限定在三个生产模块内实现并实地取证。project_status 中未定位到 SG-01 标题；仍严格不修改用户项目数据。

## 实地探针原始诊断

用指定 d0735 任务首行构造新任务深链。首行实测 UTF-8 为 58 字节；不保存正文，不修改 prepare_task。随后执行 PowerShell STA，diagnostic=true、auto_send=false、deadline=45。进程路径属于 OpenAI.Codex_26.901.6511.0 WindowsApps 包。探针退出码 0，ok=false，send_dispatched=false。

```json
{"windows":[{"draft_match_count":0,"index":1,"header_count":0,"stable_count":30,"named_editor_count":0,"categories":["header-not-found","editor-count","editor-name-mismatch"],"editor_count":1}],"enumeration_errors":0,"window_count":1}
```

以上为终态逐窗口诊断原文。发现一个通过进程门槛的窗口、一个满足可见/可用/焦点及位置条件的编辑框，但零个通过 Name 判据，直接证实此终态存在 editor-name-mismatch。editor-count 类别按通过 Name 筛选后的数量计，editor_count 字段为筛选前候选数。未出现 process-path-mismatch、handle-zero 或 UIA 枚举异常；稳定计数 30，不支持仅因 15 秒不足或稳定次数不足的解释。

终态 header_count=0、draft_match_count=0，未取得窗口身份/预填匹配证据。终态快照不能证明整个等待过程未曾匹配，也不能单凭这些计数断言深链未预填；窗口切换、UIA 文本读取与 Name 规则适配仍需下一轮独立验证。不扩大本轮安全判据。此次未执行粘贴或发送，原始自动粘贴问题仍未证明修复。

## 验证记录

1. 新回归初次 1 failure、3 errors；实现后 4/4。subprocess 桩核验 deadline、超时预算、diagnostics 与旧 receipt 契约，静态断言诊断采集和终止分支不派发输入。
2. `run_selftests.py -k codex_paste`：4/4。
3. `smoke_test.py --affected idea_chat`：9/9。
4. 默认 `smoke_test.py`：8/8。
5. PowerShell AST：0 解析错误；安全块逐字对照通过。
6. `run_selftests.py --layer architecture --all`：仅 test_round_baselines 的 R1081 完整安全全量欠账失败。
7. 收尾误启动漏写 --safe 的全量命令，已确认并终止本轮进程树，不计验收；改用 `run_selftests.py --all --safe` 后被脏树前置拒绝。未暂存、删除或改写用户预设及既有未跟踪文件。

自审：请求范围与安全边界通过；全量必要门禁未通过，不能标记 TASK_COMPLETE。继续正式验收需用户授权隔离处理既有工作区/全量阻塞；进一步适配 Name 判据需单独授权与实机身份验证，不直接放宽规则。

临时探针 JSON 已删除（本轮生成、含任务首行）；测试自动刷新的分层基线已恢复，未提交私有正文。诊断性检查点：`efaf1bc`。暂存清单仅本轮 7 个文件，diff --check 通过，凭据形态扫描零命中；未推送。
