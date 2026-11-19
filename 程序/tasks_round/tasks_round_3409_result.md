# R3409 — A3 L0–L2 消费者与接线审计
<!-- round-evidence: {"commit_base": "ccfcae57", "credential_hits": 0, "evidence_sha256": "d210d08648d68950", "exit": 0, "failed": 0, "passed": 0, "round": 3409, "tests": "docs-only"} -->

## 三问
类型：§3.5 只读诊断。仅新增本报告和标准证据，不修改源码、规则、其他车道或用户数据。
测试：本树两批定向验证通过，详见 M；默认冒烟、完整架构、全量未运行，不宣称三个基线全绿。
欠账：未修复生产缺陷；明确失败窗口和迁移验收。A3 诊断交付不代表整体任务书完成或已合入 master。

## A. 基线与范围
2026-11-18；工作树 1ae4，分支 codex/architecture-a3-audit，受审 HEAD ccfcae57df1466d9a6219a5ac5fdbfd73ec26f88，继承 R3402/A0、R3405/A1、R3406/A2。最初 detached，经根任务明确授权后绑定既定分支。中央入口领取 R3409；scope 返回另 89 个活跃分支无重叠。无对应队列任务，不认领其他任务。
本地无随附运行时，借用 D:/漫剧制作助手/运行环境/Python/python.exe 执行当前树测试，没有复制主树资产。此前命令路径误用根目录已纠正为程序目录，没有因此修改文件。

## B. master 与所有权
再次读取 master 为 0e3fc763（R3408 合入 L0 K9），并非初始 3a97b184。生产变化含 contract/__init__.py，规则新增 L0P；本报告描述 A2 基线实现，不冒称覆盖新主干全部变更。A4 应先吸收 K9 再定归属。
master 左独有/车道右独有：l0-constitution 1/0，l1-enterprise 5/3，l2-maturity-taskbook 5/2，foundation-hardening 18/19，foundation-api-disk 47/17。均只读，不据“已合入”推断所有权释放。

## C. 契约与消费矩阵
下列路径相对程序，测试仅列关联文件；实际执行范围以 M 为准。

| 能力 | 契约→实现→注入→消费者→失败分支→测试 |
|---|---|
| ServiceResult | contract/service_contract.py:12 四字段与 Cancelled → domain/subtitle_export_service → stage_execution_service.py:170 注入 publish_stage_text → export_stage_srt 将结果交上层，成功才刷新清单 → ok=False 保留 reason，取消不能等同失败 → tests/test_service_contract.py、test_stage_execution_service.py |
| ProjectContext | contract/project_context.py:11 只读快照 → orchestrator/project_context_factory.py:9 装配路径/缓存 → stage_execution_service.py:85 等注入领域 → domain 服务消费 root/resolver → stage_publication.py:21 拒绝显式上下文越界 → test_project_context、architecture/test_project_context_boundary |
| 发布 | stage_publication.py:70 校验/事务/索引契约 → agent.core.save_text 与 agent.publication.transaction → L3 注入 L2 → stage_execution_service 与剧本 UI → 校验、必需索引异常回滚；可再生索引异常记 warning 后保留成果 → test_publication_transaction、test_stage_execution_service |
| schema | contract/artifact_schema.py:25 REGISTRY/五态 → desktop_send_ledger.py:44 分类并校验 → 正常写入 stamp → desktop_automation_service.py:180 队列恢复、infra/continuity_ledger.py:374 读取 → future 禁写、missing 容忍，诊断计数交 diagnostic_capture → test_artifact_schema_wiring |
| 错误/日志 | contract/error_codes → infra/http_client.py:15 lookup/code_data → request_json 返回 ServiceResult → 上层按 ok/reason 消费；diagnostic_capture 装配启动检查 → desktop_launcher.py:30 消费 FATAL/DEGRADED，desktop.py:347 播报警告 → test_http_client、test_startup_selfcheck |
| 重试/取消 | orchestrator/stage_parallel.py:47 CONFIG 与 contract/platform_tools.py:40 cancel/checkpoint → stage_parallel.py:393 execution_scope → BackgroundTaskLifecycle 装配 control → desktop.py:217/UI 后台任务 → ExecutionStopped 与迟到代次处理 → test_background_task；SkillOrchestrator.retry:831 仅重新运行 failed 项 |

## D. 代表链路
1. 启动：desktop_launcher.launch → diagnostic_capture.run_startup_selfcheck → contract.selfcheck 注入检查；FATAL 阻断，DEGRADED 交 window/desktop 状态播报。desktop_startup_service.py:14 注入 schedule_after/idle 与 stopping 判定，首帧后选择项目。自检假依赖验证通过；真实首窗与冷启动性能未测。
2. 保存剧本/应用内文档：ui/desktop_script_pages.py:339 → domain/idea_chat.py:364 auto_save_reply → L3 publish_idea_creative 注入；已有 preparation/script_raw/natural_script 路径避免重复保存；OSError/ValueError 返回“未自动存档”，成功后刷新列表、通知三虎。本地文档导入 :389 与 UI add_script_files 复用发布器，失败按文件汇总。实际桌面保存与编辑器手改并发未测。
3. 阶段开始：ui/desktop_pet_bridge.py:58 → stage_handler_registry.start:145 → 选中 SKILL 与各阶段分发；Animatic 需要用户确认返回失败提示，fallback 明确保留。不是所有开始入口都返回 ServiceResult，旧文本返回协议不可直接删。
4. 取消：Desktop 后台任务 → BackgroundTaskLifecycle → execution_scope(control) → 发布事务前后 execution_checkpoint。取消是本地协作停止，不证明远端请求终止；已发送付费请求不能自动推定可安全重试。真实阶段取消/切项目/关窗组合仍未验证。
5. 产物发布：stage_execution_service → stage_publication → agent.publication；必需 update_index 属事务，可再生文件索引另行尽力更新。完成还须 stage_completion_service 核验，写文件成功不自动等于阶段完成。
6. skill 导入：ui/skill_panel_import.py 的预检/确认 → ui/skill_import_service.py:248 perform_import → 暂存、回收旧版、换入、_verify 试冻结、record 台账；UI 捕获 ImportBlocked/OSError/ValueError。冻结后重新校验是落地位置改变后的必要检查，不应作为“重复校验”删除。
7. skill 删除：pet_skills_manage.py:323 → skill_lifecycle_service.uninstall_skill_entry:318 → skill_import_service.uninstall_skill:620 → recycle_paths → forget_ledger_targets；锁与内置层限制在生命周期服务，回收无记录抛 ImportBlocked。字典返回值未被 UI 使用，但当前失败靠异常，不能据此认定误报成功。

## E. 已确认风险（静态失败窗口，不冒称实测复现）
A3-01：skill_import_service.perform_import 在换入后，仅 _verify 抛 ImportBlocked 的分支恢复旧版；record 台账写失败以及其他 OSError 没有同等恢复路径，finally 仅回收暂存。与函数“任一步失败都回到导入前状态”的承诺不一致。可能导入 UI 报失败而新文件已生效。建议 A6 故障注入、A11/A12 统一事务；不在本轮修改。
A3-02：skill_import_service.uninstall_skill 先回收后 forget_ledger_targets；台账失败无补偿。pet_skills_manage 删除消费者只捕获 ImportBlocked，OSError 可能逃出 UI 回调。风险是删除已生效但台账未更新/用户反馈缺失，不是已证实误报成功。

## F. 返回值与吞错判别
stage_execution_service.py:268 collect_writing_quality 直接取 publish_reports(...).data；domain/writing_quality.py:127–153 当前发布失败抛异常、末尾只返回 success，现时不能定性吞失败。未来若服务改为 UserError/SystemError，此消费者会失去原因或触发 dict(None)；列为契约演进风险。
stage_publication.py:37/52/60 捕获宽异常但 warning 明确，属于缓存降级。正式产物与缓存需分开验收，不应强行把可重建索引失败变成正式成果失败。

## G. schema 与无消费者边界
schema 已有队列、发送台账、连续性台账读写消费者，不能称为“只写版本无人读取”。本轮未穷举 REGISTRY 每一种外部消费者，也未声称全量无孤儿。通用文本发布器不自动给所有内容写 JSON schema；应由产物 owner 决定，避免把纯文本改成 JSON。
ProjectContext.snapshot 仅冻结映射外层，嵌套值仍可变；不能把 frozen dataclass 误读为深不可变。context=None 的旧发布调用也不提供项目根隔离，A4 应明确迁移边界。

## H. 重试与错误分类
HTTP 的 retries 与阶段 CONFIG 是不同层次：infra/http_client.py:108 默认不重试 POST，需 allow_retry_post 显式允许；SkillOrchestrator.retry 是失败项再执行。存在多层策略并不证明同一请求已发生重试叠乘。本轮未测远端计费/网络故障下的真实请求次数，A6 需用假服务统计调用次数、总时限及取消后请求。
ServiceResult.ok=False 不能一概计为失败，Cancelled 与 recoverable 的语义须保留。L3 部分入口将 reason 转 ValueError，迁移时需保持类型/取消信息，而不是批量替换异常语法。

## I. 影响及优先级
优先处理 skill 文件与台账的一致性、取消后的提交边界；其次收口混合返回协议及可选 context。保留旧 UI/CLI 入口与回收能力，不依据静态无 import 删除动态消费者。本轮未调用外部模型、下载 ASR 或访问真实用户项目。

## J. 整改路线
A4：吸收主干 L0P/K9 与本报告链路，明确结果/异常适配、装配例外、写入权及取消责任。A6：对 A3-01/02 与取消/重试注入失败取得行为证据。A11/A12：按消费者小批次统一失败传播和事务；先覆盖现有行为再改入口。现有 L0/L1/L2/foundation 车道保留所有权，不另造发布器或重试器。

## K. 测试迁移计划
skill 导入注入 record OSError、换入后 OSError，断言旧版/新版/台账一致；删除注入 forget_ledger_targets 失败并验证 UI 不报成功且有可恢复状态。发布注入取消、索引失败与磁盘错误，断言正式成果和可再生缓存不同回滚语义。结果适配覆盖 Cancelled/UserError/SystemError，重试用假供应商验证 POST 不重复计费。schema 对缺版本与未来版本验证读取/拒写，不仅检查字符串。上述新增测试属后续修复，本轮未编写。

## L. 交付与局限
本报告覆盖 A3 两项验收的代表性静态证据链；不是全仓消费者穷举或真实端到端通过。源码保持不变；未更新任务书勾选/状态页，整体完成文件留待全部阶段完成。分支不写 project_status；N=M+1 由 master 合入轮同步，不能覆盖其他轮次。标准提交哈希由 Git 记录定位 R3409，不自引用未来哈希。后续 A4 使用独立 worktree 新分支接续。

## M. 当前验证
在本树程序目录，PYTHONUTF8=1，借用仓库随附 Python：
- run_selftests.py -k service_contract project_context artifact_schema_wiring stage_execution_service：47 用例，0 红，0 skip（含 project_context_boundary）。
- run_selftests.py -k startup_selfcheck publication_transaction skill_import_validation skill_lifecycle http_client background_task：ALL TESTS PASSED，0 skip，退出 0；保留精简终态，不编造未保留的总数。
- dev.py scope 程序/tasks_round/tasks_round_3409_result.md：无其他分支重叠。
默认 8 业务冒烟+1隐藏探针本轮未重跑；完整架构与全量本轮未运行。R3402/A0 的 532 条及失败集合、R3406 的资产缺口只作历史基线，不能换算为当前树绿色。全量欠账未由本轮消除，master 合入前应读真实 receipts 与执行器现时判定。