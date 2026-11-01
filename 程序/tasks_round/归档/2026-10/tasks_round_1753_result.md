# R1753：性能/资源轮——云窗销毁后提示标签残留回调（LEAK）

## 三问

1. **轮次类型**：§3.7 性能／资源轮（先量后改；A 为销毁顺序修复，B 为量化）。
2. **测试跑了吗、三个基线过了吗**：
   - 新增回归 `tests/test_leak_teardown.py`：3 条全绿（28.472 秒）。
   - 默认冒烟 `python -B smoke_test.py`：8/8 通过，0 失败。
   - 架构门禁：未运行（任务书要求由调度方验收时自己跑）。
   - 全量回归：未运行（任务书明确不要跑全量）；无新增欠账。
3. **`project_status.md` 的欠账少了吗**：派发执行方不改状态页。本轮闭环了 A 的残留回调警告并新增回归；未新增欠账，历史欠账未处理。

## A. 残留回调（根因与修复）

### 涉及对话框与销毁顺序

- 提示标签路径 `.!basedialog.!canvas.!frame2.!label` 属于 `pet_cloud.Cloud.build()` 自己创建的 `BaseDialog`（`ui_widgets.py:735`，`modal=False, chrome=False`），不是设置页或业务弹窗；偶见的 `.!basedialog2` 是同一条云窗排在其它对话框之后。
- 销毁顺序：`cloud.win.destroy()` → Tk 先销毁子控件，标签的 Tcl 命令被删除 → 顶层窗口的 `<Destroy>` 事件触发 `pet_cloud.py:377` 绑定的 `Cloud._window_gone`（`pet_cloud_timing.py:223`）→ 调用 `_hint_stop()`。
- 旧版 `_hint_stop()`（HEAD 的 `pet_cloud_hint.py:114`）先 `after_cancel`，随后**无条件** `self.hint.configure(text='')`；此时标签已销毁，Tcl 报 `invalid command name ...label`，被 `except` 里的 `app_logging.swallowed()` 记录，正好是日志中的那条警告。
- 滚动定时器本身登记在 `self.parent` 上（`parent.after`），不随云窗销毁；`_window_gone` 已在 `_hint_stop` 里撤销它，问题不是定时器残留，而是撤销后仍去操作已销毁的标签。`_sync_hint`／`_hint_tick` 也存在同类“标签可能已死”的入口。

### 修复（最小改动，无吞异常兜底）

- `程序/pet_cloud_hint.py`
  - `_sync_hint`：先 `winfo_exists()`；标签不存在则清空 `self.hint`，不再 configure。
  - `_hint_tick`：访问 `chat_row`／重排前先确认标签仍存在，否则清空引用并结束。
  - `_hint_stop`：先撤销定时器（原逻辑保留），再用 `winfo_exists()` 决定是否 `configure(text='')`；不存在只清引用。
- 仍保留的 `except` 只覆盖“标签存在但 configure 真失败”的异常路径，销毁竞态已由存在性判断处理。

### 复现（改前红）

用 `git show HEAD:程序/pet_cloud_hint.py` 取出旧版，按生产路径预加载后跑同一测试（旧版文件名显示为临时文件 `pet_cloud_hint_head.py`，行号 114 与生产日志一致）：

```text
test_cloud_dialog_destroy_revokes_hint_callback ... pet_cloud_hint_head.py:114 已忽略 TclError: invalid command name ".!basedialog.!canvas.!frame2.!label"
FAIL
test_hint_stop_after_dialog_destroy_is_silent ... FAIL

FAIL: test_cloud_dialog_destroy_revokes_hint_callback
AssertionError: <tkinter.Label object .!basedialog.!canvas.!frame2.!label> is not None

FAIL: test_hint_stop_after_dialog_destroy_is_silent
AssertionError: Lists differ: ['10:50:35 pet_cloud_hint_head.py:114 TclE[45 chars]el"'] != []
- ['10:50:35 pet_cloud_hint_head.py:114 TclError: invalid command name ".!basedialog.!label"']

Ran 2 tests in 0.539s
FAILED (failures=2)
```

独立探测（真实 `Cloud.show(pinned=True)` 后 `cloud.win.destroy()`）：

```text
# HEAD 版
pet_cloud_hint_head.py:114 已忽略 TclError: invalid command name ".!basedialog.!canvas.!frame2.!label"
new swallowed: ['10:47:25 pet_cloud_hint_head.py:114 TclError: invalid command name ".!basedialog.!canvas.!frame2.!label"']

# 当前修复版
hint_job after destroy: None
hint is None after: True
win after: None
new swallowed: []
```

根窗口直接销毁（应用退出路径）探测：`new swallowed: []`。

### 改后绿

```text
Ran 3 tests in 26.063s
OK
```

## B. 页面切换资源量化

条件：真 Tk（根窗口 `withdraw()`），临时已采用分镜的项目，`Desktop` 的 14 个 `PAGES` 全部逐页 `go_page()`＋`update()`；每轮结束再做 20 次 `update()`（间隔 10ms）让排队回调到点后测量。递归控件数从主窗口向下统计。

| 轮次 | 主窗口子控件数 | 递归控件总数 | 待执行 after 任务数 | 活动线程数 | 本轮耗时 |
| --- | --- | --- | --- | --- | --- |
| 1 | 5 | 197 | 7 | 1 | 8.0s |
| 2 | 5 | 197 | 7 | 1 | 7.3s |
| 3 | 5 | 197 | 7 | 1 | 8.5s |

结论：第 2 轮到第 3 轮四项均不增长（第 1 轮建缓存后也没有增长），未发现需要修复的页面／模块。`CACHED_PAGES` 的 02 剧本结构、03 初步分镜命中缓存后同样稳定。B 无代码改动。

## 改动清单

| 文件 | 函数／位置 | 改动 |
| --- | --- | --- |
| `程序/pet_cloud_hint.py` | `_sync_hint`、`_hint_tick`、`_hint_stop` | 标签存在性判断；已销毁则只清引用，不再 configure |
| `程序/tests/test_leak_teardown.py` | 新增 | 3 条真 Tk 回归：真实 Cloud 销毁撤销提示、`_hint_stop` 晚到不报错、14 页×3 轮资源有界 |
| `程序/维护记录/skip台账.json` | 末尾 | 为新测试的 tkinter／display 两条 skip 登记（与源码双向一致） |

未改 `desktop.py`（行数不变）、`ui_widgets.py`、`desktop_layout.py`、`responsive_ui.py`、`pet_cloud_timing.py`、`pet_cloud.py`；未改 `project_status.md`、`AGENTS.md`、`docs/stages/`；未提交、未领号。

## 验证命令与实际计数

| 命令 | 结果 |
| --- | --- |
| `python -B tests/test_leak_teardown.py` | 退出码 0，3 条通过，26.063 秒；未出现 swallowed／label 无效命令 |
| `python -B run_selftests.py -k leak_teardown pet_cloud app_logging` | 8 个测试文件、43 条用例、0 红、31.5 秒、跳过 0 条 |
| `python -B smoke_test.py` | 通过 8 项，失败 0 项 |
| `python -B tests/test_pet_ui.py`（消费方） | 599 条通过，95.740 秒（另有其它模块既有的 `invalid command name ...finish` stderr，与本轮提示无关） |
| `PYTHONPATH=程序 python -B tests/test_video.py`（消费方） | 40 条通过，0.642 秒 |
| `run_selftests.py --all --safe`、`--affected`、架构门禁 | 未运行（按任务书留给调度方） |

`pet_cloud`／`pet_cloud_hint` 的测试消费方（grep）：`test_leak_teardown`、`test_pet_cloud_contract`、`test_pet_cloud_geometry`、`test_pet_cloud_r1449`、`test_pet_cloud_shape`、`test_pet_cloud_tail`、`test_pet_cloud_text`、`test_pet_ui`、`test_video`；前 7 个已由 `-k leak_teardown pet_cloud app_logging` 覆盖，后 2 个单独跑过。

## 断言未动声明

未修改、弱化、删除或跳过任何既有测试的断言；本轮只新增 `tests/test_leak_teardown.py`，并为其新增两条 skip 台账登记。没有使用 `swallowed()` 或 `except: pass` 新增掩盖；删除竞态由存在性判断处理。

## 需裁决事项

- 无阻塞项。
- 观察（不阻塞、未扩大范围）：`tests/test_pet_ui.py` 运行时会打印其它页面回调既有的 `invalid command name "...finish"` stderr（599 条仍全绿），本轮未改动该路径，是否另立资源轮由调度方决定。

## 独立验收（Claude，最新 master R1752 之上的干净验收树）

- **执行链（如实）**：codex group/group-4 第一次 09:20 起，之后第二次尝试，期间一次 600 秒日志无增长被终止；10:45 转 Qoder DeepSeek-Flash，10:59 写出结果文件。车道基于 8a114b9a，补丁对 R1752 `git apply --check` 干净通过，未用 `commit_batch.sh LANE=`。无新增模块、无 `desktop.py` 改动，所以不涉及分层／覆盖率基线／行数上限。
- **根因核对**：Cloud 窗口 `destroy()` 时 Tk 先销毁子控件，顶层 `<Destroy>` 再触发 `Cloud._window_gone` → `_hint_stop`，后者撤销定时器后无条件 `hint.configure(text='')`，标签此时已死；与 app.log 的 `pet_cloud_hint.py:114` 警告逐字吻合。修复为 `_sync_hint`／`_hint_tick`／`_hint_stop` 先判 `winfo_exists()`，**没有**用吞异常掩盖（保留的 except 只覆盖"标签存在但 configure 真失败"）。
- **变异验证**：把 `pet_cloud_hint.py` 的修复整体 `git apply -R` 回退，`tests/test_leak_teardown.py` 3 条中 2 条变红，并复现原警告 `pet_cloud_hint.py:114 已忽略 TclError: invalid command name ".!basedialog.!canvas.!frame2.!label"`；还原后 3 条全绿。
- **命令计数（验收树）**：`run_selftests -k leak_teardown pet_cloud app_logging skip_hygiene` 46 条 0 红 23.5 秒；消费方 `-k test_pet_ui test_video pet_cloud` 840 条 0 红 70.0 秒；`smoke_test.py` 通过、失败 0 项；`smoke_test.py --architecture` 375 条全部通过（退出码 0）。验收树已从主树补齐被 git 忽略的 `基准历史.json` 与子模块 `AIGC创作全流程` 文件。
- **资源增长表**：14 页×3 轮，主窗口子控件 5、递归控件 197、after 任务 7、线程 1，三轮完全持平，B 无代码改动。该表为执行方自测，调度方未重复测量。
- 执行方观察（未处理）：`tests/test_pet_ui.py` 运行时会打印其他页面既有的 `invalid command name "...finish"` stderr，599 条仍全绿；是否另立资源轮待用户决定。
- 断言未动；新增 2 条 skip 已登记台账，`test_skip_hygiene` 通过。
