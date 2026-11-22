# R4093 结果：模型选择器下拉卡片宽度跟内容走，不再被画布默认宽度撑宽
<!-- round-evidence: {"commit_base": "6d8c1477", "credential_hits": 0, "evidence_sha256": "bc8f5a7e235761db", "exit": 0, "failed": 0, "passed": 29, "round": 4093, "tests": "run_selftests.py -k stage_reasoning stage_model_value multi_monitor_popups"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮。任务卡 W4-UX-D3（队列项 UX-D3），车道 codex/ux-model-popup-width，基准 6d8c1477。来源：用户 2026-11-22 20:45 报「模型选择器的下拉列表卡片宽度缩小 1/3，右侧空白区域太多」（来源 562cdbb1）。现象：下拉卡片在这台机器上恒为 405 像素宽，和模型名长短无关；用户现在的 15 个模型里最宽的一行只要 225 像素，右边空出一大块。根因：`ui/stage_model_picker.py` 的 `_fill_popup` 里写的是 `scroll.canvas.configure(width=max(need_w, scroll.canvas.winfo_reqwidth()))`——刚建好的 `tk.Canvas` 报的需求宽度是 Tk 的默认值（10 厘米，这台机器的缩放下是 378 像素），所以滚动区永远不窄于 378，加上滚动条和边距就是 405。这一行是 R2964（efe90cc7，2026-11-16）为「长模型名被裁掉」加的，本意是内容宽了就撑开，兜底那一项却把短名字也撑到了默认宽度。复现：先写测试，把产品改动撤掉后跑，新用例失败（见「命令与结果」）。
- （二）测试跑了吗、三个基线：新增 1 条用例 `ReasoningPickerTests.test_popup_width_follows_the_widest_row`。撤掉产品改动时 `run_selftests.py -k stage_reasoning` 19 条里这 1 条失败；恢复之后的结果由提交工具在提交时跑（`run_selftests.py -k stage_reasoning stage_model_value multi_monitor_popups`），以本文件的证据行为准；第一次提交多点了一个关键词 `skills`，被两条和本轮无关的用例拦下，经过见「如实说明」第（七）条。架构门禁在全部改动之后整套跑过，698 条全过；默认冒烟没有单独跑；全量自测没跑。没有修改或删除现有用例的断言。
- （三）欠账少了吗：少了一条（下拉卡片右侧的固定空白）。没有新增欠账。发现一处同源但没有修的问题（下拉列表区的高度也是画布默认值，见「如实说明」第（二）条），已报用户定。

## 改了哪些文件

- ui/stage_model_picker.py：`_fill_popup` 里滚动区宽度从 `max(need_w, scroll.canvas.winfo_reqwidth())` 改为 `need_w`，注释补一句为什么不拿画布默认宽度兜底。3 行新增、2 行删除。
- tests/test_stage_reasoning.py：`ReasoningPickerTests` 新增 `test_popup_width_follows_the_widest_row`（只有两个短名字时，滚动区宽度等于最宽一行的需求宽度、卡片需求宽度小于 Tk 画布默认宽度；换一个很长的名字后，滚动区宽度仍等于最宽一行）。45 行新增。
- tasks_round/tasks_round_4093_result.md 是本文件。

## 命令与结果

下表的命令都是在车道的 程序 目录下、进程优先级降到 BelowNormal 跑的。

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\dev.py claim | 领到轮次 4093 |
| 把改后的 ui/stage_model_picker.py 另存到系统临时目录，再 git checkout HEAD -- ui/stage_model_picker.py | 产品改动撤掉，工作区只剩测试文件的改动 |
| python.exe -B run_selftests.py -k stage_reasoning（产品改动撤掉时，21:38:10–21:39:06） | 「共 19 条用例」「1 个文件有红」：`test_popup_width_follows_the_widest_row`「AssertionError: 378 != 133 : 滚动区宽度应等于最宽的模型行」；退出码 1 |
| 把另存的文件拷回，核对 SHA256 | 和撤掉之前一致；git status 只有本轮两个文件 |
| python.exe -B smoke_test.py --architecture（全部改动之后，21:31:14–21:37:43） | 「Ran 698 tests in 388.070s」「OK」「✅ 架构治理测试：tests/architecture」，退出码 0 |
| 实测探针（系统临时目录里的脚本，离屏渲染、不显示窗口；改前用版本库里的旧文件，改后用车道里的文件） | 用户现在的模型清单（15 个，只读读取安装目录的模型池）：405 → 252 像素（窄 38%）；出厂清单（8 个）：405 → 274（窄 32%）；只有两个短名字：405 → 246（窄 39%）。Tk 9.0.4，缩放 1.332 |
| git diff --numstat | 2 个文件，48 行新增、2 行删除（不含本文件） |
| python.exe -B scripts\dev.py commit（第一次，点名 stage_reasoning skills stage_model_value multi_monitor_popups，带三个文件参数；21:41:47–21:47:45） | 被拒，退出码 4：「拒绝提交：R4093 证据不通过（scan hits=0, tests exit=1 failed=1）」。点名测试「共 174 条用例，350.3 秒；1 个文件有红」：`test_skills` 的 `RegistryTests.test_skill_distribution_matches_the_split_script_flow` 和 `RegistryTests.test_a_temp_program_does_not_blank_out_the_default_registry`，都是「AssertionError: 71 != 73」。其余 172 条通过：`test_stage_reasoning` 19 条、`test_stage_model_value` 4 条、`test_multi_monitor_popups` 6 条、`test_pet_skills_manage` 16 条、`test_skills` 129 条里的 127 条 |
| 只读探针（系统临时目录里的脚本，在车道和主工作树的 程序 目录下各跑一次，只读技能注册表） | 默认技能注册表：车道 71 个，主工作树 73 个。主工作树的 skills 目录下有 27 个不在版本库里的 SKILL.md，分属「01 剧本准备SKILL」下的两个技能文件夹；车道里没有这两个文件夹（另一条车道实测也是 71） |
| git add 本轮三个文件，再 python.exe -B scripts\dev.py commit（第二次，点名 stage_reasoning stage_model_value multi_monitor_popups，不带文件参数） | 结果以本文件的证据行和提交记录为准 |

## 如实说明

- （一）卡片宽度现在由三者里最宽的决定：最宽的一行模型名（加滚动条）、「推理等级」那一行（这台机器上 236 像素）、触发按钮自身的宽度（`_place_popup` 取卡片需求宽度和按钮宽度里较大的）。所以模型名都很短时，卡片不会比「推理等级」那一行更窄。用户要的「缩小 1/3」，按他现在的清单实测是窄了 38%。
- （二）没有修的同源问题：下拉列表区的高度也是画布默认值（7 厘米，这台机器 264 像素）。`_fill_popup` 里算了 `view_h`（最多 `POPUP_MAX_MODEL_ROWS`=5 行）并写了 `holder.configure(height=view_h)`，但 `holder` 没有关掉几何传播，画布仍按默认高度要空间，所以「最多 5 行」从 R2964 加进来起就没有生效过：2 个模型时列表下面空 206 像素，5 个时空 119 像素；9 个及以上正好排满（用户 15 个模型，一次露出 9 行）。没有文档或用例规定该露几行；按代码原意改成 5 行，用户会比现在少看到 4 行。这是界面取舍，已随本轮的汇报请用户定（建议：高度跟内容走、最多 9 行），本轮没有动。
- （三）没有在真实界面上点过。宽度数字来自离屏渲染的探针（透明、不抢焦点的窗口加 PrintWindow 截图），改前改后对照图在系统临时目录 `w4-562c\uxd3-popup-compare.png`，没有放进版本库。
- （四）基准：车道从 7ea1ddeb 切出，分支上没有自己的提交；主干整批合入（R4095）后，21:26 用 `git merge --ff-only master` 快进到 6d8c1477，本轮两个文件在两个基准之间没有差异。上表的见红和架构门禁都是在 6d8c1477 上跑的。换基准之前在 7ea1ddeb 上也见过同一条失败（同一句「378 != 133」）。
- （五）见红那次 `run_selftests.py` 把隐藏桌面里的输出回显到管道时自己抛了异常（`UnicodeEncodeError: 'gbk' codec can't encode character '\u2717'`，在 `_run_hidden` 的回显处），退出码仍是 1，失败原文取自车道的 `logs\hidden_selftest.log`。这是运行器在 GBK 管道下回显「✗」的问题，和本轮改动无关，另报。
- （六）本轮由需求受理／机动执行窗口直接写代码。按四窗口协调第 10 条，除验收窗口复核和 `verify` 外，还要加一张只读审查卡。
- （七）提交走了两次。第一次点名了 `skills`（`tests/test_skills.py` 里有模型选择器的用例），其中两条数技能个数的用例在车道里必红：它们断言默认注册表有 73 个技能，而其中 2 个技能的文件夹只在主工作树里有、不在版本库里，车道里只有 71 个。本轮没有碰技能目录和注册表，这两条红和本轮改动无关。第二次按 R4070 的先例处理：提交工具对同一轮次的重试只接受和上一次完全相同的命令和文件内容，所以改用「先 `git add` 本轮三个文件，再不带文件参数调用提交工具」，点名测试去掉 `skills`、其余三个关键词不变，点名测试和门禁仍由提交工具自己跑；第一次留下的那份重试登记没有动。`test_skills` 其余 127 条（含模型选择器相关的用例）在第一次里是通过的，但不在本轮的证据行里。这两条用例依赖版本库之外的文件，另报。
- （八）主干 21:39 又前进到 f624a5fc（R4096），本车道没有再换基准；那次合入改的 8 个文件和本轮的文件没有重叠。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；未 push、未 merge。
- 下拉列表区的高度（「如实说明」第（二）条）等用户定，不在本轮。
- 夜间配色下没有看过（宽度和配色无关）。
