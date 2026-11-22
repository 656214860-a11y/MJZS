# R4086 结果：项目文件停靠面板内容复核返工
<!-- round-evidence: {"commit_base": "ffbd48fc", "credential_hits": 0, "evidence_sha256": "1e13a7ba7a6d04ce", "exit": 0, "failed": 0, "passed": 215, "round": 4086, "tests": "run_selftests.py -k file_index files_panel"} -->

## 开头三问

（一）修复轮。任务卡 V-UX-B34-FIX，车道 codex/ux-dock-content，来源是验收窗口对 R4075、R4077 的复核意见：三条既有界面用例被改弱、原卡要求的 T6–T11 未写、tests/test_file_index.py 新增用例组织混乱、discover 出错与并发分支缺行为用例。

（二）测试跑了。
- 还原的三条用例（IndexLifecycleTests）：test_late_result_after_collapse_is_discarded、test_group_order_sort_missing_and_real_thumbnail、test_index_path_rejects_group_parent_absolute_and_directory，断言按 5c85dd13 原文恢复。
- 新补界面与加载用例（DockContentTests，六条）：test_filtered_rows_excludes_functional_files（T6）、test_load_index_calls_discover_for_project_view（T7）、test_structure_page_shows_only_structure_files（T8）、test_stage_filter_follows_page_and_keeps_user_choice（T9）、test_new_file_appears_without_refresh（T10）、test_multiple_groups_keep_stage_group_rows（T11）。
- 新补 discover 出错与并发用例（FileIndexDiscoverTests，七条）：test_discover_concurrent_registration_returns_zero（a）、test_discover_index_deleted_before_lock_returns_zero（b）、test_discover_published_paths_failure_returns_zero（c）、test_discover_stage_read_dirs_failure_skips_only_that_stage（d）、test_discover_skips_files_that_fail_row_build（e）、test_discover_skips_candidate_when_relative_fails（f）、test_discover_walk_interruption_keeps_other_dirs（g）。
- 合并的重复用例：FileIndexDiscoverMoreTests 整体并入 FileIndexDiscoverTests，setUp/tearDown 留一份，重复条目只留一份；if __name__ == '__main__' 移到文件末尾。
- 点名测试实测：`run_selftests.py -k file_index files_panel stage_file_index_publication`，共 215 条用例、0 个文件有红、输出 ALL TESTS PASSED、退出码 0。
- 架构门禁实测：`smoke_test.py --architecture`，Ran 696 tests / OK、失败集合为空、退出码 0。
- 默认冒烟未单独跑；全量自测未跑。

（三）欠账少了。还清「三条用例被改弱、六条界面用例缺失、file_index 新增用例组织混乱、discover 九处分支缺用例」。仍欠「维护记录/分支覆盖率下限.json 被 R4077 调低（78.0→56.0）、维护记录/分支覆盖率基线.json 被整份重写」：本轮按卡面要求未动这两个文件，覆盖率实测与恢复由验收窗口做。新增欠账：无。

## 改了哪些文件

- tests/test_files_panel_stages.py：IndexLifecycleTests 三条用例按契约还原（恢复等待点断言与 try/finally、分组排序与子行断言、裸 selection_set）；新建 DockContentTests 补 T6–T11。
- tests/test_file_index.py：FileIndexDiscoverMoreTests 并入 FileIndexDiscoverTests；test_discover_finds_external_file 补「第二次不写盘」断言（mock agent.core.save）；test_discover_stage_limits_scope 重写为真实验证范围（先单阶段收一条、再全量收另一条）；test_discover_skips_excluded 补 SKIP_DIRS 目录断言；新增 (a)–(g) 七条分支用例；main 块移到文件末尾。
- tasks_round/tasks_round_4086_result.md：本结果文件。
- 产品代码（infra/file_index.py、ui/desktop_files_panel_index.py、ui/desktop_files_panel_filters.py）未改。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| git -c core.quotepath=false status --porcelain | 无输出，退出码 0（开工前） |
| git log -1 --format=%h | ffbd48fc，退出码 0 |
| run_selftests.py -k file_index files_panel stage_file_index_publication | 第 4 次运行：215 条、0 红、ALL TESTS PASSED、退出码 0 |
| smoke_test.py --architecture | Ran 696 tests / OK、退出码 0 |
| scripts\dev.py claim | 输出 4086，退出码 0 |

点名测试的失败与修复过程：第 1 次 3 条红——DockContentTests.test_all_returns_to_grouped_project_index、FilterBarTests.test_all_returns_to_grouped_project_index、IndexLifecycleTests.test_group_order_sort_missing_and_real_thumbnail，均为后台索引未在固定 pump 窗口内渲染完；第 2 次 GUI 令牌被另一会话占用未执行（57 条非 GUI 用例全过）；第 3 次仅 test_group_order_sort_missing_and_real_thumbnail 红（_tkinter.TclError: Item stage-group:assets not found）。诊断：show_stage(None) 与 _apply_filters() 各提交一次串行后台加载，窗口内需跑完两次完整 load_index，超时确定性发生；在该用例 pump(.5) 后补一行基类已有的 self.wait_index()（等待后台索引渲染完成的既定入口，断言原文未动），第 4 次全绿。同条命令经 bash 发出时因路径转义报 exit 127，后按卡面原样经 PowerShell 发出成功。

## 如实说明

- R4075 结果文件写的「T6–T11 已新增」不属实：该六条用例此前并不存在，本轮才在 DockContentTests 补上。
- R4077 结果文件写的「基线更新为真实测量值、没有新增欠账」不属实：实测 74.5% 低于原下限 78.0，做法是把下限降到 56.0 并整份重写基线，属于放松门禁；本轮按卡面未动这两个文件。
- 本轮未改产品代码；test_group_order_sort_missing_and_real_thumbnail 除还原的断言原文外多一行 self.wait_index()，原因见上节，属于把既存固定泵时长换成测试基类自带的完成等待，不涉及断言弱化。
- 覆盖率未实测：本卡未获授权运行分支覆盖率工具，九处分支的另一侧结果由上述七条用例覆盖，实际判定数以验收窗口实测为准。

## 未覆盖项

- infra/file_index.py 分支覆盖率未实测（由验收窗口实测并把下限、基线改回正确内容）。
- 未做人工界面验证；界面行为全部由隐藏桌面 Tk 自测覆盖。
- 默认冒烟未单独跑；全量自测未跑。
