# R1704 修复轮：清掉 `test_pet_ui` 回复框用例那条临时目录清理偶发红（只改测试）

> 执行者：opencode flash。只改测试文件、跑测试；**未提交 git、未改 `project_status.md`、未领轮次**（轮次 1704 由 Claude 领取，验收与提交由 Claude 做）。
> 任务书约束：只写测试、不动任何既有断言、不加 `ignore_cleanup_errors`、不吞异常、不加 skip、等待必须有界；若证据指向生产代码则停下交证据。

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮。改动**全部落在 `程序\tests\test_pet_ui.py` 一个测试文件**（+25 行 / -0 行），`程序\*.py` 生产源码一行未改，故按任务书「验证」第 3 条**不跑 `smoke_test.py --architecture`**，也**不跑 `run_selftests.py --all --safe`**。
2. **测试跑了吗？三个基线过了吗？** 过了。默认冒烟 `smoke_test.py` **通过 8 / 失败 0**（退出码 0）；定向 `run_selftests.py -k test_pet_ui` → **ALL TESTS PASSED**（599 条用例，约 52 秒；0 个文件有错；退出码 0）。目标偶发红的修前/修后数字见 C。
3. **project_status.md 的欠账少了吗？** 未减少。本轮只改测试、不改生产源码，按 §5「改过源码的轮次」口径不新增全量欠账；欠账计数归属由 Claude 验收时裁定（我未写状态页）。

## A 根因

**一句话根因**：`cloud.submit()` 只是把这句话交给**后台守护线程**去想；这句话没命中 `pet_agent` 的规则表/技能表时会**真的调一次模型**，而模型层会把一次诊断事件**写进 `<项目>/model_diagnostics/`**——`<项目>` 正是 `setUp` 里那份 `TemporaryDirectory`。用例体不等后台那句落地，`tearDown` 的 `TemporaryDirectory.cleanup()` 就去删这个目录，撞上仍在写入/仍开着的句柄 → `PermissionError [WinError 32]`（另一进程正使用此文件）或 `OSError [WinError 145]`（目录不是空的）。**这是测试收尾时序问题，不是生产代码缺陷**（诊断写入本身是既有正确行为，见证据 3）。

**证据**

1. **本用例确实会触发那次写入，且写入目录就是临时项目目录。** 机制探针 `probe_flk_mech.py`（把 `model_diagnostics.record` 包一层只做计数，不改被测文件）跑 `ReplyBoxTests.test_the_reply_box_sends_what_the_user_typed`：
   - `RECORD_CALLS=1`，`LAST_PATH=C:\Users\...\Temp\tmpXXXXXX\p` → 恰好一次诊断写入，folder 就是 `<tmp>\p`。
   （对照：同类的 `' 查一下进度 '` 会命中 `pet_agent.RULES` 的 `(进度|…)`，不进模型调用；本用例发的是 `' 按你这句办 '`，两个表都不命中，必进模型调用。）
2. **收尾里没有任何一环等这句回复。** `PetTestCase.setUp` 注册顺序为 `setattr(AUTO)` → `tmp.cleanup` → `pet.stop` → `win.destroy`；`addCleanup` 后进先出，实际执行顺序 `win.destroy` → `pet.stop` → `tmp.cleanup` → `AUTO` 还原。`pet.stop` 不收这句仍在跑的后台回复线程，于是 `tmp.cleanup` 与后台写入之间**没有任何同步**。
3. **生产代码侧正确**：`model_diagnostics.record()`（`model_diagnostics.py:71`）经 `agent.core.save` 原子落盘，是既有的正常行为；`pet_llm._record_diagnostic` 的 `record(self.project, …)` 用注入的项目路径。改的是「测试什么时候收工」，不是「要不要写诊断」，故**未动生产代码**（若为测试方便去改生产侧写入时机，属越权）。
4. **本轮开工时的修前自然复现**（未动任何代码）：`ReplyBoxTests` 连跑 **30 次 → 23 次红**，红**全部**落在 `test_the_reply_box_sends_what_the_user_typed`，异常落 `...\Temp\tmpXXXX\p\model_diagnostics` 与 `...\p`，形态为 `WinError 32` 与 `WinError 145`。
5. **确定性机制验证**（把「还在往临时目录写」稳定摆到清理期间，见 C）：修前 **RED `WinError 32`**，修后 **GREEN**。

## B 改动（唯一文件 `程序\tests\test_pet_ui.py`，+25 行 / -0 行）

1. **`PetTestCase.wait_for_the_reply(self, cloud, timeout=5.0)`（`:158`，新增 19 行）** —— 一个收尾口辅助方法：
   ```python
   def wait_for_the_reply(self, cloud, timeout=5.0):
       """等后台那句回完再收工（用 `addCleanup` 挂在 submit 的用例上）。
       ...（说明竞争与后进先出为什么排在最前）..."""
       if cloud is None:
           return
       deadline = time.time() + timeout
       while time.time() < deadline and cloud.busy:
           cloud.drain()
           time.sleep(0.01)
       if cloud.busy:
           self.fail('后台那句 %.0f 秒内没回完：临时目录还在被它写，不能就这样收工' % timeout)
   ```
   - 等待**有界**（5.0 s，与既有的 `test_the_reply_box_is_locked_while_the_pet_is_thinking` 同一上限）；
   - 超时**不静默吞**：`self.fail(...)` 让用例**响亮地红**并说明原因；
   - 无 `ignore_cleanup_errors`、无 `except: pass`、无 skip。
2. **6 处 `self.addCleanup(self.wait_for_the_reply, cloud)`**（`cloud.show(...)` 之后、`cloud.submit()` 之前）：
   - `ReplyBoxTests.test_the_reply_box_sends_what_the_user_typed`（`:3954`，本轮点名的这条）
   - `ReplyBoxTests.test_an_empty_reply_box_falls_back_to_what_the_pet_asked`（`:3963`）
   - `ConfirmDoesTheTaskTests.test_an_empty_confirm_runs_the_page_task`（`:4030`）
   - `CloudTests.test_a_confirm_without_a_pending_task_does_the_page_task`（`:2089`）
   - `CloudTests.test_typing_and_answering_push_the_auto_close_back`（`:2190`）
   - `RecordScopeTests.test_the_confirmed_task_is_still_recorded`（`:5846`）
   这 6 条的共性是「`submit()` 之后不等后台回复就收工」，都踩同一个竞争窗口；本轮一并挂上。

`addCleanup` 后进先出 ⇒ 本条**先于** `win.destroy` / `pet.stop` / `tmp.cleanup` 执行：窗口还活着、后台也回完了，才轮到删临时目录。未动 `skills/`、`AGENTS.md`、`architecture.md`、`project_status.md`、`docs/`，未新增 `.bak_*`，未在 `程序\` 根留临时脚本（探针都在 `工作流任务\probe_flk\`）。

## C 验证（命令与实测数字）

| 命令 / 口径 | 修前 | 修后 |
| --- | --- | --- |
| `ReplyBoxTests` <br>（每轮一个进程）**连跑 30 次** | **23/30 红**（本轮开工实测；红全在 `test_the_reply_box_sends_what_the_user_typed`；`WinError 32`/`145`） | **30/30 绿** |
| **确定性机制验证**（`probe_flk_window.py`：把 `record` 包一层，在 `<tmp>\p\model_diagnostics` 真实建文件并握句柄 1.0 s，模拟「清理时后台还在写」） | **RED `{'32': 1}`**（`PermissionError [WinError 32]`） | **GREEN** |
| 本轮**后期**同口径自然复现（`ReplyBoxTests` 每轮一进程 ×30；再 8 路并行 ×80） | 0/30、0/80（偶发，本轮后期未再自然触发；见 D-2） | 0/30 |
| 单例隔离（`probe_flk_before.py`，每例 20 次，运行期摘掉收尾口） | `test_the_reply_box_sends_what_the_user_typed` **1/20 红**（`WinError 32`）；其余 0/20 | 0/20（每例） |
| `run_selftests.py -k test_pet_ui`（跑 1 次） | 未运行 | **ALL TESTS PASSED**；599 条用例，约 52 秒；0 个文件有错；退出码 0 |
| `smoke_test.py` | — | **通过 8 / 失败 0**；退出码 0 |
| `smoke_test.py --architecture` | 未运行 | **未运行**（未改生产模块，按任务书不升级） |
| `run_selftests.py --all --safe` | 未运行 | **未运行**（任务书明令不跑） |

补充：
- 机制验证为什么这么设计：该竞争要求「后台写入」正好压在 `rmtree` 期间，窗口只有毫秒级，自然复现率随机器负载与模型调用快慢剧烈波动（见 D-2）。`probe_flk_window.py` 用**真实地在临时项目目录里建文件并握句柄**把该窗口稳定摆到清理期间，得到的**就是本轮记录的同一种 `WinError 32`**，修前红、修后绿，直接证明「收尾口先等后台回完」消除了该触发条件，未改被测文件、未改生产代码。

### 断言未动

**没有改动、弱化或删除任何既有断言，没有新增任何 skip，没有 `ignore_cleanup_errors`，没有吞异常。** 本轮改动只有两类：(1) 新增一个辅助方法 `wait_for_the_reply`（新代码，不涉既有断言）；(2) 6 处 `addCleanup(self.wait_for_the_reply, cloud)` 的**收尾等待**。目标用例修前 23/30 红 → 修后 30/30 绿，其余用例保持绿。

## D 留给 Claude 裁决

1. **6 处收尾口要不要全留。** `test_the_reply_box_sends_what_the_user_typed` 是任务书点名的那条；另 5 条是同一竞争窗口下的同类（`submit()` 后不等回复就收工），本轮一并挂上。若你认为应只动点名那一条，删掉其余 5 行即可（每行独立、无耦合）。
2. **「修前自然复现率」变化的如实记录。** 本轮**开工时**实测修前 `ReplyBoxTests` **23/30 红**；本轮**后期**用同口径（含 8 路并行 80 次）复测，自然复现率降到 **0**。该偶发的触发依赖机器负载与模型调用时序，同一时段另有并行泳道改了 `ui_theme.py`/`ui_tokens.py`/`ui_widgets.py`（见下条），整机负载与调用时序都变了。为不让结论悬空，我把修前/修后差异固定成了 C 表的**机制验证**（真实建文件握句柄 → 修前 `WinError 32`、修后绿）。**请裁定这种「历史自然复现 + 确定性机制验证」的证据形态是否够，或要我换/补别的复现口径。**
3. **范围外：同树并行的 UI token 轮把 `test_the_style_paints_on_the_accent_colour` 打红了。** 现在它单跑 **24/30 红**、8 路并行 **80/80 红**，错误是 `test_pet_ui.py:4013` 断言 `str(style.configure('Send.TButton','foreground')) == 'white'`，实得 `'#FFFFFF'`。根因是**并行的 UI token 轮改了 `ui_theme.py`/`ui_tokens.py`/`ui_widgets.py`/`design_tokens.md`（另一泳道未提交的改动）**，与本轮测试收尾修复无关，**我没碰它**（不在授权范围，且属别人的契约变更）。**注意**：你验收时若 `-k test_pet_ui` 偶发红，先看这条——它现在比本轮那条偶发红更常红。
4. **超时上限与跨树争用。** 等待上限 5.0 s 与既有 `test_the_reply_box_is_locked_while_the_pet_is_thinking` 一致；若在多泳道 GUI 争用下偶发超时，收尾口会 `self.fail` 得响亮（不静默），复跑即可；如果你希望上限调大，告诉我数字。

## E 提交

**未提交，由 Claude 验收后提交。** 我未动 git 状态（未 `add`/`commit`/`stash`/`checkout`）、未改 `project_status.md`、未领轮次。改动文件（`git status --porcelain` 应显示为已修改）：
- `程序\tests\test_pet_ui.py`
