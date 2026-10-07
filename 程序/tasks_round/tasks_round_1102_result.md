# R1102 简报编辑框交互细化

- 类型：修复轮；仅 desktop.py 的上传成功回调、可见标签和提交反馈有生产改动。
- 实跑：专项 22/22、相关/UI 回归 365/365（200.1 秒）、最终架构 308/308（36.171 秒）、受影响冒烟 9/9（门禁约 67 秒）、默认冒烟 8/8，三个基线通过。
- 欠账：修复上传识别结果不可见及追问合并无反馈；未处理无关历史队列。最近完整安全回归仍为 R1101，本轮不冒用其凭据。

## 实现与边界

上方标签改为“创作简报 · 可直接编辑”，下方输入提示保留。上方原本没有 Return 发送绑定，保持 Tk 原生换行；下方 Return 继续发送，未新增 Ctrl+Enter 或修改任何绑定。

发送成功路径在非空追问时追加状态“已一并提交追问”，保留既有 Agent/API 状态。缺必填和启动失败的提前返回不发成功反馈。

上传成功且控制器 replace_attachments 后，使用同一 stage_idea_attachment_reference 解析本轮引用，复用 extract_brief_creation 识别多行、普通字段别名和篇幅；锁别名来自 workflow_settings 定义。逐字段与模板按归一化空白比较，仅填空值或仍为示例的值。替换字段正文时保留其他内容，重新渲染视觉必填标记；未落盘，不清空下方追问。无本地可读转换稿或上传失败不改编辑框。

R1100 attachment_fields 门禁代码不动；idea_chat.py、script_contract.py、stage_execution_service.py、skill_panel.py、默认创意示例.md 均未改。不读取真实创作项目、不调用真实模型、不修改用户预设。附件内容仅因本轮明确授权而显示为可编辑简报，发送仍沿用上方加下方的合并契约。

## 测试证据

使用随附 Python -B，隔离工作树执行：

- 失败先行：idea_inline_brief 19 条中 3 条失败，分别定位旧标签、缺追问反馈、缺可见回填；Enter 分工测试通过。
- 修复及补边界后：idea_inline_brief 22/22。新增 5 个用例覆盖真实 Tk Enter 分工、上传队列成功回调、手填/多行/未知字段保护、不可读及失败不变、清空后回填。既有用例只追加断言，无删除、无弱化。
- 独立架构：308/308，基线数量不变。执行器自动同步架构时间及历史全量凭据镜像；TODO 快照仅同步移动后的注释行号。
- 首次较大回归和受影响冒烟发现 test_idea_chat_attachment_refresh 的 SimpleNamespace 测试桩缺新增回填方法。仅给桩增加该方法及调用断言，所有原断言保留；状态文案同时说明上方简报与下方发送框。再次 `run_selftests.py -k idea brief workflow ui_edges` 为 365/365、200.1 秒，旧测试失败已关闭。
- 最终 `smoke_test.py --affected idea_chat workflow` 9/9；`smoke_test.py` 8/8；`run_selftests.py --layer architecture --all` 308/308。未把首次失败记作通过。

本轮未改变启动入口、Tk 控件生命周期或事件绑定，距 R1101 全量 1 轮，按 AGENTS.md §5 不触发完整安全全量。未重启真实应用、未人工视觉验收；界面行为由临时项目 Tk 测试验证。

## 收尾检查

中央领取 R1102，无匹配队列 ID；validate 为 0 errors、1 条既有历史租约警告，不修改该租约。新增源码及测试常见凭据形态零命中，git diff --check 通过。采用 minimal-diff-fix 控制范围，ui-ux-pro-max 复用现有标签及反馈组件，scoped-tests 选择相关回归，tech-writer 记录实跑与未运行边界。

提交：验收通过，随本报告执行收尾提交，随后回填实现提交号；状态页下一号 1103。主目录用户预设 SHA256 保持 E596C86C8D362FD6C6797FE9F9E19B4A7507D4F6ACE19BB91CE955EFF47E4651，未跟踪资料不动。

[TASK_COMPLETE] 三项交互细化及适用自动验收完成；真实应用未重启，需重启加载。本轮没有删除测试或弱化既有断言。
