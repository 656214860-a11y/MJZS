# 接力决策

R1590/R1591：用户明确将8项真实验收延期至实际使用阶段，保留验收标准，不阻塞后续开发，不自动催验或付费实测；见程序/说明/实际使用阶段待验收清单.md。

## R1069：多文件布局，保留唯一权威

采用 agent-handoff 技能的 multi 布局，分离状态、证据、待办和历史，避免入口膨胀。
程序/AGENTS.md §0 保持唯一启动阅读协议；根 AGENTS 只路由，程序规则增加接力索引指针。
待办只链接既有优化队列，不复制状态、不分配轮次、不替代中央认领。
只建立项目内 Markdown，不安装 hooks、不修改用户级配置或 Claude 权限。
依据：本轮用户初始化请求与既有项目规则。

## R1676：`.claude` 配置入库边界

用户要求跟踪 `.claude/`。实际执行：`settings.local.json` 用 `git add -f` 纳入版本（覆盖全局 gitignore）；`scheduled_tasks.lock` 保持不跟踪（仓库 `.git/info/exclude` 的 claude-code-runtime 规则，运行期 PID／会话锁）。换机后需复核 settings.local.json 的本机绝对路径。依据：用户 2026-10-18 指示与仓库既有排除规则。

## R1678：需求锚定门禁

`tests/architecture/test_requirement_traceability.py` 要求 ✅ 需求有测试锚点；基线 `维护记录/需求锚定基线.json` 记录现状欠账 152/298，只许减少。新增或修改 ✅ 需求须同轮补锚点。依据：R1678 结果文件与 AGENTS §2.7。
