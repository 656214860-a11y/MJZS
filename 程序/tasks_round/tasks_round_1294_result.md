# R1294：Claude Code CLI 实际调度 HOLLMWOOD 四角色

类型：修复轮；中央已领取 1294，无对应队列项。用户最终明确选择 CLI 路径。API 已有执行器，本轮复用它，不将提示词扮演冒充程序调度。

## 改动与边界

启用 HOLLMWOOD 时，Claude CLI 进入助手托管对话，前三阶段继续逐项确认，自然剧本调用既有 hollmwood_roles.run：导演、编剧、导演审核、编辑、导演审核、演员、导演审核。正常流程 7 次独立 CLI 请求；审核拒绝遵循既有限次修订与停止规则。关闭开关保留交互式 CLI。

新增 ClaudeWritingAdapter 使用 -p JSON 输出、stdin 传入正文、隔离临时目录、关闭工具/项目设置/会话持久化及 hooks，保留用户登录配置；附件沿托管路径转 Markdown 正文，避免模型扫描项目。沿用进程注册、取消、输入预算、输出检查和落盘；恢复标识包含实际 CLI 模型及程序，避免换模型后复用旧结果。未改用户项目、预设、SKILL、阶段状态结构，未进行收费模型调用或重启。

范围：writing_api.py、workflow_engines.py、tests/test_writing_api.py、新增 tests/test_claude_writing_roles.py。两个生产模块均原 L3，不增加层级或架构豁免。

## 契约与自审

有意变更：开启四角色的 Claude CLI 可进入托管路径。原 test_desktop_agent_is_not_treated_as_an_api_model 仅显式设置开关关闭，原断言不变；新测试覆盖开启路径。其余既有断言未弱化、未删除、未跳过。

新增 9 条覆盖真实执行器角色顺序、审核拒绝阻断、前三阶段不触发角色、取消前后处理、CLI 隔离与请求参数、用量解析、错误正文保留及无效 JSON。自审通过：复用既有调度，不新增第二套角色状态；每次 CLI 调用有取消与超时边界，无静默切换 HTTP 或无限重试。真实 CLI 登录/网络/模型响应尚未实测；CLI JSON 完成后才显示该次正文，不宣称逐 token 流式输出。

## 实际验证

- 红灯：run_selftests.py -k claude_writing_roles，新测试最初 5 条失败，缺适配器与路由；初版测试导入 TestCase 带入 51 条原测试（通过），随后改为模块导入消除重复发现。该次另有 GUI 锁并发提示，失败依据仍为缺少实现。
- 定向：run_selftests.py -k claude_writing_roles writing_api：67 条，0 失败，2.8 秒。
- 关联：run_selftests.py -k claude_writing_roles workflow hollmwood idea_inline_brief idea_attachments script_agent_delivery_assembly：216 条，0 失败，24.0 秒。
- 默认 smoke_test.py：8/8。git diff --check 无空白错误。
- 未发现跳过记录。关联输出出现 Tk 延迟焦点回调 invalid command name / after script 警告，未导致失败，未宣称修复该既有现象。

三个基线：当前默认冒烟 8/8；本轮未运行完整架构门禁，无架构前后总数可报告，定向包含 writing_api JSON 边界检查；正式历史安全全量 R1293 为 4465/4465、514.981 秒，程序树 db2936ab12e3419fcc61e97bef846cd2a3c734f4，本轮距凭据 1 轮，未触发五轮全量门槛。历史凭据不是本轮内容树的全量验证。

提交：原领取 R1294 在并行任务推进后被提交钩子拒绝；经中央入口重新领取 R1297 收尾，未覆盖其他报告。实现已提交 8e8e576，并快进同步运行目录 master。运行目录同步后需重启助手加载；已有交互式 Claude 窗口不会自动转换为托管执行。
