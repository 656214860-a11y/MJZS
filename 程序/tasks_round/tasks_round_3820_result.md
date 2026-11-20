# R3820 内建总控退役（实施中）
<!-- round-evidence: {"commit_base": "59a117ee", "credential_hits": 0, "evidence_sha256": "c8c204199d0fa42d", "exit": 0, "failed": 0, "passed": 204, "round": 3820, "tests": "run_selftests.py -k builtin_controller_retirement skill_command skill_tools agent_skill_sync skill_user_layer skill_project_layer skill_residue_service distribution_build distribution_selfcheck skill_budget_send_entries stage_prompt_governance l1_p2_semantics skill_reference_injection req_anchor_s03_s07 workflow_writing_stages skill_reference_closure storyboard_final_scope script_preparation_roles req_s05_anchors"} -->

1. 类型：功能轮，按最新版111行《总控机制删除任务书_R3811》完整工作包实施；REQ-RET-01/02、DES-RET-01/02。原任务书快照按项目闭环命名约定纳入 `总控机制删除_R3811任务书.md`，没有改变正文。
2. 测试：代码合同可集成；17文件201条定向绿，补充5文件31条绿，默认冒烟8项业务＋隐藏桌面探针9/9，完整架构581项580过、仅预存状态头不连续1红。消费者GUI回归因共享令牌等待导致标准affected入口900秒超时；统一候选全量未运行，不能称任务验收完成。
3. 欠账：已移除专用内建总控生产依赖与桥接工具，未新增长期代码失败；预存主干状态页元数据、受忽略测试前置、共享GUI/全量验收由主代理统一候选闭环，未伪造绿凭据。

## 范围与环境

- 基线：839ef93a；分支 codex/retire-builtin-prerequisite；真实领取 R3820（非任务书历史标签）。
- 专用工作树：D:/漫剧制作助手/.agents/worktrees/retire-builtin-prerequisite。初次建树过深造成长路径检出失败，仅在新树以命令级 core.longpaths 完成 restore；后将本树移动至短路径，未切换/改写主树或他人索引。
- 解释器固定 D:/漫剧制作助手/运行环境/Python/python.exe，PYTHONUTF8=1，所有命令带 -B。
- 删除前跟踪 00 目录文件 223 项，清单 R3820_deleted_skill_files.txt；生产／阶段／文案引用见 R3820_reference_inventory.txt。其他技能、模板、skills-lock 与用户数据不属于删除范围。
- 两个保护 gitlink 在新树默认未材化，导致真实技能数 71 对既有断言 73（未降断言）。仅用主树各 git 仓库的准确索引提交 git archive 材化到本树：剧本锻造 6c3d73994f456b696de536c86602b4022824a535；编剧技能集 357d1348ccaa1ab75f2f51ef7c90a7f00a686c76。不读取脏修改、不复制 .git，不改 gitlink 指针。

## 验证过程（实施中）

- run_selftests.py -k builtin_controller_retirement：退出 1，4 条先红；专用工具仍暴露、目录仍在、注册候选接口缺失、发送绑内建路径。
- 第一批受影响 144 条，退出 1；预算发送、候选分类、同步路径及中性 fixture 修订后，复验 39 条仅剩残留 fixture 排序断言，已精确同步索引。
- smoke_test.py --architecture：退出 1，581 条/304.289 秒，3 失败1错误。删除模块后两个覆盖率汇总未同步为本轮问题，修正仅移除模块的统计；另外基线缺被忽略的基准历史.json，基线状态头3784与最新结果3809不连续，属于测试环境前置。本树补同源基准历史，状态头仅本地验证同步，不提交 project_status.md。
- 未运行完成的检查不标绿。全量先与主代理协调，等待共享活跃 PID76628 的标准锁流程，禁止强删活锁。

## 检查点验证（2026-11-19 18:50）

- 自身已知失败清零：`run_selftests.py -k test_distribution_selfcheck test_distribution_build test_storyboard_final_scope builtin_controller_retirement skill_reference_injection test_req_anchor_s03_s07 skill_command agent_skill_sync skill_user_layer skill_project_layer skill_residue_service skill_budget_send_entries stage_prompt_governance l1_p2_semantics workflow_writing_stages skill_reference_closure test_copy_rules`，退出 0，17 文件／201 条／25.5 秒，skip 0。结果包含新增 6 条退役用例。
- `smoke_test.py` 退出 0：8 项业务基线＋隐藏桌面探针＝9/9（探针由入口自动执行，显式 `--probe` 参数不支持，首次参数错误退出 2 后按入口纠正）。
- `doc_registry.py` 退出 0：83 份登记文档。
- 架构失败项定向 168 条（含技能真实73断言），临时本地状态头诊断：仅 runbook 历史覆盖数字漏同步一项失败，已同步为672模块／91有覆盖／581零覆盖；状态头已恢复原文，最终提交不包含 project_status.md。该诊断不作为正式原树绿凭据。
- 标准 `smoke_test.py --affected skill_command skill_tools agent_skill_sync skill_residue_service workflow_settings script_contract desktop_shared_send desktop_shared_input distribution_build`，进程 job `pwsh-67b23135207f482f` 尚未完成：自动选115文件／233工作单元，非GUI已跑至writing_status_line，随后等待共享GUI令牌（活进程PID76628，队列第1）。非GUI两红（分发specs未声明、定稿fixture旧00句）均在上述201条中修复转绿；旧进程的旧结果仍按真实报告。
- 完整全量未启动：共享活锁PID76628属 `D:/L3-acceptance-temp-dsh-8d752502/run_l3_candidate_fu...`，主代理明确不并发、不等第二个20分钟窗口，最终候选统一复验。不伪造全量绿凭据。
- 基准历史.json仅复制主树同源测试前置（受忽略，不入提交）。源摘要收尾补记。
- `.git/config` 精确检查只有三个受保护gitlink的active/url键，没有AIGC遗留键，因此不改共享配置。
- 第三方实质方法已在阶段说明本地化重述；MIT版权与完整许可、来源URL／吸收版本／退役前快照保留在 `skills/THIRD_PARTY_NOTICES.md`，未把包数据迁到用户层。

## 提交

按主代理授权先形成完整检查点（GUI消费者回归与统一候选全量待完成），使用项目 dev.py commit 入口；不合入 master。回滚方式为本轮提交 git revert。检查点commit为 `59a117eea9cffc257f3d1f8951148f119197ed7b`（dev.py commit退出0）；主代理接收为b860721f。注意FAIL提交是允许的诊断检查点，commit_round只识别 `R数字:` 自动生成evidence，所以该检查点没有自动evidence/R3820.json，不将其冒称正式绿凭据。当前状态不标 TASK_COMPLETE。

## 最终交接回执

- 完整架构在59a117ee已提交内容树、原始状态头、补齐受忽略基准历史环境下复跑：`smoke_test.py --architecture`，退出1，581项／280.039秒；580过，唯一失败 `tests.architecture.test_round_baselines.RoundBaselineTests.test_round_number_continuous`，栈位test_round_baselines.py:52，`AssertionError: 3784 != 3821`。没有临时改头伪绿。日志 `R3820_architecture_final.txt`，SHA256 `c274a4b1ec9081aaba06179d3693d74134b21b4e5298550626f9846460e98a32`。
- 最终再跑前述201条精确命令，退出0，17文件／201条／28.4秒，skip0；原始输出 `R3820_directed_final.txt`。在此之后仅补角色／资产fixture与本地七维和12节拍职责的完整语义；补充验证 `run_selftests.py -k script_preparation_roles req_s05_anchors builtin_controller_retirement skill_reference_injection workflow_writing_stages`，退出0，5文件31条／1.9秒。
- 源码读取型fixture补扫发现 `test_script_preparation_roles` 与 `test_req_s05_anchors` 仍绑旧标题／锚点；只改为本地职责定位，角色／确认边界／资产准入断言均保留。
- 标准affected入口最终退出1，900秒超时；不是115文件已绿。其gui_hidden包装器PID50712在父入口超时后仍等共享GUI，核对完整本树命令后仅终止本树PID50712及子PID79220（taskkill退出0），未动共享持有者PID76628。
- 基准历史.json源为主树相同文件，SHA256 `5b0451c27a364b79dd430ca10889a407f2382ceec023aad6d7bd68f6b4946c24`，受忽略且不入提交。
- `scripts/skill_package_pins.py --check`退出0：外部技能包2个、问题0；三个gitlink指针差异为空。生产可执行路径对退役目录／模块／工具扫描零命中（git grep退出1，排除负向测试、结果和历史）。
- 本轮退役专用测试：删除test_aigc_lint（9条）与test_aigc_package_diff（9条），混合test_l1_p2_semantics只删除AigcLintTempTests的2条；新增退役用例6条。旧引用架构测试改为本地职责闭合与隔离边界，未跳过测试或放宽白名单。
- 未完成：共享GUI消费者回归及正式统一候选全量；主代理明确在其接收／元数据修复后的统一候选验证。当前仅交付“代码合同可集成，GUI全量待最终候选”。
