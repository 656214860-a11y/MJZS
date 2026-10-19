# R1747：性能轮——prune_invalid_adoptions 惰性扫描剧本目录（PERFSB2）

执行方：Codex（本车道 `.wt\lane_perf2`）。仅验证并写本结果文件；未改生产代码、未改测试、未执行 git 写命令、未领号、未改 `project_status.md`／`AGENTS.md`、未读 `private\`／`.env`。
解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`。

## 一、三问
1. **轮次类型**：§3.7 性能/资源轮（收尾只验证，不改代码）。
2. **测试跑了吗、三个基线过了吗**：跑了，全部实跑：
   - 定向 `run_selftests.py -k storyboard_catalog storyboard_selection adopt`：7 个文件 / 35 条用例，0 红，2.7 秒。
   - 默认冒烟 `smoke_test.py`：通过 8 项、失败 0 项（8/8）。
   - 架构门禁 `smoke_test.py --architecture`：`Ran 374 tests ... OK`，0 红 / 0 skip（跳过 0 条）。
3. **`project_status.md` 欠账少了吗**：没有变化——本任务按派发要求不碰状态页与欠账台账；未产生新欠账（无源码改动）。另见“需裁决事项”第 1 条（任务书记载的 `test_round_baselines` 欠账在实测中不存在）。

## 二、改动清单（核对后与本任务书描述一致，无范围外改动）
`git status --short` 输出恰好三行：
- `M storyboard_catalog_service.py`
- `M storyboard_selection.py`
- `?? tests/test_storyboard_catalog_scan_count.py`

`git diff` 内容归纳（`2 files changed, 43 insertions(+), 10 deletions(-)`，另加新测试文件）：
- `storyboard_catalog_service.discover_files`：删除逐文件 `path.resolve()`，改为 `yield path, path, stat`；越界判断改为 `path.is_relative_to(root)`（root 先 resolve）。
- `storyboard_catalog_service.catalog`：新增可选参数 `completed=None`，透传给 `_catalog`；`_catalog` 在 script 分支用 `completed` 替代 `produced_scripts(context)` 的二次分镜扫描。
- `storyboard_selection.source_script_error`：新增可选参数 `available=None`，可为集合或取数器；取数器只在通过读 JSON／来源检查之后才调用；`available is None` 时用 `completed=set()` 取剧本集合。
- `storyboard_selection.prune_invalid_adoptions`：循环外改为带缓存的惰性取数器（`cache=[]` 闭包），只有第一个真正到达来源比对的板触发一次扫描。
- 新增 `tests/test_storyboard_catalog_scan_count.py`：8 条用例（空列表 0 次、全部提前返回 0 次、仅最后一块到达比对 1 次、N=1/2/10 各 1 次、与基线 `39b3c7f6` 的返回值与计数对照、摘除行为、传 `completed` 不改输出）。
- 未改 `storyboard_selection.py:297` 一带的单板校验点行为：`source_script_error(project, source)` 仍按两参数调用（现签名第三个参数可选），文案未变（`对应分镜初稿不存在或已迁移：` 等三条字符串与基线逐字一致）。

## 三、原任务书验收条款逐条核对（PERFSB2 返修口径）
| # | 条款 | 结论 | 证据 |
|---|---|---|---|
| 1 | `prune_invalid_adoptions` 的 `available` 改为惰性：第一个真正需要来源比对的板才取一次，之后复用；空列表或全部提前返回 0 次 | 满足 | `storyboard_selection.py:200-205` 闭包 `available()` 只在 `source_script_error` 通过读 JSON／来源检查之后被调用（`storyboard_selection.py:179-180`）；`test_prune_empty_adoptions_scans_nothing`、`test_prune_scans_nothing_when_all_boards_return_early` 同时断言 `_catalog`/`discover_files` 与取数器都为 0 |
| 1b | `source_script_error` 对外签名与文案不变；`storyboard_selection.py:297` 单板校验点行为不变 | 满足 | 签名只追加带默认值的 `available=None`；三条返回文案与 `39b3c7f6` 基线逐字一致；现有 `tests/test_file_cache.py:236` 两参数调用照常通过 |
| 2a | 空采用列表：`_catalog`、`discover_files` = 0，与改前一致 | 满足 | 新用例 `test_prune_empty_adoptions_scans_nothing` 实测 `(0, 0)`、取数器 0；基线对照用例 `test_prune_early_return_counts_match_baseline_no_scan` 实测改前为 `COUNT 0 0` |
| 2b | 所有板提前返回：`_catalog`、`discover_files` = 0 | 满足 | `test_prune_scans_nothing_when_all_boards_return_early` 实测 `(0, 0)`、取数器 0，返回值为两份损坏 JSON |
| 2c | N 个板到达比对（N=1/2/10，含失效）：`_catalog` = 1、`discover_files` = 1，与 N 无关 | 满足 | `test_prune_scan_count_is_one_for_one_two_ten_comparisons` 实测 `[1,1,1]` / `[1,1,1]`；`test_prune_scans_zero_unless_a_board_reaches_comparison` 只有最后一块到达时也为 `(1, 1)` |
| 2d | 仍摘掉失效板、返回值与改前一致 | 满足 | `test_early_return_removed_values_match_head` 在 `git show 39b3c7f6` 的真实旧实现上逐项比对通过；未被采用、来源已失效的孤儿板不被摘（断言 `assertNotIn`） |
| 3 | 扫描次数有专项测试 | 满足 | `tests/test_storyboard_catalog_scan_count.py` 8 条，全部通过；空列表条目的 docstring 注明“从 PERFSB 初版的 1 收回 0”的理由 |
| 4 | 真 Tk `Desktop.show(PAGE['storyboard'])` 下 MainThread `_catalog` 计数（空项目夹具应为 0） | 满足 | 见下节“MainThread 实测” |
| 5 | `discover_files` 去掉逐文件 `resolve()`：仍排除符号链接／联接点 | 满足 | 见“链接排除实测” |

### 4. MainThread 实测（临时脚本在 `%TEMP%`，未进仓库）
参考 `tests/test_asset_detail.py` 的写法：`Desktop(win, root=… )` + `ensure_stage_layout()` + `show(PAGE['storyboard'])`，空项目（仅一个 `{}` 的 `config.json`），事件循环驱动 5 秒（让后台 `catalog_snapshot` 完整跑完），用 `patch` 包裹 `_catalog` 并记录调用线程：

- `MAIN_THREAD MainThread`
- `_catalog calls 2`，线程集合 `['storyboard-catalog-scan']`（即 MainThread 0 次）
- `discover_files calls 5`

与任务书改前基线（`_catalog` 2 次、`discover_files` 4 次，全部在后台线程）对比：`_catalog` 相同、UI 线程同为 0 次；`discover_files` 5 vs 4 是因为 `catalog_snapshot` 的 script 目录传入了 `completed`，不再经 `produced_scripts` 多扫一遍分镜目录——这项“少一次”的改动属于原 PERFSB 范围，本收尾未改它，未单独复测其改前数值。

### 5. 链接排除实测（临时目录，未改仓库）
- 指向项目外的目录联接点（`mklink /J`）：`is_junction()` 为 True，`discover_files` 只发现 `ok.md`，`secret.md` 未出现（`leak: False`）。
- 指向 root 内部子目录的联接点：未被跟进（结果只有真实路径的 `a.md`、`sub\b.md`，无 `loop_to_sub\…` 重复项）。
- 文件级符号链接 `flink.md`：`is_symlink()` 为 True，未被收录。

## 四、扫描次数前后对比（来自测试内真实计数，不是推算）
| 场景 | 改前（`39b3c7f6`） | PERFSB 初版 | 当前（PERFSB2） |
|---|---|---|---|
| 采用列表为空 | 0 / 0 | 1 / 1（循环外无条件预取） | **0 / 0**（取数器 0） |
| 所有板提前返回 | 0 / 0（基线对照用例实测 `COUNT 0 0`） | 1 / 1 | **0 / 0**（取数器 0） |
| N=1 全部到达比对 | N×2 量级（每板一次 `catalog('script')`，且经 `produced_scripts` 再扫分镜目录） | 1 / 1 | **1 / 1** |
| N=2 全部到达比对 | 同上 | 1 / 1 | **1 / 1** |
| N=10 全部到达比对 | 同上 | 1 / 1 | **1 / 1** |
| 真 Tk 页面（空项目）MainThread | 0 | 1 | **0** |

（表中“改前 N×2 量级”来自任务书背景描述与本轮读到的基线源码结构，本轮未对每个 N 重跑基线实现，仅对“提前返回＝0”做了基线对照实测。）

## 五、实际计数与命令输出摘要
- `python -B run_selftests.py -k storyboard_catalog storyboard_selection adopt`：`7 个测试文件 / 7 路工作单元`；`共 35 条用例，2.7 秒；0 个文件有红`；最慢 `test_storyboard_catalog_scan_count 1.4 秒 / 8 条`；跳过 0 条。
- `python -B smoke_test.py`：`通过：8 项` / `失败：0 项`。
- `python -B smoke_test.py --architecture`：`Ran 374 tests in 131.792s` / `OK`，失败 0；有 1 条无关 `SyntaxWarning`（`skills/00全流程SKILL/…/check_package.py:2239` 无效转义），不影响结果。
- `python -B -m unittest tests.architecture.test_round_baselines`：`Ran 5 tests ... OK`（5/5 通过，无“欠一次完整安全全量”红）。
- 消费方测试：`python -B -m unittest tests.test_file_cache tests.test_storyboard_plan_service tests.test_workflow tests.test_req_s03_anchors tests.architecture.test_project_context_boundary`：`Ran 161 tests ... OK`。
- 一条如实记录的过程异常：第一次执行定向 `-k` 命令时把输出接了 `| Select-Object -Last 25`，PTY 下等到约 12 分钟仍无输出，遂中止该会话（未产生结论）；随后无缓冲重跑，2.7 秒通过全部 35 条。**不足**：该次“中止前 12 分钟无输出”的原因本轮未定位（未加日志复现），只能确认不是测试本身变慢；如调度方在意，可另立只读诊断项。

## 六、消费方检查（`grep` 全仓 `.py`，排除 `private\`）
- `discover_files`：`storyboard_catalog_service.py:116`、`:475`、`storyboard_selection.py:390`、`asset_reference_prompts.py:41`、`tests/test_storyboard_plan_service.py:28`。全部按 `(roots, suffixes, ignored[, ignored_name])` 旧签名调用，解包仍为三元组；签名未变，**不破坏**。
- `catalog`：`storyboard_catalog_service.py:545/551`（内部，旧签名）、`storyboard_selection.py:184/204/406`、`stage_execution_service.py:852`（L3 门面，两段式位置参数）、`workflow_context.py:77/87`、`workflow_tasks.py:235`、`pet_ui_voice.py:367/368`（经 L3 门面）、`desktop.py:1067`（经 L3 门面）、`storyboard_recycle_service.py:31/36`（经 L3 门面）、`storyboard_files.py:105/109/120/479/837`（兼容门面，三位置参数）、`tests/test_file_cache.py`、`tests/test_req_s03_anchors.py:140/334`、`tests/test_workflow.py:91`。新增 `completed` 带默认值且置于末位，**不破坏**。
- `source_script_error`：`storyboard_selection.py:211`（传 `available=available`）、`:320`（两参数，旧调用）、`tests/test_file_cache.py:236`（两参数）。**不破坏**。
- `prune_invalid_adoptions`：`storyboard_page_controller.py:25`（`self.project`）、`storyboard_files.py:600`（`controller.prune_invalid_adoptions()`）、`tests/test_req_s03_anchors.py:315`、新测试。签名未变，**不破坏**。
- 上述命中的测试文件均已跑：`test_file_cache`、`test_storyboard_plan_service`、`test_workflow`、`test_req_s03_anchors`、`architecture.test_project_context_boundary` 共 161 条全绿。
- 需注意：`prune_invalid_adoptions` 在 `storyboard_files.py:600`（页面 `show()` 内）是**同步在 UI 线程**调用的——这正是“必须惰性、不能无条件预取”的原因；当前实现在空项目／全部提前返回时 MainThread 为 0 次，已满足。

## 七、“断言未动”声明
- 本任务未修改任何测试文件、未增删断言、未加 skip；`tests/test_storyboard_catalog_scan_count.py` 为调度方上一轮写入后原样存在，本轮只读取并运行。
- 既有测试 `tests/test_file_cache.py`、`tests/test_req_s03_anchors.py` 等的断言未改（`git status` 仅三行，可佐证）。
- 本节只声明本轮行为，不对更早已有历史断言做背书。

## 八、需裁决事项
1. **任务书对 `test_round_baselines` 的描述与实测不符**：任务书称其“欠一次完整安全全量”应出现，本轮单独运行 `Ran 5 tests ... OK`（5/5 绿），`--architecture` 全量 374 条也全绿。可能原因是 common-dir 的全量凭据在期间被刷新，或本车道树不同；按实际情况记录为“无该欠账红”，未做任何修复。
2. **`discover_files` 的越界语义变为词法判断**：`root` 已 resolve，链接目录／文件均被排除，路径不可能带链接分量，所以等价；但若将来有人绕过本函数直接传已解析的链接路径，这里不再兜底（属防御性变化，不是当前行为缺陷）。建议在 `architecture.md` 或该函数 docstring 保持现在的说明即可。
3. **`discover_files` 的“少一次扫描”未与本轮要求逐项复测**：真 Tk 实测 `discover_files`=5 而任务书基线写 4，差 1 来自原 PERFSB 的 `completed` 优化（本收尾不改它）。若要严格对账，需要调度方按基线逐项核对 `catalog_snapshot` 的两次 `_catalog` 调用分解。
4. **消费方门面 `storyboard_files.catalog(project, kind)` 不接受 `completed`**：当前无调用方需要，未改；只记录。
5. **第一次 `-k` 运行的 12 分钟无输出**未定位原因（见第五节），不影响本次结论，但若反复出现，建议按只读诊断查 PTY 输出缓冲／GUI 令牌等待的结构化原因。

## 九、提交状态
未执行任何 git 写命令；未领号；未提交；未改 `project_status.md`。本结果文件为 pending 交付物，提交与轮次号由调度方决定。

## 独立验收（Claude，主工作区）

- 执行链：Codex group/group-4 一次完成（07:05，约 20 分钟）。收尾任务书为 verify-only，执行方未改生产代码和测试。
- 车道与主工作区三个文件逐字节一致（cmp）；`review_batch --lane perf2` PASS（4 个文件，0 失败 0 告警）。
- 主工作区复跑：`run_selftests -k storyboard_catalog storyboard_selection adopt` 35 条全绿；消费方 161 条全绿（test_file_cache、test_storyboard_plan_service、test_workflow、test_req_s03_anchors、architecture.test_project_context_boundary）；`smoke_test` 8/8；`smoke_test --architecture` 374 条中 1 条红，即已知的「R1746 欠一次完整安全全量」（test_full_safe_all_is_required_after_eight_source_rounds），与本批无关，由 post-commit 钩子后台补跑。执行方在车道里报告 374 条全绿，差异来自两棵树的全量凭据状态不同，已按实测记录。
- 诚实记录：新测试 test_storyboard_catalog_scan_count.py 的缺陷（缺 import json、基线夹具复用被改写的项目、基线用 HEAD 会在提交后失效）由调度方在被用户指出违反分发规则之前亲手修正，修正后的版本已由执行方在收尾任务中复核并全部通过；此后所有执行均改为派发。
- 去掉逐文件 resolve() 后的链接排除：执行方在临时目录实测目录联接点（指向项目外／指向内部）与文件符号链接均未被收录。
- 真 Tk 空项目打开分镜页：MainThread 的 _catalog 调用 0 次，后台线程 2 次。
- 现有测试断言未动；未新增 skip。
