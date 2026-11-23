# R4188 结果：UX-SLASH-HINT 输入 / 后悬停或键盘选中候选即在同行右侧显示用途卡
<!-- round-evidence: {"commit_base": "e5588314", "credential_hits": 0, "evidence_sha256": "ec2b8f916d45f029", "exit": 0, "failed": 0, "passed": 70, "round": 4188, "tests": "run_selftests.py -k skill_command shared_input_ui"} -->

## 开头三问

- （一）本轮属于哪种类型：功能轮（§3.1）。卡 UX-SLASH-HINT，波次 W2，车道 `codex/ux-slash-hint`，基准 `12ce348b`。目标：输入 `/` 后，悬停技能／子引擎候选的任意区域（名称、类别徽标、行留白），在类别徽标右侧同一行看到准确用途；键盘上下选择同样能查看。只消费已取得注册对象的 `description`，不新增文件扫描或模型调用，保留项目＞用户＞内置优先级与既有排序／过滤／插入行为；说明不抢焦点、不 grab、不进发送正文。
- （二）测试跑了吗、三个基线：跑了，先红后绿。定向 `run_selftests.py -k skill_command shared_input_ui` 改前 13 条红（7 条 `CompletionHintTests` KeyError 'hint' ＋ 6 条 `CandidateHintCardTests` 无卡），改后「共 70 条用例；0 个文件有红」「ALL TESTS PASSED」退出码 0。架构门禁 `smoke_test.py --architecture` 当轮实际总数 700，改前首跑 2 条红（均为本卡加行触发的行数棘轮），修完后「Ran 700 tests」「OK」退出码 0，失败集合为空。`--affected` 冒烟「通过：10 项 失败：0 项」。默认冒烟基线 8/8 未单独跑（卡面禁跑默认冒烟，`--affected` 已含本轮检查项 10/10）；全量回归未跑（功能分支、卡面未要求，欠账以 `full-safe-receipts.json` 为权威，本轮未读）。
- （三）欠账少了吗：没有新增欠账。REQ-S01-106 由 ⬜ 转 ✅ 并补真实测试锚点；REQ-S01-107 及 §13 其余目标（输入法／撤销／自适应／完整候选滚达／防重）仍 ⬜ 未动，属既有欠账，本轮不扩大。

## 改了哪些文件（文件:行号）

- `程序/domain/skill_command.py`：新增 `_item_description`（171–180 行）读对象属性／字典 `description` 键、去首尾空白保留内部换行；`completion_entries`（182 行起）条目增 `hint`，skill 直接读描述、engine 按名回查同一份注册快照（`desc_exact`/`desc_fold`，重名取第一条）、阶段别名空串；排序／过滤／去重／插入体未动。
- `程序/ui/desktop_shared_menus.py`：`CandidatePopup` 撤逐行 `Tooltip`（删 import）；整行 `<Enter>`→`_hover`（377 行）跟随高亮＋`_show_card`（382 行）、`<Leave>`→宿主延迟收；`_show_card` 把 `hint`（无则「暂无用途说明」）放进 item 的 `description` 交宿主 `_show_skill_card`；`move`（435 行）与 `refresh`（289/310 行 `had_card`）按高亮同步说明；`close`（537 行）收卡取消计时器；`__init__` 绑宿主 `<Destroy>`（282 行）→`_on_host_destroy`（394 行）＋`teardown`（541 行）销毁载体。
- `程序/desktop_shared_input.py`：`_show_skill_card`（771 行）签名不变，卡改 `overrideredirect(True)`（783 行）无边框，移除随之多余的边框偏差两步贴正；docstring 一行补「候选行」。其余未动。
- `程序/tests/test_skill_command.py`：新增 `CompletionHintTests`（176 行起，6 条：对象／字典、包子引擎、空描述、多行、重名 skill／engine 优先级）。
- `程序/tests/test_shared_input_ui.py`：新增 `CandidateHintCardTests`（668 行起，6 条：整行单卡右侧同行、键盘同步、进卡不闪＋延迟收、采纳/Esc/切页/销毁回收、翻左钳制、说明不进正文＋Enter 只采纳）；顶部补 `import time`。
- `程序/docs/stages/S01_剧本准备.md`：REQ-S01-106 ⬜→✅（R4188）、DES-S01-106 落实现、接口表／交互节同步、测试锚定表拆出 106 真实锚点（107 仍 ⬜）。
- `程序/docs/specs/08_对话式交互与输出排版.md`：§13 用途数据／触发／放置三行 ⬜→✅、索引行与节标题转 🟡、验证待办区分已实测与仍待。
- `程序/tasks_round/tasks_round_4188_result.md`：本文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k skill_command shared_input_ui`（改前，产品未改） | 退出码 1；「共 70 条用例，16.5 秒；2 个文件有红」，13 条红 |
| 同上（改后） | 退出码 0；「共 70 条用例；0 个文件有红」「ALL TESTS PASSED」 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --affected skill_command desktop_shared_input desktop_shared_menus` | 退出码 0；「ALL TESTS PASSED」「✅ 门禁…0 个文件有红」「通过：10 项 失败：0 项」 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 退出码 0；「Ran 700 tests in 260.727s」「OK」「✅ 架构治理测试」 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 退出码 0，轮次 4188 |

先红原文（改前定向，各留一条）：

```
===== test_object_and_dict_skills_carry_description (test_skill_command.CompletionHintTests...) =====
    self.assertEqual(by_name['obj-skill']['hint'], '对象用途')
KeyError: 'hint'

===== test_hover_name_badge_and_blank_show_single_side_card (test_shared_input_ui.CandidateHintCardTests...) =====
    self.assertIsNotNone(card, '悬停名称应出现用途卡')
AssertionError: unexpectedly None : 悬停名称应出现用途卡
```

架构门禁中途红（本卡加行触发，修完后重跑绿）：

```
FAIL: test_class_size_does_not_grow ... 'desktop_shared_input.py::SharedStageInput 607 行 > 上限 600'
FAIL: test_no_module_exceeds_its_cap ... 'desktop_shared_input.py: 1017 行 > 上限 1000'
```

## 按推荐执行的待确认项

- 说明卡改无边框（`overrideredirect(True)`）并移除边框偏差两步贴正：这是复用函数 `_show_skill_card` 的几何修正，同时作用于 ✦ 技能面板悬停卡（REQ-S01-91）。起因是带标题栏的 Toplevel 被 Windows 强加最小窗宽（实测 reqwidth 64 → 实际宽 120），翻左／钳位按 reqwidth 计算会压住行。改后实测宽＝请求宽，翻转／钳制正确；技能面板卡随之去掉标题栏、更贴近被动提示卡。既有 91/92 断言未改且保持绿。若要求技能面板卡保留原装饰外观，需另行拆分候选卡与面板卡的建窗路径（超出本卡范围）。
- 「暂无用途说明」占位由候选侧写入 item 的 `description` 交给复用函数，而非给 `_show_skill_card` 增参数——保持复用函数签名与技能面板旧文案「（该技能没有填写 description）」不变。

## 如实说明

- （一）`desktop_shared_input.py` 原为 1000 行整、`SharedStageInput` 逼近 600 行棘轮上限，本卡新增逻辑会顶破。为不抬高登记值：销毁回收逻辑放进 `CandidatePopup`（`desktop_shared_menus.py`）而非宿主新方法；「暂无用途说明」走 item 描述而非新参数；无边框后移除多余的 dx/dy 贴正。最终该文件 996 行、类行数回到上限内，两条棘轮转绿。未改任何门禁阈值／基线／登记表。
- （二）`--affected` 首跑退出码 1 但输出在「[隐藏桌面]…」处截断、无任何用例红原文；紧接原样重跑即全绿（0 个文件有红）。判断为跨树 GUI 令牌 contention 所致的偶发，非测试红；最终态以重跑绿为准。
- （三）翻左／钳制测试用注入显示器矩形（`mock.patch monitor_bounds`，与 R3031 既有副屏测试同法），非双屏硬件实测。
- （四）被拒绝的命令：无。未使用 git add／commit／push／merge／stash／checkout 等禁止命令；未跑卡面之外的 Python 命令。

## 未覆盖项

- 未跑默认冒烟（单独）、未跑全量自测（卡面只要求上述三条验收命令）。
- 双屏／缩放硬件实测、Windows 拼音输入法、候选滚达、粘贴／撤销、矮窗口自适应、防重与失败恢复均属 REQ-S01-107，未实现未验证。
- 未在真实桌面端到端鼠标悬停／键盘操作；几何与生命周期经真 Tk 隐藏桌面合成事件断言覆盖。
- 「换项目」关闭路径经 `set_stage`／`close_completion` 间接覆盖，未单独构造换项目事件断言。