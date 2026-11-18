# R3285：SKILL预算全量失败闭环
<!-- round-evidence: {"commit_base": "b9af2205", "credential_hits": 0, "evidence_sha256": "a683ff4de9b617f9", "exit": 0, "failed": 0, "passed": 43, "round": 3285, "tests": "run_selftests.py -k skill_context_budget_prestage writing_context_budget_guard branch_coverage_floor complexity_ratchet function_size_ratchet"} -->

## 三问

- 类型：§3.2 修复轮，用户授权的最终验收阻断项闭环，中央领号R3285。
- 验证：首次候选安全全量8601条、895.9秒、10文件有红、5条既有跳过；明确NO_RECEIPT，不写绿色凭据。预算门禁等七组77/77、窗口夹具35/35、测宽/标准PATH相关27/27已复测通过；UI几何及来源并发仍在修，最终全量待补。
- 欠账：所有首次全量失败现已定向闭环，最终安全全量复验、主线合并与正式凭据未完成，不宣称任务完成。

最终闭环汇总：来源并发50/50+100/100；其新决策点基线按五组既有消费者真实测量77/77，file_index为74/93=79.6%≥78%原下限。预算实体14/25=56%≥54%原下限，其他实体历史测量保留并显式联合来源，不降低floor。静态函数体积修复后语音设置9条+体积2条11/11；全部首次失败均有具体处置，不能以这些定向结果代替最终全量。

## 首次全量结果与诊断

代码HEAD b9af2205，预先同步master056f882f。候选测试临时将本树状态头设最新结果+1，结束finally恢复；按--allow-dirty-diagnostic运行，避免分支提交共享状态，未生成receipt。

原始日志common-dir `task-logs/skill-budget-final/full-safe-candidate.log`。等待其他车道R3267全量锁后正常跑完，8601条/730文件、895.9秒，10红文件：

1. branch_coverage_floor：L0新增前缀逻辑改变decision points，需真实测量更新基线，不手工伪造点数或降floor。
2. complexity_ratchet：新增两个引用helper参数个数超过7，收为最小上下文参数对象，不抬阈值。
3. copy_rules：预算拒发文案超45字，精简同时保留正文合计/预算/技能名及拒发含义。
4. script_agent_delivery_assembly、idea_semantic_brief、stage_reasoning：旧合成API模型fixture缺窗口，按新未知API拒发契约补明确合成128K窗口，原业务断言不变。
5. file_origin_provenance：并发来源登记时项目索引路径被错误拒绝，待独立复现，不归因预算。
6. model_manager_actions：真实Tk窗高1061<请求1227，待复现/核需求。
7. skill_notes：无Tk的旧面板fixture触发最新公共测宽root需求，待最小fixture修复。
8. ui_edges_tables：滚动位置相差36px，待串行复验。

## 分工与写入边界

- full-fix-core：预算两个helper/调用点、按既有入口真实重测分支覆盖率基线、相关回归。
- full-fix-ui-fixtures：上述四UI/来源相关测试只读定位并复现，只在确实fixture变更时调整，不弱断言、不skip、不私改产品。
- 父代理：三个API语义测试的合成窗口fixture、本结果文件、集成复验/提交。

环境：PYTHONUTF8=1、PYTHONIOENCODING=utf-8，PATH含D:/Tools/ffmpeg/bin，随附解释器，Tk由正式隐藏runner执行；用户数据/密钥/生产模型池不读写，外部请求全桩。

## 中间闭环证据（最终提交前续填）

- full-fix-core 已完成：两个helper改为 `_ReferenceContext` 五字段对象，参数为6/4；文案3行42固定字，保留数字detail；7组77/77、36.189秒。真实覆盖率脚本仅预算实体测量32/32、1.581秒，row14/25=56.0%≥既有floor54.0%，其余83实体行原样；targets仅增prestage，aggregate1266/2370；联合快照来源写明，失败的原全targets尝试未用于绿色凭据。日志common-dir `task-logs/R3285-fullfix-core/`。
- 父代理窗口fixture三文件只补显式合成128K，无业务断言变化：35/35、76.3秒（含跨树GUI排队），日志 `R3285-fullfix/window-fixtures.log`。
- full-fix-ui-fixtures：skill_notes仅patch视觉测宽边界保业务断言；标准PATH后provenance/notes27/27。两个真实UI问题最小修复后七文件65/65、36.5秒；语音设置复用ScrollForm+固定底部动作；滚动根因为子控件异步换行改变请求高度却被own Configure门禁吞掉，3行修复且撤销无效尝试，不降原assert。新增容器helper使函数体积门禁合规，function-size+model-manager11/11、3.4秒。完整对照与日志common-dir `task-logs/R3285-ui-fixtures/report.md`。
- 来源登记原并发用例100次82绿18红，证明真实竞争；独立 provenance-race-fix 已抓到resolve临时返回带\\?\\盘符前缀而root不带，同实体被误判越界。补丁稳定absolute/normcase锁key先锁后校验，并仅在严格parent/leaf非reparse且路径仅差Win32前缀时容忍拼写差异，保symlink/junction越界防护。确定性回归原1红后新3项及边界已绿；最终provenance+file_index50/50；原并发用例100/100、53.267秒，`provenance-concurrent-100-green.log`；新增确定性红/绿均保留。最终strict parent/root补强后新3项再次验证。原始100次18红→100次0红，未降低并发或断言。
- 接续要求：等UI/来源两个子会话ready并收日志后，父默认冒烟/静态复验，统一入口提交R3285；禁止与子代理并发写其文件。之后代码静止重跑候选safe全量（使用既有commit_round.wait_for_lock自动排队，临时状态头只诊断最后finally恢复，日志新文件不要覆盖首次失败），全绿后再正式merge-queue/serve合master并跑匹配master正式receipt。当前master056f882f，需合入前重查，无推送。四轮提交abd48c38/cd0302b2/dd6a7cd4+同步dec4239c/b9af2205均已保存。最终任务完成文件尚未写，goal未完成不能标TASK_COMPLETE。
