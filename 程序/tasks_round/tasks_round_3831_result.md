# R3831 内建总控退役消费者与真实验收交接
<!-- round-evidence: {"commit_base": "59a117ee", "credential_hits": 0, "evidence_sha256": "20b42d213d59114e", "exit": 0, "failed": 0, "passed": 204, "round": 3831, "tests": "run_selftests.py -k builtin_controller_retirement skill_command skill_tools agent_skill_sync skill_user_layer skill_project_layer skill_residue_service distribution_build distribution_selfcheck skill_budget_send_entries stage_prompt_governance l1_p2_semantics skill_reference_injection req_anchor_s03_s07 workflow_writing_stages skill_reference_closure storyboard_final_scope script_preparation_roles req_s05_anchors"} -->

1. 类型：R3820功能轮的必要跟进修复／验证轮；仅补源码读取型消费者、剧本本地职责完整语义与真实验证证据，不做目录治理。
2. 测试：默认冒烟8项业务＋隐藏探针9/9；退役定向201条、补充31条通过；提交入口真实定向204条通过。完整架构581项580过，唯一状态页既有不连续；GUI消费者affected因共享活锁900秒超时，正式全量未跑，不冒称全部验收。
3. 欠账：代码合同可集成；原状态页与GUI／正式全量由主代理统一候选闭环，未关闭或隐藏欠账。

## 背景与改动

- R3820完整检查点 `59a117eea9cffc257f3d1f8951148f119197ed7b`，主代理接收为b860721f。再次用R3820提交时，跨树唯一轮次闸拒绝“R3820已被非祖先分支使用”（退出1），故本树按入口领R3831，不绕过门禁。
- `test_script_preparation_roles` 定位从退役00标题改为本地职责标题；三角色、五阶、情绪与不另设确认阶段断言保留。
- `test_req_s05_anchors` 从退役参考链接改为本地身份串／角色一致性／资产方法；来源、锚点、版本、冲突不覆盖等断言保留。
- 01本地方法补齐原职责的台词七维名称与12情绪节拍参考值；仍无总控目录依赖，来源MIT许可保留。
- 其他全部退役变更见R3820结果与任务完成记录。本轮不动治理路径、主树、他人索引、用户数据、gitlink或锁。

## 命令与真实回执

解释器均为 `D:/漫剧制作助手/运行环境/Python/python.exe -B`，`PYTHONUTF8=1`，工作目录程序。

- `run_selftests.py -k test_distribution_selfcheck test_distribution_build test_storyboard_final_scope builtin_controller_retirement skill_reference_injection test_req_anchor_s03_s07 skill_command agent_skill_sync skill_user_layer skill_project_layer skill_residue_service skill_budget_send_entries stage_prompt_governance l1_p2_semantics workflow_writing_stages skill_reference_closure test_copy_rules`：退出0，201条/17文件/28.4秒/skip0；日志 `R3820_directed_final.txt`，SHA256 d1d65afa5d18b05883184e3149d0ca9014f784527aee20503d1d54f004f528c7。
- `run_selftests.py -k script_preparation_roles req_s05_anchors builtin_controller_retirement skill_reference_injection workflow_writing_stages`：退出0，31条/5文件/1.9秒/skip0。
- 提交入口R3820重试前真实生成证据：`evidence/R3820.json`，基线59a117ee，定向204条0红、凭据扫描0命中；实际提交后被跨分支轮次唯一闸拒绝，不能将其说作R3820已正式收尾。
- `smoke_test.py --architecture`：退出1，581项/280.039秒，580过，唯一 `test_round_baselines.RoundBaselineTests.test_round_number_continuous`，test_round_baselines.py:52，AssertionError3784!=3821（当时最新结果R3820）。日志 `R3820_architecture_final.txt`，SHA256 c274a4b1ec9081aaba06179d3693d74134b21b4e5298550626f9846460e98a32。没有临时改头；基准历史受忽略同源文件仅测试前置，SHA256 5b0451c27a364b79dd430ca10889a407f2382ceec023aad6d7bd68f6b4946c24。
- `smoke_test.py`：退出0，业务8项＋隐藏探针9/9。`doc_registry.py`：退出0，83份。`skill_package_pins.py --check`：退出0，2包0问题。可执行路径退役依赖grep零命中（退出1），git diff --check退出0。
- 标准affected自动选115文件/233单位：退出1，900秒超时，主因等待共享GUI活持有者PID76628；不得宣称全绿。父入口超时后本树孤立gui_hidden PID50712及子PID79220经核对完整命令后终止（taskkill退出0），共享PID76628未动；所有本会话后台job回执已收集。

## 交接与未解决项

主代理明确接收“代码合同可集成，GUI全量待最终候选”。主代理在统一候选修状态页轮次后跑正式GUI/完整全量。本分支不合master、不push、不伪造全量绿凭据。回滚为git revert本轮与R3820提交，不触碰用户数据。提交hash以本轮dev.py回执为准。
