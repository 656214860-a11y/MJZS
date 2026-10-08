# R1141：HOLLMWOOD 桌面 Agent 配置接线修复

## §7 三问

1. 类型：§3 修复轮。中央入口领取 1141；队列没有匹配项，未认领无关任务。
2. 测试：本轮默认冒烟 8/8、受影响冒烟 9/9、架构 310/310 通过；定向 146 条及 API 27 条通过。未运行全量安全回归；距历史 R1140 全量一轮，未涉及启动、Tk 生命周期、删除或层级登记表，不满足本轮升级条件。历史凭据不代表本轮全量通过。
3. 欠账：闭环 HOLLMWOOD 开关/自定义规则未到达桌面 Agent 及续发缺规则的问题；不清除其他历史待办。主树状态头随收尾更新为 1142。

## 原因与修改

- Codex 窗口收到的是完整任务文件的读取指令，并非完整正文。旧首发正文虽有四角色规则，却没有 HOLLMWOOD 名称；续发正文没有四角色规则，且桌面配置快照没有收集该开关和项目规则。
- workflow_settings.current 从既有 stage_config 权威入口收集 writing 四角色配置；统一生成开关摘要和规则，首次、续发经 workflow_engines 注入。关闭时明确不沿用历史规则，项目覆盖规则优先。
- workflow_tasks 仅对 Agent 路由移除固定注入，非 Agent/API 原任务正文保留；没有改动 API 四角色执行器。
- codex_tasks 支持可选可见摘要，desktop 投递时展示当前 HOLLMWOOD 状态；配置快照参与现有 setup_key，配置变化不误用旧设置。简报提取专用投递不追加该摘要。
- 新增 tests/test_hollmwood_agent_delivery.py，覆盖新任务、复用任务、启用、关闭、角色覆盖、其他阶段隔离及 API 兼容。既有测试和断言未删除、未弱化。

## 本轮实跑证据

使用随附 Python，工作区为干净 master 8845253 派生的 codex/hollmwood-wiring；主目录原有 7 个跟踪路径修改未纳入本轮。

| 命令 | 结果 |
| --- | --- |
| 新增专项（修复前） | 7 条中 4 失败、1 错误，复现配置未注入 |
| run_selftests.py -k hollmwood workflow codex | 146 条，0 红，1.9 秒；包含最终 8 条新增专项 |
| smoke_test.py --affected idea_chat workflow | 9/9，定向子门禁 0 红 |
| run_selftests.py -k writing_api | 27 条，0 红，1.0 秒 |
| run_selftests.py --layer architecture --all（首次） | 310 条，1 红：隔离工作树缺少未跟踪的 screenplay-gate-engine.md 外部参考文档 |
| run_selftests.py --layer architecture --all（补齐同一参考文档后） | 310/310，30.0 秒；未修改测试或架构基线规则 |
| smoke_test.py | 8/8 |

未运行：真实 Codex 窗口端到端创作、付费模型调用、全量安全回归。不将任务文本正确生成等同于模型已实际执行全部角色。旧用户任务书没有重写，新发送才生成修复后的任务。

## 自审与收尾

自审通过：改动限配置接线、任务注入、可见摘要及专项测试；复用现有设置权威和投递路径，无新进程/网络入口，不修改用户项目数据。外部参考文档仅补齐隔离验证环境，不纳入提交。用户需要重启应用加载修复。

提交状态：实现与本报告待收尾提交，提交后在主树收尾登记实际哈希。回滚使用对应提交的 git revert，不覆盖用户修改。
