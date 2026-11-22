# R4115 结果：SANHU-FIX-5 三虎聊天规则与模型说明补全
<!-- round-evidence: {"commit_base": "24be2ed3", "credential_hits": 0, "evidence_sha256": "eeb13c809054bfff", "exit": 0, "failed": 0, "passed": 154, "round": 4115, "tests": "run_selftests.py -k pet_agent pet_llm"} -->

## 开头三问

（一）本轮属于哪种类型：修复轮。任务卡 W6-SANHU-FIX-5（写卡：编码预备窗口；依据三虎只读审查报告的 S-08、S-09、S-13），车道 codex/sanhu-fix-rules，基准 24be2ed3。

（二）测试跑了吗、三个基线：

- 点名测试 `run_selftests.py -k pet_agent pet_llm token_saver`：改前 241 条用例、3 个文件有红——test_pet_agent 11 条（全部出自本轮新增的 StageAndLevelRuleTests：13 阶段切页 4 条子用例红、档位 2 条子用例红、LEVEL_ASK 1 条、生成分镜预演 1 条、rule_reply 短名 3 条子用例红）、test_pet_llm 1 条（新增 SYSTEM_PREFIX 阶段名单用例）、test_pet_agent_error_wiring 1 条（改了断言的 test_verdicts）；改后 241 条用例 0 红，ALL TESTS PASSED。
- 架构门禁 `smoke_test.py --architecture`：实测 Ran 700 tests，OK，失败集合为空。
- 默认冒烟没单独跑；全量自测没跑；pet_ui 这组没跑（留给验收窗口）。
- 新增 6 条用例（test_pet_agent.py 新类 5 条、test_pet_llm.py 1 条）；改了 1 处已有断言——test_pet_agent_error_wiring.py 的 test_verdicts_carry_only_action_and_hint 中 unknown 那行：原断言 `'没认出来：先按「重试失败项」，要细节看「查看待确认详情」'`，新断言 `'没认出来：先按「重试失败项」，要细节看右键菜单里的「待确认项」'`；理由：右键菜单里那一项现在叫「待确认项」，句子要对上界面。没有删除或改弱别的用例。

（三）欠账少了吗：少了——三虎不认「只提醒」、切页规则缺 4 个阶段（分镜预演/剧本结构/连贯性/视频生成页）、给模型的阶段名单缺 3 个（SYSTEM_PREFIX 只列 10 个）、两句固定文案对不上现在的界面（UNKNOWN_REPLY 的「点页面上的按钮」、VERDICTS unknown 的「查看待确认详情」），这几条已修；SHORT_NAMES 补齐 13 个短名；「只提示」作为别名仍认成 hint。未新增欠账。

## 改了哪些文件

- `ui/pet_agent_rules.py`：level 规则加「只提醒」；在 generate 规则前插三条 goto（分镜预演→animatic、剧本结构→script_structure、连贯性→continuity）；在 generate 规则后插一条 goto（视频生成|视频页→video）；UNKNOWN_REPLY 改句并新增 LEVEL_ASK；VERDICTS unknown 改句。
- `pet_agent.py`：导入加 LEVEL_ASK；SHORT_NAMES 补 script_structure/animatic/continuity 三个短名；level_in 末行加别名「只提示」→hint；match_rule 命中 level 但认不出档位时回 LEVEL_ASK。四处同一行原地改，行数不变。
- `infra/pet_llm.py`：SYSTEM_PREFIX 的 stage 名单补全到 pet_bus.STAGES 的 13 个。
- `tests/test_pet_agent.py`：文件末尾新增 StageAndLevelRuleTests（5 条表驱动用例）。
- `tests/test_pet_llm.py`：加 `import pet_bus`，PersonaTests 末尾新增 1 条 SYSTEM_PREFIX 阶段名单用例。
- `tests/test_pet_agent_error_wiring.py`：test_verdicts 里 unknown 那行断言换成新句子。
- 本结果文件。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git -c core.quotepath=false status --porcelain` | 0 | 无输出（工作树干净） |
| `git log -1 --format=%h` | 0 | 24be2ed3 |
| `git rev-parse --abbrev-ref HEAD` | 0 | codex/sanhu-fix-rules |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_agent pet_llm token_saver`（改前） | 1 | 共 241 条用例，129.6 秒；3 个文件有红：test_pet_agent 11、test_pet_llm 1、test_pet_agent_error_wiring 1（均为本轮新增/改断言的用例） |
| `git -c core.quotepath=false diff --numstat` | 0 | 6 个文件：pet_llm.py 1/1、pet_agent.py 4/4、test_pet_agent.py 51/0、test_pet_agent_error_wiring.py 1/1、test_pet_llm.py 4/0、pet_agent_rules.py 8/3 |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_agent pet_llm token_saver`（改后） | 0 | 共 241 条用例，3.7 秒；0 个文件有红；ALL TESTS PASSED；实际跳过 0 条 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | Ran 700 tests in 279.7s，OK |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 领到轮次号 4115 |

## 如实说明

- pet_agent.py 改前改后行数相同（numstat 4 增 4 删，仍为 1046 行，等于行数上限登记值）。
- ui/pet_agent_rules.py 多了 5 行（98→103，numstat 8 增 3 删）。
- VERDICTS 的 auth 那一句没动（归别的卡）。
- 「去质检与交付」命中的仍是前面的「交付→导出」规则（intent=export、stage=delivery），测试只断言阶段。
- 「生成分镜」「生成视频」「预演」「剧本」的旧命中不变，已在回归断言里钉住。
- 没有在真实界面上试过，没有连模型。
- 其他与卡面不一致的地方：无。

## 未覆盖项

- pet_ui 这组回归没跑（留给验收窗口）。
- 真实界面和真实模型没试。
- 全量自测没跑。
- 默认冒烟没单独跑。
