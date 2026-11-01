# R1730：需求锚定轮——REQ-S01-01 气泡式对话界面补真 Tk 锚点（BUBBLE）

执行者：opencode（派发任务，独立车道 `D:\漫剧制作助手\.wt\lane_bubble\程序`）
解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`

## 开头三问（AGENTS §7.3）

1. **本轮属于 §3 哪种类型？** 验证/基线轮（§3.10）：只补测试锚点、不改任何产品代码。派发执行方，不领号、不提交、不改 `project_status.md`。
2. **测试跑了吗、三个基线过了吗？**
   - 定向（任务书命令）：`run_selftests.py -k test_req_s01 test_idea_chat` → **通过（147 条用例 / 151.0 秒 / 0 个文件有红 / ALL TESTS PASSED）**。
   - 需求锚定门禁：`-m unittest tests.architecture.test_requirement_traceability` → **通过（Ran 4 tests / OK）**。
   - 默认冒烟 `smoke_test.py`、完整架构门禁、全量 `--all --safe`：**未运行**（任务书未要求；改动只在 `tests/`，分支不累计全量欠账）。
3. **`project_status.md` 的欠账少了吗？** 未改动该文件（执行方无权写）；本轮不新增也不减少欠账，无锚定基线需要删除（REQ-S01-01 早已 ✅ 且已有锚点，本次是追加第二条锚点）。

## 改动文件

- `tests/test_req_s01_anchors.py`：新增 `IdeaBubbleAnchorTests`（1 条真 Tk 用例）＋ 顶部 `import tkinter`、`import desktop_idea_chat`、复用夹具 `from tests.test_idea_chat import _Harness, idea_chat`、`from tests.test_ui_edges import make_minimal_project`、`from ui_tokens import COLORS`；模块 docstring 补一句说明。
- `tasks_round/tasks_round_pending_BUBBLE_result.md`：本文件。
- 产品代码：**未改**（`git status --porcelain` 仅 `程序/tests/test_req_s01_anchors.py` 一处 M）。

## 测试名

`tests.test_req_s01_anchors.IdeaBubbleAnchorTests.test_req_s01_01_idea_messages_render_as_bubbles_and_survive_restart`

docstring：`REQ-S01-01：创意对话按气泡渲染；销毁界面、用同一目录重建后仍按原顺序出现。`

步骤：临时项目里 `idea_chat.append(proj,'user',…)` ＋ `idea_chat.append(proj,'assistant',…)` → 建真 Desktop 窗口并读出气泡 → 断言容器/底色/对齐/宽度/文字完整 → `win.destroy()` 后用同一目录重建，再断言两只气泡按原顺序回来。

## 每条断言对应的代码契约（文件:行）

| 断言 | 契约（实际代码） |
| --- | --- |
| 两条消息各自是独立气泡容器：`bubble_0`、`bubble_1` 各有一段正文、互不重叠 | `desktop_idea_chat.py:600` `name='bubble_'+str(index)`；`:635` `box.insert('end',preview+'\n',name)` |
| 文字完整（预览＝全文） | `desktop_idea_chat.py:633-635`（`bubble_preview` 对短文本原样返回，`idea_chat_controller.collapse_preview` `:23-32`） |
| 用户气泡底色 `success_subtle`，模型气泡底色另取模型色且两者不同 | `desktop_idea_chat.py:606` `model_back,_ = self.model_chat_colors(...)`；`:608` `background=… COLORS['success_subtle'] if mine else model_back` |
| 用户贴右（左边距更大），模型贴左（左边距正好 `BUBBLE_GAP`） | `desktop_idea_chat.py:212-215` `return max(0,width-BUBBLE_GAP-body),BUBBLE_GAP`（user）／`BUBBLE_GAP,max(0,width-GAP-body)`（model）；`BUBBLE_GAP` 见 `:67` |
| 气泡正文宽度＝对话区实际宽度−左右边距，>0 且 ≤ 对话区宽度 | `bubble_margins` `desktop_idea_chat.py:208-211`（body 被 `BUBBLE_FLOOR`/`BUBBLE_MAX_RATIO` 封顶）；几何取 `box.winfo_width()` 与标签 `lmargin1`/`rmargin` |
| 用户气泡正文首像素在模型气泡右侧 | `add_bubble` 按 `mine` 写入的 `lmargin1`（`:610`）经 `<Configure>`→`refit_bubbles`（`desktop_writing_page.py:307`）落成实际像素，用 `box.bbox('bubble_N.first')` 量取 |
| 重启重建后按原顺序重现 | 持久化 `idea_transcript.append:227`／`load:211`；重绘 `desktop_idea_chat.show_conversation:670`（`:734` load，`:777-790` 按序分片 `add_bubble`） |

说明：用户/模型气泡的对齐写在**边距**（非 `justify`，两者的 `justify` 都是 `left`），底色是辅以区分的第二契约；断言按代码实际契约取这两样，未臆造。

## 自证（红）

方法：临时脚本把渲染函数 mock 成纯文本追加——`desktop_idea_chat.IdeaChatMixin.add_bubble = lambda …: box.insert('end', text+'\n')`（不建 `bubble_<序号>` 容器、不设底色/边距），再跑同一条用例。脚本放在 `C:\Users\LAIBIAO\AppData\Local\Temp\opencode\bubble_red_proof.py`，跑完已删除；车道里的产品代码保持原样，未落任何改动。

红的输出（原文摘录）：

```
FAIL: test_req_s01_01_idea_messages_render_as_bubbles_and_survive_restart
  (tests.test_req_s01_anchors.IdeaBubbleAnchorTests.test_req_s01_01_idea_messages_render_as_bubbles_and_survive_restart)
Traceback (most recent call last):
  File ".../程序/tests/test_req_s01_anchors.py", line 168, in test_req_s01_01_idea_messages_render_as_bubbles_and_survive_restart
    self.assert_rendered_bubbles(d.idea_log)
  File ".../程序/tests/test_req_s01_anchors.py", line 125, in assert_rendered_bubbles
    self.assertEqual(len(ranges), 2, name + ' 应为一段独立的气泡正文')
AssertionError: 0 != 2 : bubble_0 应为一段独立的气泡正文

Ran 1 test in 3.017s
FAILED (failures=1)
RED_PROOF_RESULT=RED
```

绿（真实代码，同一用例）：`ok` / `Ran 1 test in 5.431s` / `OK`。

## 实际计数

- `python -B run_selftests.py -k test_req_s01 test_idea_chat`
  → `共 147 条用例，151.0 秒；0 个文件有红`；`ALL TESTS PASSED`。
  → 其中 `test_req_s01_anchors 21.2 秒 / 3 条`（含新用例）；`test_idea_chat` 拆成 #1–#9 分片全部无红。
  → GUI 令牌：本车道独占，直接取得，**未出现 `[GUI_WAIT]`，未等待**（未触及任务书的 5 分钟上限）。
- `python -B -m unittest tests.architecture.test_requirement_traceability`
  → `Ran 4 tests in 3.423s`；`OK`（exit 0）。
- 备注：标准输出里 Tk 的 `error reading package index file … unknown encoding "cp1252"` 与偶发 `invalid command name "…poll"` 是本机 Tcl/Tk 环境噪声（stderr），不改变计数与结论。PowerShell 把任何写 stderr 的原生命令回显成 `Exited with code 1`（已用干净探针复核：`exit=0` 的命令同样被回显为 1），非测试失败。

## 需裁决事项

1. **测试文件分层归属**：按任务书要求把真 Tk 用例加进 `tests/test_req_s01_anchors.py`，因此该文件顶层出现 `tkinter`/`desktop_idea_chat` 导入，`run_selftests.gui_test_module`（`run_selftests.py:1023-1026`）会把**整个文件**判为 GUI 单元——原本无 Tk 的 REQ-S01-22／31 两条锚点今后也走 GUI 令牌。若希望二者分离（非 Tk 锚点不进 GUI 池），需裁决是否把 Tk 用例单列到新的 GUI 测试文件。
2. **夹具复用**：新用例继承 `tests/test_idea_chat.py` 的私有 `_Harness` 并复用其注入包装 `idea_chat`（含 `L3` 网关注入）。这满足任务书「可复用其中的夹具和窗口搭建方式」，但引入了跨测试文件的私有依赖；如需彻底解耦可改为在本文件内自建等价夹具（会重复约 30 行代码）。
3. **真几何断言要求窗口可见**：为量到真实像素宽度/首字坐标，用例内对窗口调用 `deiconify()`，测试期间会短暂出现一个可见窗口（`test_idea_chat.py` 中已有同类用例这样做）。若不接受可见窗口，可退化为只按 `bubble_margins`＋标签边距计算（仍真 Tk，但不是像素级 `bbox`）。

## §4.2 交付前自检

- 验收标准：任务书四步（写入两条消息、断言气泡容器＋对齐/底色＋宽度＋文字完整、重启重建、自证红）全部落实 → **通过**。
- 改动范围：仅 `tests/test_req_s01_anchors.py`（＋本结果文件）；产品代码零改动 → **通过**。
- 适用验证：定向与需求锚定门禁已跑并绿；`smoke_test.py`、完整架构门禁、全量回归**未运行**（如实记录）。
- 是否引入新问题：新用例自身绿、自证红成立；未改动产品代码，未新增 skip；跨文件私有夹具复用已列为待裁决项。

**结论：通过。**

[TASK_COMPLETE]

## 独立验收（Claude，主工作区）

- 车道 diff 只改 `tests/test_req_s01_anchors.py`，产品代码零改动，干净应用到 R1729。
- `run_selftests.py -k test_req_s01`：3 条 0 红；`tests.architecture.test_requirement_traceability`：4 条 OK；`smoke_test.py` 默认通过。
- 自证红独立复核：把 `IdeaChatMixin.add_bubble` 换成纯文本追加后，用例红在 `bubble_0 应为一段独立的气泡正文`。
- 执行方三项需裁决，Claude 裁定维持现状：①整文件进 GUI 令牌池（多出的 2 条非 Tk 用例只多约 5 秒）；②复用 `test_idea_chat._Harness` 夹具（避免重复约 30 行）；③测试期间短暂显示窗口（与 `test_idea_chat` 同类用例一致）。
