# R4126 结果：SANHU-FIX-4 三虎固定文案对齐界面
<!-- round-evidence: {"commit_base": "8c6910f7", "credential_hits": 0, "evidence_sha256": "c04b76b3183842f7", "exit": 0, "failed": 0, "passed": 167, "round": 4126, "tests": "run_selftests.py -k sanhu_mode stage_flow pet_agent"} -->

## 开头三问

（一）本轮属于哪种类型：修复轮。任务卡 W6B-SANHU-FIX-4（写卡：编码预备窗口；依据三虎只读审查报告的 S-06、S-07、S-13），车道 codex/sanhu-fix-rules，叠在 8c6910f7（R4115，SANHU-FIX-5）之上，同一目录同一分支单独一笔提交。

（二）测试跑了吗、三个基线：

- 点名测试 `run_selftests.py -k sanhu_mode stage_flow stage_command_contract manual_plan pet_agent`：改前实测 224 条、退出码 1，红 5 条且全部是预期位置——SanhuCopyWordingTests 的 test_auto_final_off_copy_points_to_manual_sync、test_final_page_ask_is_about_syncing_not_adopting、test_copy_does_not_name_removed_buttons、test_unchecked_skill_copy_points_to_the_skill_icon，加 RetryAuthorityTests.test_verdicts_carry_only_action_and_hint；改后实测 224 条全过、退出码 0、ALL TESTS PASSED。
- 回归 `run_selftests.py -k pet_ui ui_edges_autopilot`：实测 647 条、退出码 1，红的正好是已知 2 条——test_pet_ui.FrameBatchSeamTests.test_auto_keyframe_with_no_gap_finishes_as_completed 与 test_it_says_nothing_when_there_is_no_gap（本机没有 FFmpeg），未修。
- 静态检查 `run_selftests.py -k copy_rules static_names`：实测 26 条全过、退出码 0。
- 架构门禁 `smoke_test.py --architecture`：实测 700 条全过（OK）、退出码 0、失败集合为空。
- 默认冒烟没单独跑；全量自测没跑。
- 新增 7 条用例：test_sanhu_mode.py 新类 SanhuCopyWordingTests 5 条（其中一条不建窗口钉定稿状态条文案），test_stage_flow.py 新类 ManualLabelGuardTests 2 条（钉「按钮名表里的名字在对应页面上真的存在」＋登记豁免表与 MANUAL_LABELS 全键一一对应）。
- 改了 1 处已有断言：test_pet_agent_error_wiring.py 的 test_verdicts_carry_only_action_and_hint 中 auth 一行。原断言 `'auth': ('notify', '接口密钥无效或没配：检查 .env 里的 Key')`；新断言 `'auth': ('notify', '接口密钥无效或没配：到「模型管理」里检查密钥；用 .env 配置的，检查里面的 Key')`。理由：密钥现在也可以在「模型管理」窗口里填，只叫用户看 .env 不全。没有删除或改弱别的用例。

（三）欠账少了吗：十处指向已删除控件或说错对象的固定文字已按接口契约原地改对。留下的欠账：MANUAL_LABELS 里两项豁免——script「手动制作剧本」（剧本页入口在底部输入框，按钮有意删掉，tests/test_manual_gate.py 守着）、animatic「手动制作分镜预演」（页面按钮叫「生成分镜预演」，改名由发送链路那一项定）。无新增欠账。

## 改了哪些文件

- ui/desktop_automation_tick.py：auto_final_state 文档串 off 档说明、off 状态句、retry_auto_final 早退句共 3 行改字（不再叫用户「勾上」「自动生成定稿」，改指「手动同步资产」按钮与全自动模式）。
- ui/pet_ui_voice.py：open_chat 的 notice 1 行（「点『确认』」改为「在回复框按回车」）。
- ui/pet_ui_stages.py：export_delivery 文档串与 notice 共 2 行（交付页入口改说「手动制作交付」，平台版本导出指到「后期剪辑」页）；run_skill 未勾 SKILL 句 1 行（阶段内部名改 STAGE_NAMES 中文名，去处改指底部输入框「技能」图标）。
- ui/pet_ui_support.py：PAGE_ASKS 第 7 项 1 行（分镜定稿页问句改说「同步资产、生成定稿」，不再说「采用掉」）。
- orchestrator/stage_exec.py：未勾选 SKILL 提示 1 行（不再提「阶段配置」「恢复默认」，改指「技能」图标）。
- ui/pet_agent_rules.py：VERDICTS 的 auth 一行（密钥提示补指「模型管理」窗口）。
- tests/test_pet_agent_error_wiring.py：同上一行断言同步（见开头三问（二））。
- tests/test_sanhu_mode.py：只增 97 行——新导入、_StatusLine/_AutomationHost 两个辅助替身、SanhuCopyWordingTests 五条用例；已有类与用例未动。
- tests/test_stage_flow.py：只增 42 行——ManualLabelGuardTests 两条守卫；已有内容未动。
- 本结果文件 tasks_round/tasks_round_4126_result.md。

## 每一句的原文和新文

1. ui/desktop_automation_tick.py 第 163 行（auto_final_state 文档串）：
   原：`          off      「自动生成定稿」没勾上`
   新：`          off      三虎不在全自动，不会自动同步定稿`
2. ui/desktop_automation_tick.py 第 182 行：
   原：`            return state('off','「自动生成定稿」没勾上：勾上之后资产一补齐就自动同步（定稿会把工作稿移入回收站，可恢复）')`
   新：`            return state('off','三虎现在不会自动同步定稿：把三虎切到全自动后资产一补齐就自动同步，现在也可以点「手动同步资产」（定稿会把工作稿移入回收站，可恢复）')`
3. ui/desktop_automation_tick.py 第 205 行：
   原：`                return '未开启「自动生成定稿」：勾上之后资产补齐才会自动同步。'`
   新：`                return '三虎现在不会自动同步定稿：切到全自动后资产补齐才会自动同步，现在可以点「手动同步资产」。'`
4. ui/pet_ui_voice.py 第 1050 行：
   原：`        self.notice = '云朵框已打开：三虎问的是这一页该做的事，点「确认」它就去办'`
   新：`        self.notice = '云朵框已打开：三虎问的是这一页该做的事，在回复框按回车它就去办'`
5. ui/pet_ui_stages.py 第 463 行（文档串）：
   原：`        """「导出交付」：把用户带到「质检与交付」页——导出按钮在那儿，三虎不代按。"""`
   新：`        """「导出交付」：把用户带到「质检与交付」页——制作入口在那儿，三虎不代按。"""`
6. ui/pet_ui_stages.py 第 465 行：
   原：`        self.notice = '交付导出在「质检与交付」页：按「导出」就出清单（这一步三虎不代按）'`
   新：`        self.notice = '交付在「质检与交付」页：点「手动制作交付」开始；各平台版本在「后期剪辑」页导出（这一步三虎不代按）'`
7. ui/pet_ui_stages.py 第 559 行：
   原：`                self.notice = '「%s」这一阶段的 SKILL 都被您取消勾选了——先到阶段配置里勾上再说。' % stage`
   新：`                self.notice = '「%s」这一阶段的 SKILL 都被您取消勾选了——先在底部输入框的「技能」里勾上再说。' % pet_bus.STAGE_NAMES.get(stage, stage)`
8. orchestrator/stage_exec.py 第 139 行：
   原：`        text = '「%s」未勾选 SKILL：请先在阶段配置里勾选，或点「恢复默认」。' % stage_flow.stage_name(stage)`
   新：`        text = '「%s」未勾选 SKILL：请先在底部输入框的「技能」里勾选这一步要用的技能。' % stage_flow.stage_name(stage)`
9. ui/pet_ui_support.py 第 234 行（PAGE_ASKS 第 7 项）：
   原：`    ('要不要我把拍板的那几份分镜采用掉，往后推一步？', '执行选中'),`
   新：`    ('要不要我把已采用的分镜同步资产、生成定稿？', '执行选中'),`
10. ui/pet_agent_rules.py 第 101 行（VERDICTS 的 auth 一项）：
    原：`    'auth': ('notify', '接口密钥无效或没配：检查 .env 里的 Key'),`
    新：`    'auth': ('notify', '接口密钥无效或没配：到「模型管理」里检查密钥；用 .env 配置的，检查里面的 Key'),`

另：tests/test_pet_agent_error_wiring.py 第 69 行断言与第 10 处同步改（见开头三问（二））。

## 命令与结果

| 命令 | 实测结果 |
| --- | --- |
| `git -c core.quotepath=false status --porcelain` | 退出码 0，无输出 |
| `git log -1 --format=%h` | 退出码 0，输出 8c6910f7 |
| `git rev-parse --abbrev-ref HEAD` | 退出码 0，输出 codex/sanhu-fix-rules |
| `run_selftests.py -k sanhu_mode stage_flow stage_command_contract manual_plan pet_agent`（改前） | 退出码 1，共 224 条、121.5 秒，红 5 条：SanhuCopyWordingTests 4 条（off 文案、定稿页问句、已删按钮名、未勾 SKILL 句）＋ test_verdicts_carry_only_action_and_hint |
| `git -c core.quotepath=false diff --numstat` | 9 个文件：desktop_automation_tick.py 3/3，pet_ui_voice.py 1/1，pet_ui_stages.py 3/3，pet_ui_support.py 1/1，stage_exec.py 1/1，pet_agent_rules.py 1/1，test_pet_agent_error_wiring.py 1/1，test_sanhu_mode.py 97/0，test_stage_flow.py 42/0 |
| `run_selftests.py -k sanhu_mode stage_flow stage_command_contract manual_plan pet_agent`（改后） | 退出码 0，共 224 条、237.0 秒，ALL TESTS PASSED |
| `run_selftests.py -k pet_ui ui_edges_autopilot` | 退出码 1，共 647 条、113.9 秒，红 2 条均为已知 FFmpeg 缺失（FrameBatchSeamTests 两条） |
| `run_selftests.py -k copy_rules static_names` | 退出码 0，共 26 条、10.4 秒，ALL TESTS PASSED |
| `smoke_test.py --architecture` | 退出码 0，Ran 700 tests in 449.126s，OK，失败集合为空 |
| `scripts\dev.py claim` | 退出码 0，领到 R4126 |

## 如实说明

- ui/pet_ui_stages.py 与 ui/pet_ui_voice.py 改前改后行数相同（numstat 增删相等：3/3 与 1/1），仍各为 1202 行与 1201 行，未触行数上限门禁。
- 定稿状态那条用例（test_auto_final_off_copy_points_to_manual_sync）照卡面宿主拼法一次跑通：_AutomationHost 四个 mixin＋root/win=None/studio/status/worker=None/page_index=None/pet/asset_base()，没有补额外假属性，没有退回读源码断言；pet.run_skill 行为断言也实测跑通，未退回。
- 守卫表没有按实际改过：写卡窗口登记的 11 项文件与按钮名本轮逐一 grep 核实，全部命中，改产品前这条守卫就是绿的。
- 没有在真实界面上试过，没有连模型。
- 其他与卡面不一致的地方：无。

## 未覆盖项

- 真实界面和真实模型没试。
- 全量自测（--all --safe）没跑。
- 默认冒烟（smoke_test.py 不带参数）没单独跑。
- 结构检查（governance 下的脚本）由写卡窗口另跑。
