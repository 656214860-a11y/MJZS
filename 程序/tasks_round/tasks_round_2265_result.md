# R2265 结果：白模预演选 API 模型时拒绝并提示（功能轮，REQ-S09-50／DES-S09-50）

1. 轮次类型：§3.1 功能轮。用户裁决白模预演不做 API 直连、保留本地 Agent（原直连方案已丢弃，未提交）。
2. 改动：`previs_automation.require_local_agent()` 唯一判定与文案（engine=='qwen' 抛 ValueError，提示“白模预演需要本地 Agent（Claude 或 Codex 桌面通道），请在该阶段设置里切换引擎”）；调用点两处——`desktop_idea_chat._FlowAgentLaunch.build()` 对 `stage=='previs'`（手动入口经 white_model 的 guarded 弹既有错误提示）与 `previs_automation.start`（busy 之后、建批次之前，走既有启动失败异常）。codex／claude 等引擎行为不变；未删 Qwen 模块。
3. 文档：`docs/stages/S09_白模预演.md` 新增 REQ-S09-50、DES-S09-50 与测试锚定行。
4. 测试：新增 `tests/test_previs_local_agent_only.py`（先红：手动入口未拦、`require_local_agent` 不存在；后绿 4/4）。断言未动。
5. 验证：`run_selftests.py -k previs white_model` rc=0；`smoke_test.py` 通过；`smoke_test.py --architecture` 通过 8 项，另有 2 个失败（`test_agents_md` 缺 `维护记录/基准历史.json`、`test_skill_reference_injection` 缺 `skills/00全流程SKILL` 包）——均为本 worktree 缺未跟踪文件所致，与本轮无关；`-k idea_chat` 同样因缺 `00全流程SKILL` 包失败（SKILL 引用缺失），未能作为本轮凭据。未跑全量。
6. 未验证：真实界面弹窗显示（只验证异常文案与未启动进程）。无新增模块，分层表与模块计数不变。
7. 是否已提交：见提交（分支 codex/wip-R2265）；project_status.md 未改。
