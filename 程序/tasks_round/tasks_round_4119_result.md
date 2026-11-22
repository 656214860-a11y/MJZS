# R4119 结果：结构页和分镜页选不到剧本——台账不再撤销自然剧本的采用；「结构剧本」目录里按集排版的结构稿也认；分镜页列出每份可用的结构剧本
<!-- round-evidence: {"commit_base": "02e2c3e0", "credential_hits": 0, "evidence_sha256": "219c8a4733ec9641", "exit": 0, "failed": 0, "passed": 119, "round": 4119, "tests": "run_selftests.py -k script_structure storyboard_catalog_snapshot preparation_confirmation writing_restart writing_unconfirm"} -->

## 开头三问

- （一）本轮属于哪种类型：缺陷修复轮。任务卡 W4-FIX-SCRIPT-SELECT（队列项 FIX-SCRIPT-SELECT），车道 codex/fix-script-adopt-select，从 89fdb829 切出，00:06 快进到 02e2c3e0。来源：用户 2026-11-22 23:41 报「剧本结构页面的生成的剧本无法选择采用, 下一阶段初步分镜无法选择」（来源 562cdbb1）。现象：结构页上方显示「自然剧本（待选择采用版本）」，「结构剧本」的列表是空的；初步分镜页的剧本列表也是空的。根因有三层（只读查了用户当前的项目，项目名和文件内容不记在这里）：① 当天 23:10 新生成了一份「项目设定」，台账写口顺带把自然剧本的采用记录清空（`orchestrator/writing_preparation_ledger.py` 的 `_revoke_natural_script_adoption`，写入「前置阶段已更新，请重新生成或明确采用自然剧本」），项目里有两份自然剧本，于是没有一份算采用；② 当天 15:23 由模型直接写进「结构剧本」目录的一份结构稿（文件名是「…_结构剧本_第01集_日期.md」，正文是「# 第1集：…」加「分场结构」）不被 `is_structured_script` 认，因为它只认正文首部有「# 结构化剧本」加「## 角色档案」或「## 分场剧本」的本地规则版式；③ 两份 10 月的结构稿认得出来，但它们记的来源原稿已经删了，按 REQ-S02-21 现有的规则不显示。另外分镜页的剧本列表只放「当前那一份」结构剧本。几层叠加，两个页面都是 0 份可选。本轮改 ①② 和分镜页只列一份的问题；③ 是写明的现有需求，没有动。复现：见「命令与结果」的反向验证，撤掉产品改动后 13 条用例红。
- （二）测试跑了吗、三个基线：新增 9 条用例（两个测试类）；因为需求变了，改了 7 条现有用例的断言（逐条列在「改了哪些断言」）；没有删除用例。反向验证：撤掉 4 个产品文件的改动，13 条红（7 条改过的加 6 条新加的；另外 3 条新加的当时改前改后都过，见「新增的用例」）。改后（基准 02e2c3e0）：和这次改动有关的 20 个关键词一起跑，36 个测试文件 490 条里 1 条红，是 `test_script_contract` 里一条比对技能名单的用例，撤掉产品改动对照跑它一样红（见「如实说明」第（十一）条）；第一遍红过的那条这一遍过了。引用「当前结构剧本」的其余 6 个测试文件另跑一遍，699 条里 2 条红，都是 `test_pet_ui` 里报「未找到 FFmpeg 解码器」的用例（第（十二）条）。架构门禁在 12 个文件的改动全部完成之后整套跑过，700 条全过。验收窗口要求的九个静态模块 47 条全过。结构检查退出码 0。默认冒烟没有单独跑；全量自测没跑。提交时的点名测试由提交工具跑，以本文件的证据行为准。
- （三）欠账少了吗：少了用户报的一处缺陷，撤销采用的那段代码删掉了（台账模块 9 增 35 删）；多了两个测试类 9 条用例和一条新需求 REQ-S03-07。没有新增文件，没有动任何门禁的阈值、基线和登记表。留下的欠账写在「未覆盖项」，最要紧的两条：模型写的结构稿在剧本结构阶段仍然显示未完成；用它做初步分镜这一步没有实际跑过。

## 改了哪些文件

- contract/script_contract.py（17 增 2 删）：新增 `_is_declared_structured_script(path, head)`；`is_structured_script` 改成两种认法任一种成立即可：本地规则版式（原来的判断），或者文件在「结构剧本」目录里、文件名声明是结构剧本、正文非空。来源那一行写着大纲、纲要、梗概的仍然拒绝，这一段没动。
- domain/storyboard_catalog_service.py（9 增 8 删）：`_catalog` 里分镜页的剧本列表原来只放 `structured_script_path` 那一份，改成放 `structured_script_paths` 的每一份（每个来源最新的一份）；「旧版」「原稿已变更」两个标记的规则不变，只是对每一份都判断。
- orchestrator/writing_preparation_ledger.py（9 增 35 删）：删掉 `_revoke_natural_script_adoption` 和 `_confirmed_basis`；`_save_preparation_state_guarded`、`_promote_revision` 只写台账，名字、参数和返回值不变，所以调用点（`writing_api.py`、`orchestrator/writing_unconfirm.py`）不用改；模块说明写明台账不动自然剧本的采用记录。
- writing_api.py（1 增 2 删）：从导入列表里去掉上面两个已删除的名字。全仓搜过，这两个名字在 `writing_api.py` 里只是被导入，没有别处使用。
- tests/test_script_structure.py（96 增 0 删）：新增模块常量 `EPISODE_SCRIPT` 和测试类 `ModelWrittenStructureScriptTests`（6 条）。
- tests/test_storyboard_catalog_snapshot.py（46 增 0 删）：新增测试类 `StructureScriptCatalogTests`（3 条）。
- tests/test_preparation_confirmation.py（14 增 17 删）、tests/test_writing_restart.py（12 增 5 删）、tests/test_writing_unconfirm.py（15 增 16 删）：7 条用例改断言，见下一节。
- docs/stages/S01_剧本准备.md（5 增 5 删）：REQ-S01-14、DES-S01-14 改写（项目设定、剧本大纲、角色卡的任何改动都不撤销自然剧本的采用；已经被撤销的项目要手动采用一次）；REQ-S01-88、DES-S01-78、DES-S01-88 里提到撤销采用的半句跟着改。
- docs/stages/S02_剧本结构.md（4 增 4 删）：REQ-S02-21、DES-S02-21 改写（两种认法、来源不能是大纲、已知限制）；REQ-S02-20 加一句说明；测试锚点行加上新测试类。
- docs/stages/S03_初步分镜.md（3 增 0 删）：新增 REQ-S03-07（剧本列表列出每份可用的结构剧本）、DES-S03-07 和锚点行。
- tasks_round/tasks_round_4119_result.md 是本文件。

## 改了哪些断言（7 条，都是因为需求变了）

依据：用户 2026-11-22 23:12 第 1 条「之前的项目大纲->设定->角色卡->自然剧本的逻辑链已经取消(相应功能比如文档名前加已确认), 4个文件可以同时或者逐个生成」；23:41 报的缺陷正是这条撤销逻辑造成的。原来这 7 条守的是「前面的文档一改，已采用的自然剧本就撤销」；需求取消以后，同一个场景改成守「采用不被撤销」。

- 原断言：`assertIsNone(script_contract.resolve_script_source(project))`；`assertIn('前置阶段已更新', selection['reason'])`；其中 2 条还有 `assertEqual(selection['path'], '')`。
- 新断言：`assertEqual(script_contract.resolve_script_source(project), script.resolve())`（下一阶段仍然读到原来采用的那份）；`assertNotIn('reason', selection)`（采用记录没有被写成失效）。

| 文件 | 原用例名 | 新用例名 | 备注 |
| --- | --- | --- | --- |
| tests/test_preparation_confirmation.py | test_confirm_last_rewrite_stage_promotes_revision_and_revokes_script | test_confirm_last_rewrite_stage_promotes_revision_and_keeps_script_adoption | 「采用版本切换到重写稿」「revision 清除」两处断言没动 |
| tests/test_preparation_confirmation.py | test_confirm_different_adopted_file_revokes_natural_script_adoption | test_confirm_different_adopted_file_keeps_natural_script_adoption | 原来有第三句（path 为空） |
| tests/test_preparation_confirmation.py | test_confirm_after_brief_change_revokes_natural_script_adoption | test_confirm_after_brief_change_keeps_natural_script_adoption | |
| tests/test_writing_restart.py | test_confirm_new_outline_invalidates_character_and_script | test_confirm_new_outline_invalidates_character_and_keeps_script_adoption | 新用例在开头先建一份自然剧本和它的采用记录（原用例里没有这一步），第二句新断言写的是「采用记录文件的字节前后相同」；「该步及下游确认失效」的断言没动 |
| tests/test_writing_unconfirm.py | test_unconfirm_revokes_natural_script_adoption | test_unconfirm_keeps_natural_script_adoption | 原来有第三句（path 为空） |
| tests/test_writing_unconfirm.py | test_unconfirm_then_reconfirm_different_file_keeps_adoption_revoked | test_unconfirm_then_reconfirm_different_file_keeps_adoption | |
| tests/test_writing_unconfirm.py | test_partial_adoption_of_confirmed_doc_trims_deconfirms_and_revokes_adoption | test_partial_adoption_of_confirmed_doc_trims_deconfirms_and_keeps_script_adoption | 截写文件、回退该阶段、台账记 partial_adoption 的断言没动 |

`tests/test_writing_restart.py` 的 `test_adoption_failure_restores_selection_and_pending_version` 没有改，照样通过。

## 新增的用例（9 条）

`ModelWrittenStructureScriptTests`（tests/test_script_structure.py，锚 REQ-S02-21）：

1. test_episode_layout_in_structure_folder_is_recognised_and_listed：按集排版的稿被认出、进列表、成为当前结构剧本。改前红。
2. test_structure_page_lists_the_model_written_script：结构页的文档列表里有它。改前红。
3. test_each_episode_file_stays_listed：第 1 集、第 2 集各一份，两份都在。改前红。
4. test_outline_source_is_still_rejected：来源写着大纲的不认。边界用例，改前改后都过。
5. test_name_and_folder_are_both_required_and_blank_is_rejected：文件名不合规、不在「结构剧本」目录、正文空白，三种都不认。边界用例，改前改后都过。
6. test_hidden_when_its_source_script_is_deleted：来源原稿删掉后不显示、文件还在。反向验证时这一条改前也过；之后补了一句「删来源之前它在列表里」的断言，补完没有再做一次反向验证。

`StructureScriptCatalogTests`（tests/test_storyboard_catalog_snapshot.py，锚 REQ-S03-07）：

7. test_model_written_episode_script_is_listed：分镜页的剧本列表里有按集排版的结构稿。改前红。
8. test_every_visible_structure_script_is_listed_not_only_the_newest：每份可用的结构剧本都在，不只是最新的一份。改前红。
9. test_structure_script_whose_source_is_gone_stays_hidden：来源原稿删掉的不进列表。改前红（它先断言删之前在列表里）。

## 命令与结果

下表的测试命令都在车道的 程序 目录下、进程优先级降到 BelowNormal 跑。界面测试整轮在隐藏桌面里跑。日志放在项目的临时目录，没有放进 程序 目录。

| 命令 | 结果 |
| --- | --- |
| 在一个已合入、工作树干净的闲置车道目录里从主干切分支 codex/fix-script-adopt-select（当时主干是 89fdb829） | 没有新建工作树目录 |
| 两个只读诊断脚本（在主工作树的 程序 目录跑，读用户当前项目，23:44 至 23:50） | 采用记录是空的并带「前置阶段已更新」；结构页可选的结构剧本 0 份；分镜页剧本列表 0 份；「结构剧本」目录里有 3 份文件，1 份不被认、2 份因来源已删隐藏。没有写任何文件 |
| 第一遍（改动之后，基准 89fdb829，23:55:22 至 23:57:01）：python.exe -B run_selftests.py -k script_structure storyboard_catalog_snapshot preparation_confirmation writing_restart writing_unconfirm | 退出码 1，「定向：忽略增量台账，执行 12 个匹配测试文件」「共 119 条用例，94.9 秒；1 个文件有红」「实际跳过 0 条用例」。红的是 `test_script_structure` 的 `ScriptStructureTests.test_stage_execution_reads_downloaded_preparation_script`：「AssertionError: False is not true」，工具提示「[SUSPECT_CONCURRENCY] 红项发生时有其他 PID 持有 GUI 令牌；建议串行复跑」。新加的和改过的用例都过 |
| 串行重跑（23:57:15 至 00:00:58）：python.exe -B run_selftests.py -k test_script_structure --serial | 退出码 0，「执行 7 个匹配测试文件」「共 64 条用例，220.4 秒；0 个文件有红」「ALL TESTS PASSED」（其中约 200 秒在等界面令牌） |
| 反向验证（00:01:51 至 00:05:40）：把 4 个产品文件另存到系统临时目录，git checkout 这 4 个文件回到基准，跑第一遍的同一条命令，跑完拷回 | 退出码 1，「共 119 条用例，226.3 秒；5 个文件有红」：test_script_structure 3 条、test_storyboard_catalog_snapshot 3 条、test_preparation_confirmation 3 条、test_writing_restart 1 条、test_writing_unconfirm 3 条，合计 13 条，正是 7 条改过的和 6 条新加的；第一遍红过的那条这一遍是过的。拷回后 4 个文件的 sha256 前 12 位和另存前一致（560ef97f11fe、8adc26514f10、a44178636120、91f3e27ee76e），git status 还是原来的 12 个文件 |
| git merge --ff-only master（00:06） | 快进到 02e2c3e0，没有产生提交；主干这几步没有改本轮的 12 个文件（快进前用 git diff --name-only 核过） |
| 大一圈定向（全部改动之后，基准 02e2c3e0，00:06:43 至 00:10:35）：python.exe -B run_selftests.py -k script_structure storyboard_catalog req_anchor_s02 req_anchor_s01 req_s03 critical_chains stage_completion script_workspace_service preparation writing_restart writing_unconfirm writing_ledger writing_api storyboard_page_controller storyboard_scope script_contract requirement_traceability stage_flow storyboard_plan | 退出码 1，「定向：忽略增量台账，执行 36 个匹配测试文件」「共 490 条用例，227.1 秒；1 个文件有红」「实际跳过 0 条用例」。红的只有 `test_script_contract` 的 `AuditTests.test_the_audit_covers_every_script_skill`（两份技能名单不一致）。第一遍红过的那条所在的分片 16 条全过 |
| 九个静态模块（00:10:35 至 00:11:49）：python.exe -B -m unittest tests.architecture.test_static_hygiene tests.test_static_names tests.architecture.test_print_ratchet tests.architecture.test_module_size_ratchet tests.architecture.test_function_size_ratchet tests.architecture.test_silent_exception_ratchet tests.architecture.test_todo_comment_snapshot tests.architecture.test_skip_hygiene tests.test_copy_rules | 退出码 0，「Ran 47 tests in 71.950s」「OK」 |
| python.exe -B governance\check_structure.py --check --summary（00:11:49 至 00:11:58） | 退出码 0，输出里 ok 是 true，delta 的 added、removed 都是空表；finding_count 是 1、findings 是空表，那一条是什么我没有展开看 |
| python.exe -B smoke_test.py --architecture（00:11:58 至 00:22:31） | 退出码 0，「Ran 700 tests in 632.519s」「OK」「✅ 架构治理测试：tests/architecture」 |
| 对照（00:22:46 至 00:22:50）：把 4 个产品文件另存后检出回基准，python.exe -B run_selftests.py -k test_script_contract，跑完拷回 | 退出码 1，「执行 2 个匹配测试文件」「共 64 条用例，1.9 秒；1 个文件有红」，红的还是 `AuditTests.test_the_audit_covers_every_script_skill`，报错原文和大一圈里的一样。拷回后 4 个文件的 sha256 前 12 位和另存前一致，git status 还是 12 个文件 |
| python.exe -B run_selftests.py -k file_cache model_output_contract sanhu_mode ui_edges_controls pet_ui（全部改动之后，00:22:50 至 00:24:09） | 退出码 1，「执行 6 个匹配测试文件」「共 699 条用例，75.8 秒；1 个文件有红」。红的是 `test_pet_ui` 的 `FrameBatchSeamTests.test_auto_keyframe_with_no_gap_finishes_as_completed` 和 `FrameBatchSeamTests.test_it_says_nothing_when_there_is_no_gap`，都是「ValueError: 未找到 FFmpeg 解码器，请安装或配置 FFmpeg 后重试」 |
| python.exe -B scripts\dev.py claim | 领到轮次 4119 |
| git diff --numstat | 12 个已跟踪文件（4 个产品、5 个测试、3 份文档），行数见「改了哪些文件」；没有新文件（不含本文件） |
| python.exe -B scripts\dev.py commit（点名 script_structure storyboard_catalog_snapshot preparation_confirmation writing_restart writing_unconfirm） | 结果以本文件的证据行和提交记录为准 |

## 如实说明

- （一）没有在真实界面上点过，没有截图，没有从车道起真实的应用窗口。「选得到」是用服务层的返回值验证的：结构页用 `script_structure_documents`，分镜页用 `storyboard_catalog(project, 'script')`，就是两个页面建列表时调的函数。
- （二）诊断是只读的。用户项目里被清空的那条采用记录我没有改（不替用户改项目数据）。合入并重启应用以后，要用户自己采用一次自然剧本，结构页上方才不再显示「待选择采用版本」；模型写的那份结构剧本不依赖这一步，合入后就能在两个页面的列表里看到。这两句是按代码和只读诊断推出来的，没有在用户的项目上试过改后的程序。
- （三）顺序不对：这一轮是先改的产品代码、后写的测试，不是先红后绿。用反向验证补：撤掉产品改动后 13 条红。没有用 git stash，用的是另存再检出、拷回后核对指纹。`test_hidden_when_its_source_script_is_deleted` 那一句补的断言是反向验证之后加的，没有单独见过红。
- （四）第一遍红过一次的 `test_stage_execution_reads_downloaded_preparation_script`：原因没有查清。事实只有这些：第一遍并行红，工具标了疑似并发；串行重跑过；反向验证那一遍（并行，不含产品改动）过；快进后的大一圈（并行，含产品改动）也过；提交工具点名跑的那一遍以证据行为准。读代码看到的一种可能：`stage_exec.run` 在这一步勾选的技能读不出来时返回 ok=False，而 `stage_flow.selected_skills` 遇到任何异常都当成空表；这条路径不经过本轮改的函数。这只是读代码的推测，没有复现，也没有在不含本轮改动的主干上反复并行跑来确认它本来就不稳。请验收时留意这一条。
- （五）模型写的结构稿和本地规则做的结构稿的差别（已写进 REQ-S02-21）：它没有派生清单，所以剧本结构阶段的完成检查（REQ-S02-23）仍然报未完成；这不挡在初步分镜里选它（读代码，阶段依赖只在前一阶段是「失败」时才拦）。它没有来源登记，所以不参与「同一来源只留最新一份」和回收。来源那一行如果不是能找到的文件路径，按现有规则仍然不显示。
- （六）用选到的模型结构稿去做初步分镜，这一步要调模型，没有跑过；分镜的范围选择（按集、按场）认不认这种版式，也没有验证。
- （七）默认项会变：`structured_script_path` 取最新的一份可用结构稿，以前模型写的稿不算，现在算。项目里同时有本地规则做的稿和更新的模型稿时，结构页和分镜页默认会指向模型稿，剧本结构阶段可能从「已完成」变成「未完成」（见第（五）条）。这是让模型稿可选的直接后果，没有另外处理。
- （八）「来源原稿删掉后结构稿不显示」是 REQ-S02-21 现有的规则，没有动；已经问用户要不要改成带「来源已删除」标记显示，等答复。
- （九）基准：第一遍、串行重跑、反向验证是在 89fdb829 上跑的；快进以后的那几遍是在 02e2c3e0 上跑的。架构门禁和静态模块是在本文件写进车道之前跑的，没有包含本文件。
- （十）本轮的代码由需求受理／机动执行窗口直接写。按四窗口协调第 10 条，除验收窗口复核和 `verify` 外，还要加一张只读审查卡。本窗口没有合入、没有登记已验收。
- （十一）大一圈里红的 `test_script_contract` 的 `AuditTests.test_the_audit_covers_every_script_skill`：它比的是技能目录里的名单和登记的名单。做了对照：撤掉 4 个产品文件的改动单独跑这一组，同一条用例同样的报错。编码预备窗口 23:52 的心跳也说过它在车道里未改动的基准上就红（车道里少两个技能目录）；「少两个目录」这个原因我没有自己核对。队列项的验收命令里没有放 `script_contract` 这个关键词。
- （十二）另一组里红的两条 `test_pet_ui` 用例报的是本机找不到 FFmpeg。编码预备窗口 23:52 的心跳说这两条是已知的（本机没有 FFmpeg）；我没有在不含本轮改动的基准上对照跑这两条，只是报错内容和本轮改的函数对不上。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；没有截图；未 push、未 merge。
- 用模型写的结构稿做初步分镜没有实际跑（要调模型）；按集、按场的范围选择没有验证。
- 模型写的结构稿在剧本结构阶段仍显示未完成（没有派生清单）；要不要给它补清单或者放宽完成检查，没有做，等需求。
- 来源已删的旧结构稿仍不显示（等用户决定）。
- 用户项目里已经被清空的采用记录没有修，要用户手动采用一次。
- 第一遍红过一次的那条用例没有查清原因。
- 取消先后链的其余部分（文档名前的「已确认」、四份文档同时生成、采用后作为后续阶段的参考）不在本轮，另出需求文档和任务卡。
