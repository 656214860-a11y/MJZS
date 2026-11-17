# R3227：同步主干包化与完整运行环境兼容收尾
<!-- round-evidence: {"commit_base": "72afa1e8", "credential_hits": 0, "evidence_sha256": "9940f4b28bb07a10", "exit": 0, "failed": 0, "passed": 31, "round": 3227, "tests": "run_selftests.py -k stdlib_closure copy_rules branch_coverage_floor"} -->

## 三问

1. 类型：兼容轮＋主干同步；处理已批准的完整Python/白名单依赖带来的测试契约变化，不新增业务功能。
2. 验证：默认冒烟9/9；核心8文件100条通过；stdlib/copy/branch覆盖3文件31条通过；完整架构502/502、186.287秒。发布安全全量三次启动被活动后台全量拒绝（exit3），未实际执行，不能称绿。最终桌面启动/正常退出未完整验收。
3. 欠账：旧架构四项已由主干更新＋补齐现有验证资料解决；平台分支覆盖实测38.1%高于36%原下限；标准库裁剪旧契约改为完整环境契约。发布全量和严格隔离GUI保留未完成，未降门槛。

## 主干同步与提交映射

从原d29e1e83接续，经master实际同步至dd7ce8e（R3226）。起初尝试merge，只有HTTP默认opener与重复R3215政策三处冲突；后按runbook使用rebase，先备份本轮三文件于common-dir再abort自己merge并rebase，未改其他车道。重复R3215自动跳过，HTTP冲突保留RequestsJsonOpener；主干包化更改保留。没有在功能树提交或手改project_status。

现提交映射：R3218 e5389134（原89987d28）；R3220 853b04fa（原76b291ac）；R3224 72afa1e8（原32f92795）。各轮报告内旧hash为当时真实提交，不伪改历史凭据。

## 本轮改动

1. tests/test_stdlib_closure.py：适配用户已批准的完整Python3.14.7。原10条4红（requests/urllib3解析、恢复模块物理存在、tkinter.colorchooser假设）；现12条全绿。保留启动闭包可解析和58项历史清单/去重，恢复可移植模块必须在盘；包子模块缺失改临时虚构包，不再依赖实际Tk裁剪。第三方仅requirements明确白名单、仅当前runtime site解析；新增未登记/缺失/个人sys.path伪包和try ImportError不能蒙混等负例，没把任意ImportError放行。
2. tests/test_copy_rules.py：仅PROMPT_FILES两个路径 pet_llm.py/continuity_ledger.py → infra实体路径；原14条断言不动。此路径遗漏已由另一主干R3229/R3231并行修复（本树基线dd7之前），后续同步可自动收敛。
3. 维护记录/分支覆盖率基线.json：真实工具测量HTTP/platform/cli_streaming与既有open_https_redirect/platform_opening目标，共72条全绿，platform45/118=38.1%≥原floor36%；只更新该实体行及总计1226/2340、84模块，新增module_measurements记录合成定向快照来源，未降下限。最初子集36/118、后42/118均不足，没有写入；完整原targets尝试遇无关失败后停止，没有假称全套测绿。
4. runbook §9：完整标准库＋生产锁替代旧零依赖/裁剪环境的当前描述，历史3.15/a2凭据仅作历史，发布前全量/Tk仍必需。
5. 正式任务书更新状态与未完成边界。

## 测试和基线闭环

- 核心HTTP/platform/redirect/boundary/dependency/claim/dev_entry：100条，30.7秒，0红。
- stdlib_closure/copy_rules/branch_coverage_floor：31条，23.8秒，0红；默认冒烟9/9（隐藏桌面探针成功）。
- 完整架构在补资料前4项红，补后唯platform决策点元数据红，真实重测后502条、186.287秒、OK。
- 既有技能资料AIGC创作全流程在Git为gitlink但无.gitmodules映射；新工作树缺包。只读复用主树同名技能资料与维护记录/基准历史.json到本树，不伪造文件/测试结果。相关4文件34条已全绿。
- 完整安全全量被R3226、后R3231后台全量持锁拒绝，exit3，未force/未删锁。共同进程曾为50320/50736，后49248/44144，以运行时状态为准；日志只记录拒绝，不能算执行全量。

## 候选副本实际证据（旧feature源码，不是rebase后最终发布版）

现有distribution_build.py、verify未使用allow-undecided；复用主树ffmpeg9文件263905916字节到工作树runtime，无用户数据/私有配置源。requests-r3224-final及中文空格副本各2457清单文件341793218字节（含摘要清单实际2458文件342252637字节），排除项零命中、keep完整、digest零mismatch/extra。

副本自身Python3.14.7 -I -X utf8 -B：requests2.34.2/Pillow13，PNG内存往返，CA加载118根证书，五主要入口导入，真实本地RequestsJsonOpener请求HTTP200中文JSON，中文空格路径复验通过。共用证据summary在common-dir/requests-migration-evidence/r3224-final-agent6，不将其当新HEAD摘要。

GUI使用额外全新可丢弃副本，经gui_hidden运行真实启动器，仅Tk定时destroy；Tk和Desktop初始化、mainloop进入/返回均真，但first_paint_complete=false。审计阻止副本外D:/漫剧下载/项目与注册表访问，故exit1/ok=false，不是发布绿，也未覆盖finish_close/cleanup。

只读根因：domain/projects.py默认downloads_root=D:/漫剧下载，可用副本config.json产品支持字段隔离；宠物首次attach会尝试注册开机自启Run键，尚无Desktop入口可配置的禁用seam。严禁为测试放开全局注册表写入或真实个人配置。下一步只在丢弃副本预置下载目录继续核验，并明确首次自启行为是否属于现有产品契约；本轮未改业务默认值。

## 提交、后续和完成边界

本轮提交由标准dev.py commit生成31条定向证据；实际hash以git log与evidence/R3227.json为准。未知测试临时目录不暂存、不擅删；本树源码已记录可恢复。

剩余：新HEAD完整安全全量、新HEAD发行副本重建/Tk正常启动退出、合入队列处理、主干运行环境按生产锁一致化（主树requests仍2.32.3），任务完成文件。任务书整体不标完成，目标保持active；锁不会被当成已穷尽替代路径的永久阻塞。
