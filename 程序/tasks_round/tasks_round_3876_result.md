# R3876 最终治理候选覆盖率重测与分支状态检查口径修正
<!-- round-evidence: {"commit_base": "08997bc5", "credential_hits": 0, "evidence_sha256": "b47e1688147b0589", "exit": 0, "failed": 0, "passed": 16, "round": 3876, "tests": "run_selftests.py -k architecture.test_branch_coverage_floor architecture.test_coverage_baseline architecture.test_round_baselines"} -->

## 三问

1. 类型：验证/基线及目录治理验收修正轮；在独立 codex/governance-final 工作树上完成，不改主树状态页或其他会话索引。
2. 验证：最终候选冒烟9/9；登记84份；真实分支覆盖率102个目标全部通过，103实体、1742/3062决策点；覆盖floor/行覆盖口径/状态规则12/12。正式安全全量在本轮提交后的干净内容树继续运行；当前不宣称任务全部完成。
3. 欠账：修复新工作树缺精确gitlink内容、属性行尾及隐藏桌面FFmpeg路径初始化失败造成的环境红；保留全部测试断言和覆盖floor。统一“功能分支不能改状态页”与轮次连续性检查的范围，主干连续性不放宽。

## 基点与集成边界

- 最终候选基点 f583e096，治理集成08997bc5（R3868），保留后续master新增源码和A15文档，文档登记84份而非旧候选83份。
- 原候选2ed443f0及其未提交合并修复仍保存在旧树，不触碰或重置。主树其他会话的暂存内容未处理。
- 最新主干18个L0/L1实体与旧候选不同，故旧树1908条测量只作原轮证据，本树重新运行生成器，不复制旧覆盖数字。

## 失败诊断与闭环

1. 旧候选覆盖首跑1908条，三处红：两项图片解码和两证据日志CRCRLF。原工作树缺FFmpeg，补复制后图片问题仍在隐藏桌面复现。
2. 最小复现：同PNG/同参数/同隐藏桌面中，工作树复制版ffmpeg连-version返回3221225794（0xC0000142，初始化失败），stderr空；主安装目录同hash的ffmpeg正常。单线程/console flags改变无效。非GUI前序479条全部通过，证实不应降低图片验证。
3. 只删除本次自建、忽略且非Git跟踪的旧树ffmpeg测试副本，PATH明确前置主安装运行环境/ffmpeg/bin。隐藏图片两用例2/2通过；生产图片校验、断言未改。
4. 旧树最终真实覆盖1908目标用例通过、102实体1691/2978、floor10/10；旧树完整架构616/616。但新候选实体不同，未复用为新树当前成绩。
5. 新候选首覆盖1948条有三失败：desktop.py/ui/skill_panel.py工作树行尾LF而.gitattributes及断言要求CRLF，两个已跟踪gitlink未材化导致技能数量少项。依属性恢复CRLF，git add后无源码diff；仅使用索引固定commit git archive材化两包，不复制脏内容、不改gitlink指针；标准test_line_endings+test_skill_user_layer26/26通过。
6. 新候选第二次覆盖102目标全通过，生成器写新JSON（tests_ok=true），103实体、1742/3062点。精确用例总数以临时原始日志与最终记录为准，不先填估计数。覆盖floor未降。

## 分支状态检查范围

项目规定仅master可提交project_status；原门禁却把分支新结果文件也当成主干状态要求，导致干净分支无法生成正式绿色全量。R3876在test_round_baselines明确：

- master/main/分离主干候选沿用“状态轮次=全部已合入最新结果+1”；
- 功能分支状态文本必须与master共同基点逐字相同，该基点自身仍须连续；
- 改页、缺轮次或坏基点都由新增反例测试拒绝；最终合并轮仍负责推进状态页。

runbook§12同步此口径。测试2/2通过；没有skip或临时改页掩盖。

## 测量与凭据

- 解释器：D:/漫剧制作助手/运行环境/Python/python.exe，PYTHONUTF8=1，-B。
- 工具路径：PATH前置 D:/漫剧制作助手/运行环境/ffmpeg/bin，最终树不复制运行环境。
- 真实覆盖命令：标准GUI令牌→scripts/gui_hidden.py→scripts/branch_coverage_report.py（当前基线targets102项）--json 维护记录/分支覆盖率基线.json。
- 日志：执行器Temp/governance_final_coverage.log；真实数据在本提交的分支覆盖率基线.json，无失败时写入。
- runbook§11区分历史行覆盖675/133/542/15与本轮分支重测，不冒称整仓覆盖率或当前全量。

## 待最终验收

提交本轮后标准run_selftests.py --all --safe --force在干净树取得正式凭据，失败按实际原因闭环；随后逐项任务完成文件、合并master与主树复核。此前所有“未完成全量”的记录保持事实，不倒填通过。
