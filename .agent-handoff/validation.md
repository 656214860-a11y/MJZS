# 验证证据

## 2026-10-12 O13 完成

- 2026-10-12 O13：新增 `tests/test_writing_response_preservation.py::PreparationReplyStateTests` 3 条（状态判据区分四态／无状态消息为空串；确认成功后为「阶段稿待确认」且消息含路径与确认；取消后迟到错误含「原始响应已保存」「不等于正式采用」与归档路径且台账未变）；扩展既有 2 条（格式不合格与截断带 `原始响应已保存`＋原因标签且消息点明归档不等于正式采用；版本变化经 `reply_to_writing` 带 `因版本变化未采用`）。定向 `-k writing` 139/139、关联 `-k idea_inline_brief writing_response_preservation` 46/46、桌面 `-k ui_edges` 115/115、架构相关 22/22、默认冒烟 8/8，全 0 红。`desktop.py` 增 1 行 → TODO 注释快照 desktop.py 行号 2748→2749。本轮 1336 − 1330 = 6 ≥ 5，收口补一次干净 master 全量。

## 2026-10-12 O12 完成

- 2026-10-12 O12：新增 `tests/test_tts.py::TtsBatchIdentityTests` 6 条（清单记身份／中途改设置不混用／换模型与换端点失效旧缓存／截断与空文件不续用／旧清单无摘要时文件非空即沿用／密钥不入指纹清单批次记录）；定向 `-k tts` 49/49、`-k tts audio animatic subtitle` 全绿、关联 `-k ui_edges` 115/115、架构相关 `-k unification_ratchet json_io_boundary layers tts_publication_boundary todo_comment_snapshot` 12/12、默认冒烟 8/8，全 0 红。夹具 `fake_synthesize` 跟随新签名补 `**_kwargs`（`tests/test_ui_edges.py` 两处，只改夹具）。本轮 1334−1330=4<5，不跑全量。

## 2026-10-12 O11 完成

- 2026-10-12 O11：新增 `tests/test_confirm_gates.py::ConfirmationBindingTests` 5 条（换候选只失效那一个角色且门禁重问／改冲突优先级重问／跨集同批次 ID 内容不同即复核／无关字段不扰动／旧记录无摘要仍算已确认）；定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 101/101、接缝 `-k ui_edges stage_execution stage_parallel` 172/172、架构相关 `-k unification_ratchet confirm_gates_json_boundary todo_comment_snapshot layers no_circular_import stage_paths` 15/15、默认冒烟 8/8，全 0 红。台账无变化（`stage_execution_service.py` json.loads 仍 108/1039/1070/1086）。本轮 1333−1330=3<5，不跑全量。

## 2026-10-12 O10 完成

- 2026-10-12 O10：新增 `tests/test_confirm_gates.py::AdoptTransactionTests` 6 条（落盘失败留 failed 且门禁不通过／应用前中断留 pending／成功记 applied 不再问／重复点击幂等／旧记录无 state 按 applied／未知 key 空相位），改 `tests/test_asset_detail.py` 两条（第二步失败事件 `['record','apply','record']` 且不刷新不报成功；第一步失败不落盘）；定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 96/96、架构棘轮 `-k unification_ratchet confirm_gates_json_boundary` 5/5、默认冒烟 8/8，全 0 红。台账 `架构统一基数.json` 第四项三处行号随 adopt 加长平移（1025/1056/1072→1039/1070/1086，exempt 不变），`TODO注释快照_20261003.json` 的 asset_detail.py 注释行号 346→350。
- 2026-10-12 O10 收口全量（干净 master 工作树 `--all --safe`）：第 1 次 4528 条／445.5 秒／1 文件红（`architecture.test_todo_comment_snapshot` 行号平移，定向 2/2 修绿）→ 第 2 次 4528 条／449.2 秒／0 红，绿凭据 round=1330、tree=3281c7c7，`last_full_safe_all_round`=1330。文档收尾在绿凭据之后，非同树全量。

## 2026-10-12 O09 完成

- 2026-10-12 O09：新增 `tests/test_previs.py::PrevisEvidenceTests` 2 条（改调度失效／改回复用／换文件失效且不删成果／旧记录无来源时退回旧口径）；定向 `-k previs white_model` 138/138、关联 `-k stage_execution_service stage_parallel` 57/57 与 `-k ui_edges` 115/115、默认冒烟 8/8，全 0 红。架构（干净 master 工作树 `--layer architecture --all`）312/312、0 红。台账 `架构统一基数.json` 第四项三处行号随插入平移（exempt 不变）。

## 2026-10-12 O08 完成

- 2026-10-12 O08：新增 `tests/test_previs.py::RoutingGateConsistencyTests` 4 条（自动→复杂、复杂→简单、跨集同镜头 ID、删除覆盖）；定向 `previs stage_parallel` 143/143、0 红；接缝 `previs stage_parallel stage_execution local_previs stage_completion white_model stage_models manual_gate row_targets ui_edges desktop` 398/398、119.2 秒、0 红；架构 `smoke_test.py --architecture` 312/312 OK；默认冒烟 8/8。回归修复仅颜色：`test_previs_monitor.py`、`test_ui_edges.py` 的 `ready` 打桩补 `source=None`。本轮号 1316 − 上次绿全量 1312 = 4 < 5，未跑全量。

## 2026-10-12 O07 完成

- 收口全量：干净 master 工作树（`HEAD=b0c6716`、`HEAD:程序`=12ad4759）`run_selftests.py --all --safe`——第 1 次 4500 条／528.7 秒／21 文件红（缺嵌套子模块致写作与技能组假红；补子模块后同树定向 489/489、0 红），第 2 次 4516 条／388.1 秒／0 红，凭据 round=1312、tree=12ad4759。

- 定向：新增 `tests/test_white_model_identity.py` 12 条＋ `white_model_identity previs` 相关 136/136、5.0 秒、0 红。
- 接缝：`white_model previs project stage_execution local_previs desktop stage_parallel stage_completion storyboard keyframe asset` 669/669、48.9 秒、0 红（`test_desktop_startup_perf` 本轮通过）。
- 门禁：默认冒烟 8/8；`smoke_test.py --architecture` 312/312（首次 311/312，因本轮在 `stage_execution_service.py` 插入 7 行使 `架构统一基数.json` 第四项三处豁免行号漂移，同步行号后全绿）。
- 全量：见 [R1312](../程序/tasks_round/tasks_round_1312_result.md) 文末；按用户 2026-10-12 指令只在收口跑一次，先查 7 天内同内容树绿凭据（无），本轮未命中 AGENTS §5 升级条件。

## 2026-10-12 O06 完成

定向 591/591（含接缝）、修复后相关 128/128、默认冒烟 8/8。第 1 次全量（树 e0df829a）4 文件红，均为夹具/环境；第 2 次全量（树 0e2a2f06）4504/4504、536.7 秒通过，但检出为 detached 工作树，执行器未写绿凭据；第 3 次全量为取凭据在 master 临时工作树重跑，行至性能用例被并发活动中断退出 1，未取得凭据，不再重跑。O05 历史全量不覆盖本轮树。详见 [R1307](../程序/tasks_round/tasks_round_1307_result.md)。

## R1265

- 最终受影响 14 文件 458/458、156.7 秒；冒烟 9/9，日志 程序/outputs/r1265-affected-final.log。
- 本轮架构 307/311；四处失败修复后相关 3 文件 10/10，日志 程序/outputs/r1265-architecture-fix.log。未改门禁断言。
- R1264 历史真实全量 tree=9ea232b7027c6e77b4ef9516c146a8e9c5ae2b95、413.396 秒；不覆盖本次树。中央 validate 0 errors/0 warnings，未实发 API 或重启。见 [报告](../程序/tasks_round/tasks_round_1265_result.md)。

## R1208

- 正式 master fe4a923 安全全量 4291/4291、397.379 秒、含架构 311/311，执行器凭据 round=1208、tree=3831b1e0fe2e20cf1ea6c7b0b8afb9c881c3bff9；日志 TEMP/r1208-full-final.log。
- 首次全量 2 条旧取消 fixture 失败，补齐前置后定向 73/73，再完整复验通过。默认冒烟 8/8、受影响冒烟 9/9。全量后的缓存隔离补丁先红后绿、定向 68/68，日志 TEMP/r1208-cache-green.log；最终树未同树全量。见 [R1208](../程序/tasks_round/tasks_round_1208_result.md)。

## R1200

- 定向 129/129、默认冒烟 8/8、受影响冒烟 9/9。首次全量仅架构登记行号漂移，修正后定向 71/71。
- 干净 e1f2d26 安全全量 4283/4283、539.0 秒、exit=0（含架构 311/311）。后续仅文档收尾；不声称最终文档树或用户主目录同树全量。
- 后续干净 master 808a972 正式全量 4283/4283、511.725 秒，R1202 凭据已写入；未实发 API、未重启。原始日志 TEMP/R1200-full-recheck.log、TEMP/R1202-master-full.log；见 [报告](../程序/tasks_round/tasks_round_1200_result.md)。

## R1162

- 定向 137/137、受影响冒烟 9/9（含默认 8/8）、相关边界 5/5；主目录两项回归 2/2。先红后绿与命令目录错误记录见 [报告](../程序/tasks_round/tasks_round_1162_result.md)。
- 实现 db0e878，主目录同步回执 6523465；既有 6 项已跟踪改动保持原样。未重启应用、未真实桌面粘贴或模型发送。本次交接补记仅文档与只读代码核验，不重复运行测试，以上均为 R1162 已有凭据。

## R1139

- 技能/Codex 定向 197 条通过，默认冒烟 8/8；补充定向 27 条和 ratchet/coverage 7 条通过。
- 干净 master 191ef05 全量安全回归 exit=1，旧 UI 按钮样式及剧本输出契约断言失败；没有本轮绿色全量凭据。详情与未运行项见 [报告](../程序/tasks_round/tasks_round_1139_result.md)。
- 实际 67 技能安装，重复 67 unchanged；只读 Codex skills/list 确认 pipeline-script-preparation enabled，不冒称已验证模型加载执行。

## R1074

- 旧实现内存对照 17/17，迁移后定向 58/58，默认冒烟 8/8，受影响 9/9；原断言未改，新增 11 条。
- 干净 master 813b662 正式安全全量 4026/4026，含架构 309/309，exit=0。tree=c924740a7a042954a6e4e086736a15fe5c31437c、round=1074、seconds=295.657、at=2026-10-06T00:23:14；执行器真实凭据，不手改。
- 初次 runner 无写锁权限中止；获授权后通过。旧实现对照首次 cwd 导入错误，修正绝对导入路径后通过；详见本轮报告。全量后仅文档回填，不冒称最终文档树受测。
- 收尾文档／轮次门禁 15/15、0.8 秒；中央任务 completed，validate 0 errors、1 条既有租约警告。

## R1073

- 迁移前 test_pet_ui 574/574（含新增 G3 7 条）；迁移后定向 588/588，默认 smoke 8/8。冻结 100 个 ID 的摘要与 R1059 一致，前后方法 AST 不变。
- 干净 master d6bfe1e 正式全量 4015/4015，含架构 309/309，exit=0。新增 G3 7 条及内存协调 10 条，未删原测试。
- 执行器凭据：tree=68211bcc962eff5e40fe0722c0735a920044e7ec，round=1073，seconds=359.982，at=2026-10-05T17:51:24。临时日志 R1073-full.log。
- 后续仅文档回填，最终文档树未重跑全量；不声称实机视觉体验已验收。
- a517dd1 后文档／轮次 15/15；中央 R1073-CHAT-COORDINATION completed，validate 0 errors、1 条既有租约警告。

## R1072

- 定向 70/70；默认 smoke 8/8；失败集合修复后 200/200。首轮 5 文件／6 失败均已关闭，位置快照仅同步行号，不增加豁免。
- 正式安全全量：干净 master 6cf0911e6f7b9f86e27433f72031201a734fe6e5，3998/3998，含架构 309/309，exit=0。
- 执行器真实凭据：tree=ba1498584b9be6c5e89736ebc21fef649ae8a594，round=1072，seconds=357.954，at=2026-10-05T17:35:42。后续仅文档收尾，不冒称最终文档树已全量。
- 日志：系统临时目录 R1072-master-full.log；长期事实摘要见 R1072 结果文件。

## R1070

- 周期安全全量：干净 master bc6358e719fea403a0e74a09f06786a0a7ab7bf7 执行 run_selftests.py --all --safe，exit=0，ALL TESTS PASSED，313.560 秒。
- 执行器真实凭据：tree=69a5dd97bc85aebed4f89780683ae3ecce1ee34c，round=1069，at=2026-10-05T08:44:11。round 取执行时最新报告，不手工改为 1070。
- 输出仅保留尾部，未保留本次总用例计数，不沿用历史 3994 冒充本次计数。全量后仅文档收尾，不声称最终文档树同树全量通过。
- 中央 validate：0 errors、1 既有租约 warning，详见 risks。文档链接与 diff --check 通过，凭据形态扫描 0 命中；默认 smoke_test.py：8/8、0 失败。未独立重跑架构门禁。

## R1069

静态检查：11 份入口/接力文档链接有效、标记唯一、无模板占位符；diff --check 通过。
在 程序/ 执行 ../运行环境/Python/python.exe -B -m unittest tests.architecture.test_agents_md tests.test_round_claim：23/23，10.982 秒。
同一解释器执行 -B smoke_test.py：8/8，0 失败；默认模式未启动独立架构门禁。
仅文档改动；全量凭据轮次 1067 至本轮 1069 差 2，按既有周期不重复全量。
最终结果见 [R1069](../程序/tasks_round/tasks_round_1069_result.md)。

## 历史基线（不是当前树验收）

- R1068 主树全量：干净提交 1b36059d5e7c8036b50cbf8118d41b3d0aa2ed84，3994 条通过。
- 凭据 tree=8466f0109fe30c54a31d1ea8890e5b05843553d6，round=1067，at=2026-10-05T08:20:53。
- R1068 收尾：冒烟 8/8，test_agents_md + test_round_claim 23/23。
- R1068 隔离副本：批量删除定向 90/90、冒烟 8/8、架构 309/309；不是生产删除或逐候选独立证明。
