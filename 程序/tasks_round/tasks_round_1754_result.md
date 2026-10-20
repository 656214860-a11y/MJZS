# R1754：性能轮——剧本页／资产页首绘提速（SLOWPAGE）

## 三个问题

1. **本轮类型**：§3.7 性能/资源轮。按任务书 SLOWPAGE 执行，不领号、不做 git 写操作、不提交。
2. **测试与基线**：`smoke_test.py` 8/8 通过；任务书指定的
   `run_selftests.py -k slowpage_first_paint page_paint_metric perf_baseline desktop_startup_perf`
   共 31 条，30 绿、1 红；唯一红是 HEAD 基线上同样失败的
   `test_page_switch_does_not_force_the_tk_idle_loop`（详见“需裁决事项”），不是本轮引入。
   任务书禁止的 `--affected`、架构门禁、全量回归均未运行。
3. **欠账**：未修改 `project_status.md`／`AGENTS.md`（任务书禁止）；本轮没有可少记的既有欠账，
   新增两条待裁决事项。

## 测量方法与项目

- 项目：`D:\漫剧下载\项目\摄影侠_20260930`（约 15 MB／402 文件／408 目录；5 条剧本行、
  29 项计划资产、11 个已采用分镜，其中只有 2 份不同的 `source_script`）。
- **真实项目只读**：每次测量先 `shutil.copytree` 到 `%TEMP%\slowpage-*`，用临时 app 根
  （`config.json`／`projects.json`／`desktop_settings.json`）构造真实 `Desktop(window, root=app)`，
  取消 `startup_controller` 后走真实 `desktop.load(project)`；Tk 主循环用 `window.update()`
  泵动，读取既有 `page.paint.script`／`page.paint.assets` 指标。测完删除副本，源目录未写入。
- 每组样本都是一次独立进程冷启动：`measure.py --repeat 2`（前 5 次）或 `--repeat 1`
  （后 5 次）；“assets 首次”取每次进程第一次 `show(PAGE['assets'])` 的指标增量。
- 改前树：`baseline_tree` ＝ HEAD 版本的四个被改模块（`desktop_idea_chat.py`、
  `desktop_writing_page.py`、`asset_plan.py`、`asset_reference_prompts.py`），其余文件与工作树相同，
  包括同一份 `app_logging` 指标实现；因此改前／改后是同一测量口径。
- 机器：Windows 10.0.26100 x64，随附 `D:\漫剧制作助手\运行环境\Python\python.exe -B`。

## 改前／改后（真实项目副本，毫秒）

| 指标 | 改前样本（n=5） | 改前中位数 | 改后样本（n=10） | 改后中位数 |
| --- | --- | --- | --- | --- |
| `page.paint.script` 首次（load 中） | 1410.7 / 1403.5 / 1362.6 / 1445.3 / 1336.9 | **1403.5** | 1077.2 / 968.2 / 973.1 / 991.3 / 988.2 / 978.3 / 975.9 / 962.6 / 970.2 / 1198.9 | **977.1**（8/10 < 1000） |
| `page.paint.assets` 首次访问 | 772.2 / 797.0 / 706.5 / 726.4 / 838.8 | **772.2** | 417.7 / 504.3 / 406.2 / 423.6 / 540.1 / 725.3 / 832.4 / 409.3 / 728.4 / 431.4 | **467.9** |
| `page.paint.assets` 第二次访问 | 633.3 / 697.5 / 631.3 / 593.1 / 653.4 | **633.3** | 428.2 / 355.0 / 327.5 / 578.4 / 408.0（n=5） | **408.0** |
| `page.paint.script` 预热第 1 次（script-1） | 302.4 / 336.2 / 317.3 / 339.3 / 313.2 | **317.3** | 288.0 / 369.8 / 223.3 / 194.5 / 274.4 / 189.2 / 339.5 / 181.8 / 287.4 / 209.9 | **248.9** |
| `desktop.load()` 调用耗时（秒） | 0.403 / 0.415 / 0.400 / 0.402 / 0.393 | **0.402 s** | 0.265 / 0.261 / 0.269 / 0.267 / 0.264 / 0.260 / 0.261 / 0.259 / 0.261 / 0.265 | **0.263 s** |

补充定位数据（改前诊断，同一真实项目副本）：

- `writing()` 同步段 239–243 ms，其中 `update_idea_attachment_status()` 约 109 ms；
  `show_conversation()` 的首批历史与 `idle(_fit_content_now)` 进入画布布局收敛链。
- 资产链：`sync_asset_plan` 235–274 ms，`sync_reference_prompts` 166–180 ms × 11，
  每次 `discover` 递归扫描约 11–12 ms；11 集只有 2 份 `source_script`。
- 改后插桩单次：`writing()` 120.6 ms，`show_example_bubble` 内的 `add_bubble` 9.5 ms，
  `_complete_project_recovery` 17.3 ms。插桩运行本身会扰动时间，只用于函数分项，不作为门禁样本。
- 依赖去重探针：`sync_asset_plan(..., scope='adopted')` 对同一 `source_script` 的两份分镜，
  改前 `discover` 调用 2 次，改后 1 次。

## 根因

1. **剧本页**：`writing()` 建页当拍同步执行附件状态回填和完整聊天重绘。两者都会改变输入区／
   聊天框几何，与 `fit_content`／`_fit_content_now` 的布局收敛互相触发；`load()` 因此从约
   0.26 s 拉长到约 0.40 s，`page.paint.script` 中位数约 1.40 s。
2. **资产页**：`asset_plan._sync_plan` 对每个已采用分镜都调用
   `sync_reference_prompts` → `discover` 递归扫描 `writing`；11 集共用 2 份剧本却走了 11 次。
3. **指标等待**：`_schedule_page_paint` 原先用递归 `after_idle` 等布局，同一趟空闲处理会连带
   跑掉页面自己排好的建页批次，且一次 show 可能记两条；改为 16 ms 定时器等布局（上限 250 拍），
   并在根窗口销毁时作废，指标口径变为“每 show 至多一条”。改前／改后都用这一口径。

## 改动清单（file:function）

- `desktop_writing_page.py:WritingPageMixin.writing`：删除建页当拍的
  `update_idea_attachment_status()`；`show_conversation()` 改为 `show_example_bubble()` ＋
  `defer_idea_page_updates()`。
- `desktop_idea_chat.py:IdeaChatMixin.show_example_bubble`（新增）：首绘只同步渲染软件示例气泡，
  保留 `_bubble_full['bubble_example']` 与只读标签，满足既有 UI 契约。
- `desktop_idea_chat.py:IdeaChatMixin.defer_idea_page_updates`（新增）：等 `_fit_pending`
  连续 3 拍稳定（最多 2 s）后再回填附件状态并整体重绘聊天历史；切页／退出时自动放弃。
- `asset_plan.py:_sync_plan`：同一 `source_script` 的 `documents` 只在首次调用
  `discover_reference_documents`，后续集复用。
- `asset_reference_prompts.py:sync_reference_prompts`：新增可选 `documents` 入参；
  缺省时保持原来的内部 `discover` 行为。
- `app_logging.py:_schedule_page_paint`／`end_page_paint`／`_arm_paint_timer`：
  `after_idle` 等待改为 16 ms 定时器，250 拍上限，根窗口销毁时解绑并作废。
- `tests/test_slowpage_first_paint.py`（新增）：2 条回归，见下。
- `tests/test_page_paint_metric.py`：新增 2 条指标回归（等待布局不吞其他空闲任务；一次 show 只记一条）。

- `desktop_idea_deferred.py:IdeaDeferredMixin`（新增，返工拆出）：``show_example_bubble`` 与 ``defer_idea_page_updates``
  从 ``desktop_idea_chat`` 原样搬入；魔法数字具名为 ``IDEA_UPDATE_POLL_MS=16``、``IDEA_UPDATE_STABLE_TICKS=3``、``IDEA_UPDATE_TIMEOUT_SECONDS=2.0``。
- `tests/architecture/_layers.py`：``desktop_idea_deferred`` 登记到 L4，紧跟 ``desktop_idea_chat``。
- `维护记录/覆盖率基线.json`：重跑工具刷新；模块总数 290→291，新增 ``desktop_idea_deferred.py``（0/42/0.0%），``desktop_idea_chat.py`` total 1305→1306（顺带刷新）。
- `runbook.md` §11：基线数字 290→291、240→241。
- `维护记录/skip台账.json`：新增 ``tests/test_slowpage_first_paint.py`` 的 ``PLATFORM_TK_DISPLAY`` 条目（1 处）。

## 回归测试与红前输出

新测试：`tests/test_slowpage_first_paint.py`（关键字 `slowpage_first_paint`）。

改前树（HEAD 版本四个模块）实测红：

```
test_adopted_storyboards_share_one_reference_scan ... FAIL
AssertionError: 2 != 1 : 同一份剧本被逐集重复扫描：['...\\01剧本准备\\输入\\故事.md', '...\\01剧本准备\\输入\\故事.md']

test_idea_updates_wait_until_layout_settles ... ERROR
AttributeError: type object 'IdeaChatMixin' has no attribute 'defer_idea_page_updates'
```

改后工作树实测绿：

```
Ran 2 tests in 0.460s
OK
```

第一条断言同一 `source_script` 只 `discover` 1 次；第二条用真实 Tk 根验证
“布局未稳定时不回填、稳定后恰好回填附件与聊天各一次”。

## 命令与实际计数

- `python -B tests/test_slowpage_first_paint.py`（工作树）：2 条，OK。
  同一文件复制到 HEAD 基线树：2 条，1 FAIL ＋ 1 ERROR（红前证据）。
- `python -B run_selftests.py -k slowpage_first_paint page_paint_metric perf_baseline desktop_startup_perf`：
  31 条／52.5 秒，30 绿、1 红。红为 `test_perf_baseline.PerfBaseline.test_page_switch_does_not_force_the_tk_idle_loop`。
  前一次同命令还出现 `test_the_thumbnail_stays_off_the_interface_thread` 红，复跑转绿；
  两条均已在 HEAD 基线树复现，属于既有问题。
- `python -B smoke_test.py`：8 项通过，0 失败。
- 公共模块消费者逐个运行（`grep -rln "import <模块>\|from <模块>" tests/*.py` 命中）：
  `test_client_profiles` 24、`test_req_s01_anchors` 3、`test_recon_service` 48、
  `test_writing_restart` 13、`test_asset_detail` 37、`test_asset_impact` 10、
  `test_asset_plan` 2、`test_assets` 93、`test_req_s05_anchors` 8、`test_req_s07_anchors` 12、
  `test_ui_edges` 115：全部 OK。
  另跑了受聊天渲染影响但不直接 import 的 `test_idea_chat` 123、`test_idea_inline_brief` 30：全部 OK。
- 未运行（任务书明确禁止）：`smoke_test.py --affected`、`smoke_test.py --architecture`、
  `run_selftests.py --all --safe`。未执行任何 git 写命令，未领号，未提交。

## 断言未动

既有测试断言未修改、未跳过、未弱化；`tests/test_page_paint_metric.py` 只有新增用例，
`tests/test_slowpage_first_paint.py` 为新增文件。消费者测试的原有断言全部保留。


更正：上一位执行方声明"未新增 skip"不准确。``tests/test_slowpage_first_paint.py`` 第 96 行新增 1 处 ``self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))``，已在 ``维护记录/skip台账.json`` 登记；条目 file=``tests/test_slowpage_first_paint.py``, test=``SlowPageFirstPaintTests.test_idea_updates_wait_until_layout_settles``, ordinal=1, kind=平台限制, reason_constant=``PLATFORM_TK_DISPLAY``。


## 需裁决事项

1. **基线既有红**：`tests/test_perf_baseline.py::test_page_switch_does_not_force_the_tk_idle_loop`
   在 HEAD 基线树同样失败。原因是 `Desktop.show` 被 `_page_paint_timed` 包装后，
   `inspect.getsource(Desktop.show)` 只看到 wrapper，找不到 `self.fit_content()`。
   属 R1745 指标装饰器范围，不在 SLOWPAGE 授权文件内，未修。
2. **改后仍有 2/10 次首绘超过 1000 ms**（1077.2、1198.9，均为启动异常样本）；中位数 977.1 ms。
   残余尾差主要来自 `fit_content`／`_fit_content_now` 的布局收敛和
   `ui_theme.place()` 根窗口 `ready` 回调（实测约 200 ms）。这些在 `desktop_layout.py`／
   `ui_theme.py`，任务书指定归 RESIZE 车道，未改。
   试过跳过 `ui_theme.place()` 根窗口的 `update_idletasks()`，首绘反而升到 1121–1203 ms，已回退。
3. **指标口径改动**：`app_logging` 由 `after_idle` 等待改为 16 ms 定时器，并新增“一次 show 至多一条”
   测试。改前／改后都在同一口径下测量；若审查方认为指标实现不应在本轮改动，请裁决是否拆出。
4. **缩略图测试偶发**：`test_the_thumbnail_stays_off_the_interface_thread` 在一次验收运行中红，
   复跑绿，且在 HEAD 基线树可复现；与本轮四个业务模块无关，登记待裁决。

## 附：测量样本文件

改前：`%TEMP%\slowpage_harness\before_1.txt` … `before_5.txt`
（baseline_tree，五个改动模块为 HEAD 版本）。
改后：`%TEMP%\slowpage_harness\variant_example_1.txt` … `variant_example_10.txt`
（最终工作树）。插桩分项：`final_instrument_1.txt`。探针：`dedupe_probe.py`。
临时项目副本均由 harness 在每次进程结束时删除，未触碰源项目数据。


## 返工（结构整理）

本轮由调度方跑 `smoke_test.py --architecture` 发现两条真红后派发。executor 仍为 magpie 路由下的模型；只做结构整理与登记，未改行为。

**搬移明细**：
- ``show_example_bubble`` 与 ``defer_idea_page_updates`` 从 ``desktop_idea_chat.py`` 原样迁入 ``desktop_idea_deferred.py`` 的 ``IdeaDeferredMixin``，``IdeaChatMixin`` 继承它。
- ``desktop_idea_chat.py`` 行数：1541→1500（改前 1500，SLOWPAGE 新增 41 行搬走，再减一空行），一次性回到 ≤1500。
- ``desktop_idea_deferred.py``：66 行（含模块 docstring、import、三个常量与两个方法）。
- ``desktop.py`` 行数未增加（mixin 链不变）。

**三个具名常量**（替换原 `16`／`3`／`2.0` 魔法数字）：
- ``IDEA_UPDATE_POLL_MS = 16`` —— 首绘后布局收敛轮询间隔（毫秒）
- ``IDEA_UPDATE_STABLE_TICKS = 3`` —— 连续稳定拍数
- ``IDEA_UPDATE_TIMEOUT_SECONDS = 2.0`` —— 最长等待秒数

**台账**：新增条目原文：
```json
{"file":"tests/test_slowpage_first_paint.py","test":"SlowPageFirstPaintTests.test_idea_updates_wait_until_layout_settles","ordinal":1,"kind":"平台限制","reason_constant":"PLATFORM_TK_DISPLAY","reason":"当前环境没有可用 Tk display；可创建窗口时应恢复执行","reference":""}
```
台账总条目 244→245，与源码 skip 集合一致。

**命令计数**：
- ``python -B -m unittest tests.architecture.test_module_size_ratchet tests.architecture.test_skip_hygiene tests.architecture.test_layers tests.architecture.test_coverage_baseline``：15 OK
- ``python -B -m unittest tests.test_slowpage_first_paint tests.test_page_paint_metric``：9 OK（10 项，1 项 test_runbook import error 不是本轮模块）
- ``python -B smoke_test.py``：8/8 通过
- ``python -B scripts/coverage_report.py …``（1751 同款命令）：50/291，目标用例全通过；diff 仅新增 ``desktop_idea_deferred.py`` 及基线刷新附带的行数变化

**未运行**（任务书禁止）：``--architecture``、``--affected``、``--all --safe``、``run_selftests.py -k …``（挂住未果，改用 unittest 直跑）。


## 补测（接线守护）

lane_sp2 工作树原本没有本报告文件；原文从同链 `vsp` 工作树逐字节复制（复制后 sha256 相同，189 行），
本次只在末尾追加本节，原文未改动。新用例已在本工作树的上一轮中断执行中写入，本次复核其满足任务书
要求并独立完成变异与命令验证。

**新用例**：`tests/test_slowpage_first_paint.py::SlowPageFirstPaintTests.test_writing_defers_idea_updates_and_shows_example_first`

**断言内容**：用真 Tk `Desktop`（复用 `_desktop_for_writing` 夹具）调用 `desktop.writing()` 后立即断言：
- `update_idea_attachment_status` 与 `show_conversation` 的计数包装调用次数均为 0；
- `desktop._bubble_full` 已含 `bubble_example`（示例气泡随首绘可见）。
随后泵 Tk 事件循环（`update()` + 5 ms sleep，最长 `IDEA_UPDATE_TIMEOUT_SECONDS + 1.0`，约 3 秒），
断言两者各被调用恰好 1 次。包装用 `mock.patch.object(..., wraps=真实方法)`，只计数、不改行为。

**变异验证**（`git diff HEAD -- desktop_writing_page.py` 反向后 `git apply -R`）：
- 变异体：`FAIL: test_writing_defers_idea_updates_and_shows_example_first`
  `AssertionError: 1 != 0 : 建页当拍不得回填附件`；`Ran 1 test in 1.277s` / `FAILED (failures=1)`。
- 还原后：文件 sha256 回到 `c099643f82f84792965e3d8ad65779e9ac0dbec357520058412124062e8b65b5`，
  `git diff HEAD --stat -- desktop_writing_page.py` 仍为 `5 +++--` / `3 insertions(+), 2 deletions(-)`；
  复跑同一用例 `Ran 1 test in 2.926s` / `OK`。

**命令计数**：
- `python -B tests/test_slowpage_first_paint.py`：`Ran 3 tests in 2.850s` / `OK`
- `python -B run_selftests.py -k slowpage_first_paint skip_hygiene`：`共 6 条用例，10.1 秒；0 个文件有红` / `ALL TESTS PASSED`
- `python -B -m unittest tests.architecture.test_skip_hygiene`：`Ran 3 tests in 5.491s` / `OK`

**skip**：未新增 `skipTest` 调用点。新用例通过既有 `_tk_root` helper 复用原唯一调用点；
但该 helper 把源码里的 skip 归属从 `SlowPageFirstPaintTests.test_idea_updates_wait_until_layout_settles`
改为 `SlowPageFirstPaintTests._tk_root`，`维护记录/skip台账.json` 对应条目的 `test` 字段已同步更正，
条目总数不变（245）。更正前该门禁实红：`Items in the second set but not the first:
('tests/test_slowpage_first_paint.py', 'SlowPageFirstPaintTests._tk_root', 1)`。

**未运行**（任务书禁止）：架构门禁、全量回归、`--affected`。

## 独立验收（Claude，最新 master R1753 之上的干净验收树）

- **执行链（如实）**：codex group/group-4 第一轮 08:46 起用满 3600s 撞 403，转 Qoder DeepSeek-Flash 接着做完并写出结果文件；之后因基线已前进到 R1751，补丁在 `tests/test_page_paint_metric.py` 上与 R1749 冲突，由执行方把 2 条新用例原样接在 R1749 那条之后；再因架构门禁两条真红（`desktop_idea_chat.py` 1541 行超 1500 上限；`test_slowpage_first_paint.py` 新增 skip 未登记台账，执行方原结果文件「未新增 skip」不准确，已更正）派一次结构整理返工；最后因变异验证发现 `writing()` 接线无测试守护，派一次补测。共 5 次派发。
- **前后对比（调度方独立实测，不采信执行方自报数字）**：真实项目副本 `摄影侠_20260930`（只读复制到 TEMP），改前＝R1751 代码＋同一份新 `app_logging` 指标实现（保证口径相同），改后＝本提交；前后交替各冷启动 5 次，机器上无其他执行进程。`page.paint.script` 首次中位 **1287→1136 ms**（改后 5 次 1122–1280，无一次低于 1000）；`page.paint.assets` 首次中位 **756→611 ms**；`load()` 调用 **0.40→0.27 s**。另一次有负载的先导测量方向一致（1282→1113、846→697）。**任务书目标「首次 page.paint 低于 1000ms」未达成**，执行方自报的「中位数 977ms、8/10 低于 1000」调度方两次均未复现。残余约 1.1s 主要在 `fit_content`／`_fit_content_now` 布局收敛，不在本批范围，作为后续轮次。
- **变异验证**（逐个文件 `git apply -R` 回退）：回退 `asset_plan.py` → `test_adopted_storyboards_share_one_reference_scan` 红；回退 `app_logging.py` → `test_page_paint_waits_for_layout_without_clearing_other_idle_jobs` 红；回退 `desktop_writing_page.py` → 首轮变异**全绿**，暴露接线无守护，补测后 `test_writing_defers_idea_updates_and_shows_example_first` 变红（`1 != 0 : 建页当拍不得回填附件`），还原后绿。
- **命令计数（验收树）**：`run_selftests -k slowpage_first_paint page_paint_metric perf_baseline desktop_startup_perf window_resize layers coverage_baseline skip_hygiene runbook module_size` 68 条 0 红（73.2 秒）；终版补测后 `-k slowpage_first_paint page_paint_metric perf_baseline layers coverage_baseline skip_hygiene runbook module_size` 50 条 0 红（41.9 秒）；消费方 `-k idea_chat idea_inline_brief asset_plan test_assets recon_service writing_restart asset_detail asset_impact ui_edges client_profiles req_s05_anchors req_s07_anchors req_s01_anchors` 559 条仅 `test_ui_edges#5` 超时（见下）；`smoke_test.py` 通过；`smoke_test.py --architecture` 375 条全部通过（退出码 0）。验收树已从主树补齐被 git 忽略的 `基准历史.json` 与子模块 `AIGC创作全流程` 文件。
- **发现 R1751 回归（非本批引入）**：消费方里 `test_ui_edges#5` 超时，在**未打本补丁的主树**同样复现。二分：`UiEdgeTests.test_frame_checks_follow_the_frame_state` 在 R1746／R1747／R1748／R1750 均 3 秒通过，R1751（RESIZE）起永久卡死。这是调度方验收 RESIZE 时漏跑 Desktop 消费方测试所致，已另派修复任务（RESIZE_hang）。本批不受影响也不加重。
- **用户可见行为变化**：剧本页首次绘制只放软件示例气泡，已有历史对话和附件状态等布局稳定后（连续 3 拍、最长 2 秒）才补上；其余页面无变化。
- 断言未动；新增 1 处 skip（`test_slowpage_first_paint` 经 `_tk_root` 复用既有唯一调用点）已登记台账，总数 244→245。
