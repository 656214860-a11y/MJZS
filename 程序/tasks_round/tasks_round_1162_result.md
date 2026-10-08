# R1162：Claude Desktop 与 Codex 统一全文投递

## §7 三问

1. 类型：§3.2 修复轮；用户明确批准将 Claude Desktop 的投递方式与 Codex 对齐。
2. 验证：两项失败复现先红后绿；定向 137/137，受影响冒烟 9/9（含默认 8/8），相关架构边界 5/5。未运行完整架构或安全全量；历史正式全量 R1160，不冒充本轮通过。
3. 欠账：本轮投递差异已修复；不改变历史待办。R1162 − R1160 = 2，未触发五轮全量周期，也未修改启动路径、Tk 生命周期、删除语义或层级表。

## 修改与边界

- `desktop.py`：取消读取任务文件全文时对 Claude Desktop 的排除，让两端共用原有全文读取／文件不可读时路径指令回退分支；状态文字改为“本次任务”，不再声称只粘贴路径。
- SKILL 路径引用、任务文件归档、首发/续发拼装、API/CLI、45 秒就绪等待均不变。
- 粘贴后仍由用户手动发送；未修改自动粘贴脚本或其草稿保护，不增加自动发送、重试或 Enter 兜底。
- 普通创作测试验证剪贴板与任务文件全文完全相等，包含用户要求、writing 契约和技能路径，不包含 SKILL 正文。
- Claude 读取后续 SKILL/附件仍可能需要本地文件访问授权；本轮只解除读取任务书正文的额外依赖。

## 测试契约迁移

- `test_native_claude_pastes_task_reference_without_cli_or_auto_send` 改名为 `test_native_claude_pastes_full_task_without_cli_or_auto_send`；“不含正文、包含路径和无法读取提示”的旧路径投递断言按用户要求改为正文及文件全文严格相等。文件归档、指定程序、45 秒、禁止 CLI/Codex 误路由和 prepared 回执断言保留。
- 新增 `test_native_claude_writing_pastes_contract_and_skill_reference_not_skill_body`，覆盖真实普通创作拼装（外部发送打桩）。未删除测试或降低安全断言。

## 本轮实跑

全部使用随附 Python，`-B`，在同 HEAD 的干净工作树验证；测试只使用临时虚拟项目，不读真实项目，不实发模型。

1. `-m unittest` 上述两项：修改前 2 项失败，均因为只收到任务路径；修改后 2/2，0.288 秒。
2. `run_selftests.py -k workflow codex_paste dispatch`：137 条、0 红，1.4 秒。
3. `smoke_test.py --affected workflow codex_paste`：9 项、0 失败，包含默认 8 项及定向门禁。
4. `-m unittest tests.architecture.test_platform_opening tests.architecture.test_platform_process_boundary tests.architecture.test_copy_entry_boundary`：5/5，3.530 秒。
5. `git diff --check`：通过；凭据扫描及最终暂存核对在提交前执行，结果见收尾回执。

未运行：完整架构、安全全量、真实 Claude/Codex 窗口粘贴、登录或模型回复；未重启应用。历史凭据仅作周期判断。

## 自审与提交

自审通过：仅两行生产代码与直接相关测试；共用全文分支避免两端再分叉，无新增依赖，不改变安全发送语义。主目录既有改动不纳入本轮。

中央领取 R1162；队列仅有历史 B-facade-callers 和 architecture-unfreeze-1-2，无本轮匹配 ID，不冒领。

提交：待本轮实现提交后回填真实 hash；未 push。
