# R1496 结果
> 说明：车道分支 `codex/wip-R1482`，合并时正式记为 R1496。验收：在真实环境直接 unittest 跑 test_script_contract、锁契约/锁面板新增用例、test_master_skill、test_desktop_compact_layout 共 86 条通过；run_selftests -k skill_panel idea_chat idea_brief workflow_settings stage_config test_core pet_settings desktop_startup test_ui_edges 全部通过。
1. 本轮类型：功能轮（界面＋契约）。
2. 测试跑了吗：跑了；114 条定向用例首次 1 红，增量修复已闭环；完整任务书范围未跑完，不宣称全量绿。
3. 欠账变化：实现六个新锁；新增 GUI 回归用例待执行，未增加 SKILL 适配范围；不更新全量凭据。

## 新锁与包内依据
- track：赛道，无预选；SKILL.md 〇·0。
- material_source：素材来源，无预选；SKILL.md 〇·1（四项完整文案）。
- reference_mode：全能参考模式／首尾帧模式，默认前者；SKILL.md A，仅 Seedance 2.5 生效。
- splice_mode：段缝衔接方式，默认末帧定格承接；SKILL.md D；本任务约定选填，标注多段任务用。
- style_base：真人实拍质感／2D 手绘动画／3D CG 动画／水墨二维；SKILL.md I、style-lock-protocol.md §三 Step 1。
- style_directors：逗号分隔，最多四张；SKILL.md I、style-lock-protocol.md §三 Step 3。
- 上述 SKILL.md 位于 skills/00全流程SKILL/AIGC创作全流程/short-drama-director/。
- 两份风格参考位于同包 references/style-bible/；另读 style-archetype-taxonomy.md §二至§五，区分基底与原型。

## 改动
- script_contract、总控.json：六锁、别名、选项、默认值、依赖条件、2026-10-15 必填生效日期。
- stage_config：从程序 projects.json 登记记录读取创建时间；未知时间按旧项目兼容，不用目录复制时间推断。
- workflow_settings/master_skill 既有委托入口：新项目缺赛道／来源阻断；旧项目只提供警告；旧五锁原规则保留。
- production_lock_fields、skill_panel、desktop、ui_tokens：共用 FlowBar 控件，保留原五项顺序与创作窗原文本字段；黄色必选、参考模式置灰、多段说明。
- idea_brief_form、idea_chat：新锁标签与别名提取、按创建时间筛必填；desktop 传入项目创建日期。
- stage_execution_service：沿用现有发布器保存制作锁及简报；导演卡超过四张拒绝保存。
- workflow_settings：各阶段注入已选新锁，依赖不成立的参考模式不注入；注明“以项目锁定值为准，不要再向用户弹问这些锁”。
- PROJECT_MAP：登记共用视图模块；新增两个 tests 文件，既有断言未改。

## 实际验证
- 指定解释器：D:\漫剧制作助手\运行环境\Python\python.exe。
- 首次 run_selftests.py -k（任务书范围，简报按实际模块名）停留 GUI 令牌申请约五分钟，停止；未执行用例。误带的 --no-receipt 不受该运行器支持，无有效作用。
- 第二次同范围加 --gui-wait 0，68.7 秒仍停留令牌获取，停止；未执行用例。
- 实跑：run_selftests.py --layer service -k test_script_contract test_master_skill test_idea_inline_brief test_idea_attachment_brief test_idea_local_brief test_idea_semantic_brief test_workflow_settings test_stage_config test_core。
- 实跑匹配 7 文件、114 用例、86.9 秒、1 红；模块导入通过。service 分类中原有部分简报 Tk 用例实际执行，不能据此宣称所有 GUI 覆盖通过。
- 首红：test_idea_inline_brief.InlineBriefTests.test_coordinator_refreshes_editable_locks_without_save_badge；原视图替身无 lock_row。修复保留 lock_inputs 协议。
- 增量 unittest：上述失败方法＋test_script_contract_production_locks，共 7 条，6 通过、1 红（新增日期测试发现 Path.root 取驱动器根）。
- 修复路径类型判断后，仅复跑 ProductionLockContractTests.test_creation_date_uses_registry_not_copied_directory_time，1 条通过。
- 两个实际失败均已分别验证修复；新增锁契约、日期门禁、持久化、别名、各阶段注入用例通过。
- 最终 12 个改动 Python 文件 AST 检查通过；git diff --check 通过（退出码 0）。
- 测试器生成的分层基线恢复至任务开始内容；不将部分测试改写为全量凭据。

## 未完成／边界
- 新增 test_skill_panel_production_locks 的真实 Tk 联动与窄窗用例未运行；test_skill_panel_imported、test_desktop_compact_layout、test_core 等完整指定范围未验收。
- GUI 令牌获取未正常返回，未改测试运行器、未绕过跨树令牌；需在令牌恢复后补跑剩余 GUI 与完整定向范围。
- I 锁仅预设入口；递进式技法家族、导演卡推荐、参数转译仍由模型按协议完成，未实现该对话流程。
- 未改任何 *.skill.md、全流程包内文件或 project_status.md；未领取轮次、提交、切分支、合并或推送。
