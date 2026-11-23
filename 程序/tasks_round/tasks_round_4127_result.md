# R4127 结果：登记的空壳项目目录按失效登记找回、清除与重建不误留
<!-- round-evidence: {"commit_base": "89fdb829", "credential_hits": 0, "evidence_sha256": "fc4e2dcbc76eba7b", "exit": 0, "failed": 0, "passed": 185, "round": 4127, "tests": "run_selftests.py -k project_open project_rename_reconcile project_recovery projects core project_switch_guard"} -->

## 开头三问

- （一）本轮属于哪种类型：功能修复轮（缺陷修复）。任务卡 W6B-UX-D2B（波次 W3），车道 `codex/ux-project-library-missing`，工作树 `.agents/worktrees/dist-manifest-declare`，基准 `89fdb829`。接 UX-D2A（R4097）：登记的项目文件夹还在、但里面没有 `config.json`（空壳）时，打开报「无法打开」，登记无法找回也无法清除。本卡让空壳与「文件夹不在了」的登记同路：打开时自动接回，选择窗口可重新查找或手动指定，可只清登记不动磁盘，删除前先提醒，重建索引不误留。
- （二）测试跑了吗、三个基线：先在 89fdb829 上跑点名测试做基准：6 个文件 170 条全绿。加 15 条新用例（三个既有测试文件内追加，无新文件）后未改实现先跑红：185 条里 3 个文件有红，红项全部是新用例（reconcile 文件 10 处、open 文件 7 条、recovery 文件 2 条）。实现后同一命令 185 条全绿；点名回归（desktop_startup_perf/ui_batch3/ui_batch4）28 条全绿；架构门禁 700 条全绿，失败集合为空。默认冒烟未单独跑；全量自测未跑。
- （三）欠账少了吗：少了一个真实缺陷（空壳登记卡死：打不开、找回不了、清不掉）。没有新增欠账，没有动任何门禁的阈值、基线和登记表。

## 改了哪些文件

- `domain/projects.py`：新增 `project_dir_openable`（目录存在且含 `config.json` 才算能打开）与 `recognizable_project_dir`（库一级内可识别为项目：有 config 或阶段目录、回收站不算）。`reconcile_missing`（模块函数）把「目录不在」和「只剩空壳」都收进失效清单；候选排除登记自身与被其他能打开登记占着的目录；返回新增 `unregistered`（未登记的可识别目录）供手动指定。新增 `manual_claim_error`（手动指定逐项拒绝：不存在／自身／回收站／库外／已登记／不可识别）、`shell_rescue_dirs`（删除前只读提示）、`claimed_registration_notice`、`missing_project_open_error`／`empty_shell_open_error`（空壳报「没有项目配置文件…留下的空壳…重新查找项目」）、`is_empty_shell_open_error`、`EMPTY_SHELL_OPEN_NOTICE`、`_registration_kept`（重建保留判定：库内留可识别目录、库外留能打开的）。`needs_cleanup_after_open_error` 扩到壳句子但明确不认 engine 原句。`_claim_reconciled` 拒认已登记目录。`Projects.reconcile_missing` 加 `manual` 参数、可打开登记直接回 `none`。`clear_missing_registration` 判定从「目录存在」改为「能打开」。`rebuild_registry` 保留判定改 `_registration_kept`。几处弯引号按界面口径统一「」。
- `desktop.py`：`load` 的失效分支判定改 `project_dir_openable`，并且只对**已登记**的路径走找回（未登记路径照旧交 `open_studio` 报引擎原句，避免误伤任意路径调用）；认领成功提示改 `claimed_registration_notice`（原壳还在时说明它没有动）；仍打不开时报 `missing_project_open_error`（壳和目录不在各一句）。
- `ui/desktop_project_pages.py`：`project_row_text` 空壳行标「没有项目配置文件，可重新查找或清除登记」，与「目录已失效」分开。`open_project_or_cleanup` 与选择窗 `enter` 对壳报空壳提示而非「剧本已删除」。选择窗「删除选中项目」对空壳先警告（建议先取消、列出尚未登记的项目目录），仍继续只清登记不动磁盘。「重新查找项目」对能打开的登记回「还在原位」，无指纹匹配时把未登记目录摆成手动指定选项（`manual=True` 走逐项校验）。`_cleanup_project_path` 为壳时顶部提示用空壳句子。`clear_missing_project` 判定同步 `project_dir_openable`。
- `docs/specs/04_数据与本地存储.md`：新增 §2.4「项目登记与失效找回」：能打开判据、两种失效形态、找回扫描范围与候选排除、手动指定校验、清除登记与重建索引语义、失效目录绝不写入/移动/删除。
- `tests/test_project_rename_reconcile.py`：新增 `EmptyShellReconcileTests` 6 条（壳自动认领不动磁盘、双候选确认态、残壳不自匹配、无匹配列未登记目录＋手动认领、五类非法目录逐项拒绝、被占候选排除＋直接认领拒认）。两处既有用例夹具随契约同步：`test_unchanged_project_keeps_valid_picker_and_opens_normally`、`test_existing_project_is_not_cleared` 的「有效项目」补写 `config.json`（断言一字未动；裸目录在新契约下本就是空壳，见如实说明一）。
- `tests/test_project_recovery.py`：新增 `EmptyShellRegistrationTests` 2 条（清壳登记只动登记且文件原样、可打开项目仍拒清；重建丢纯壳留残缺项目并保状态）。
- `tests/test_project_open.py`：新增 `EmptyShellOpenTests` 7 条（壳自动接回并先刷新选择器、无匹配报壳句子且不向壳写文件、行文字三态、删除警告取消全保留、`open_project_or_cleanup` 壳措辞、选择窗 enter 壳提示、可打开登记重新查找回「还在原位」）。
- `tasks_round/tasks_round_4127_result.md`：本文件。

## R1–R11 做到没有

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| R1 空壳按失效登记同路找回 | 做到 | `project_dir_openable` 入 `reconcile_missing` 失效清单与 `load`/`enter`/`open_project_or_cleanup` 判定；`test_desktop_load_claims_shell_*` |
| R2 候选排除（自身／他登记占用／回收站／不可识别） | 做到 | `recognizable_project_dir`＋`p==old`＋`held`；`test_partial_shell_is_missing_and_never_matches_itself`、`test_candidate_held_by_openable…` |
| R3 单一候选自动认领 | 做到 | `len(choices)==1` 分支；`test_empty_shell_auto_claims…` |
| R4 多候选确认态 | 做到 | `state='confirm'`；`test_empty_shell_with_two_candidates_returns_confirm` |
| R5 无匹配列未登记目录手动指定 | 做到 | `unregistered` 字段＋手动选择器；`test_missing_match_lists_unregistered_dirs…` |
| R6 手动认领逐项校验 | 做到 | `manual_claim_error`；`test_manual_claim_rejects_each_invalid_directory`（5 子用例） |
| R7 认领更新登记与引用、壳原样 | 做到 | `_claim_reconciled`＋`_sync_desktop_project_paths`；用例守 `dir_listing` 不变、壳仍在 |
| R8 清壳登记只动登记；可打开仍拒清 | 做到 | `clear_missing_registration` 判定改 `project_dir_openable`；`test_clear_missing_registration_keeps_shell_files…` |
| R9 重建丢纯壳、留残缺、不误加 | 做到 | `_registration_kept`＋`known` 排除；`test_rebuild_registry_drops_pure_shell…` |
| R10 打开报可执行提示＋「重新查找项目」、不向壳写文件 | 做到 | `empty_shell_open_error`/`EMPTY_SHELL_OPEN_NOTICE`；用例守目录清单不变、提示含「重新查找项目」 |
| R11 删除先警告建议取消、取消全保留；引号统一 | 做到 | 选择窗删除分支警告＋`shell_rescue_dirs`；`test_delete_selected_project_on_shell_warns_and_cancel_preserves`；用户可见句中弯引号改「」 |

## 命令与结果

以下命令都在车道的 `程序` 目录下跑（git 类在车道根），全部直接执行、无权限拒绝。

| 命令 | 结果 |
| --- | --- |
| `git status --porcelain` / `git rev-parse HEAD` / `git branch --show-current`（开工核对） | 工作区干净 / `89fdb829…` / `codex/ux-project-library-missing` |
| `python.exe -B run_selftests.py -k project_open project_rename_reconcile project_recovery projects core project_switch_guard`（基准，改动前） | 退出码 0；「共 170 条用例…0 个文件有红」237.5 秒「ALL TESTS PASSED」（GUI 令牌排队属环境等待，非失败） |
| 同上命令（新用例写完、实现未改，跑红） | 退出码 1；「共 185 条用例，116.2 秒；3 个文件有红」：reconcile ✗10、open ✗7、recovery ✗2，全部是新用例 |
| `python.exe -B -m py_compile domain\projects.py desktop.py ui\desktop_project_pages.py tests\…（三个测试文件）` | 退出码 0 |
| 同上点名命令（实现后，跑绿） | 退出码 0；「共 185 条用例，6.8 秒；0 个文件有红」「ALL TESTS PASSED」 |
| `python.exe -B run_selftests.py -k desktop_startup_perf ui_batch3 ui_batch4`（回归） | 退出码 0；「共 28 条用例，27.3 秒；0 个文件有红」「ALL TESTS PASSED」（after 回调噪音属已销毁控件的正常 Tcl 回显） |
| `git status --porcelain` / `git diff --numstat` / `git diff`（自查） | 退出码 0；7 个文件（不含本文件），553+/44-；范围＝3 产品文件＋1 文档＋3 测试文件 |
| `python.exe -B smoke_test.py --architecture` | 退出码 0；「Ran 700 tests in 433.622s」「OK」「✅ 架构治理测试：tests/architecture」 |
| `python.exe -B 维护记录\基准脚本\round_claim.py next` | 领到轮次 4127 |
| `python.exe -B scripts\dev.py commit -m "R4127: …" --tests project_open project_rename_reconcile project_recovery projects core project_switch_guard <七文件>` | 见下方提交记录 |

跳过：1 条既有登记位（`test_core.ValidateProfileTests.test_stage_profile_wrong_preset_rejected`，发行包未含受测 bundled skill，存量跳过，非本轮新增）。

## 如实说明

- （一）两处既有用例夹具随契约同步（断言一字未动）：`test_unchanged_project_keeps_valid_picker_and_opens_normally` 和 `test_existing_project_is_not_cleared` 原来用「只建目录、没有 `config.json`」当「有效项目」；新契约下那正是空壳，按本卡定义必须走找回/可清。补写 `config.json` 让夹具恢复「能打开的有效项目」本意，断言保持不变。属 §2.4 契约变更的同步定位。
- （二）`load` 的找回与报错只对**已登记**路径生效：`test_asset_thumbs`（`mock.Mock()` 宿主＋裸目录）与 `test_a_missing_folder_is_caught_before_anything_else`（`SimpleNamespace`＋不存在路径）这两处不可改文件都要求未登记路径照旧落到 `open_studio` 报引擎原句（engine 的「目录不存在或已被移动：路径」与「没有项目配置文件 config.json」已满足两处断言）。已登记空壳仍走找回并抛本模块的壳句子，两条新用例守着。
- （三）`needs_cleanup_after_open_error` 认本模块的壳句子（含「没有找到可以自动接回的项目文件夹」），不认 engine 原句：engine 句走「无法打开项目」弹窗，本模块句才走清理/找回提示，用例 `test_desktop_load_on_shell_without_match_reports_shell_sentence` 显式守这个区分。
- （四）项目首页右键菜单的「删除项目及全部素材…」对空壳仍是回收站语义（可恢复），未加警告；卡面点名的删除警告落在项目选择窗口的「删除选中项目」。壳被回收后指纹匹配不受影响（匹配对候选目录配置里的引用比对，不靠壳内容）。
- （五）`_project_item_menu` 的「只清除失效项目登记」仍只对目录不存在的登记显示（沿用 `Path.exists()` 判断菜单项显隐）；空壳经选择窗「删除选中项目」确认后可清登记，两处入口行为一致但入口不同，未扩大。
- （六）界面未实际点过：选择窗/提示文字由隐藏桌面自测经真 Tk 树与按钮回调断言（文字取自 `textvariable` 与 `confirm` 调用参数）。

## 未覆盖项

- 未跑全量自测、未跑默认冒烟（卡面未点名）；未 push、未 merge、未动主工作树。
- 已被建出来的存量空壳文件夹本卡不清理、不移动（卡面明确产品代码不做删除/移动）。
- 未登记路径在目录不在/缺配置时的提示沿用 engine 原句（无「重新查找项目」引导），与改动前一致，未扩大。
- 选择窗删除警告只在项目库存在未登记目录时附清单；库内无可认领目录时只给建议取消＋清除登记选项。
