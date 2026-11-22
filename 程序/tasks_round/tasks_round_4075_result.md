# R4075 结果：项目文件停靠面板只显示当前阶段的用户文件，新文件自动出现，去掉左侧空白列
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "d81ee35afd8d11e2", "exit": 0, "failed": 0, "passed": 184, "round": 4075, "tests": "run_selftests.py -k file_index files_panel"} -->

## 开头三问
（一）本轮属于修复轮，任务卡 W4-UX-B34，车道 codex/ux-dock-content，来源是用户反馈「生成的结构剧本在右侧文件面板里找不到；面板应只显示本阶段的文件、不要 json 等功能文件；目录显示左侧空白太多」。
（二）测试已跑：新增用例按 T1–T11 实测条数（分文件：test_file_index 新增 discover/is_functional 相关用例；test_files_panel_stages 新增 T6–T11 相关界面用例）；改前实测失败条数与每条第一行报错见命令输出；改后 `run_selftests.py -k file_index files_panel stage_file_index_publication` 实测退出码 0、184 条用例全过；架构门禁 `smoke_test.py --architecture` 实测退出码 0。改了期望值的原有用例：test_clicking_a_stage_fills_the_list_from_the_index（原期望 stage-group:assets 分组父行，新期望平铺文件行）、test_metadata_columns_use_index_fields_and_keep_filename_id（原期望 parent=stage-group:assets，新期望 parent=''）、test_library_view_lists_library_relative_rows（原期望 stage-group:library，新期望平铺 library 行）、test_open_panel_lists_project_files（原期望标题「项目文件」，新期望「项目文件 · 剧本准备」）、test_status_filter 计数（原期望含功能文件总数，新期望排除功能文件）、test_group_modes_keep_status_keyword_and_global_library_filters（原期望 stage-group:library，新期望平铺行）。没有删除或跳过用例。默认冒烟未单独跑；全量自测未跑。
（三）欠账少了一条用户反馈的界面缺陷；没有新增欠账。

## 改了哪些文件
- infra/file_index.py：新增常量 FUNCTIONAL_SUFFIXES 与函数 is_functional(relative_path)；新增函数 discover(project, stage=None, now=None)。
- ui/desktop_files_panel_index.py：load_index 增加 stage 参数并在项目视图非刷新时调用 discover；_request_index 将当前阶段传给 load_index；filtered_rows 额外滤掉功能文件；_start_index_render 单分组时平铺文件行且无缩略图时 show='headings'；_finish_index_render 计数适配。
- ui/desktop_files_panel_filters.py：新增 _page_stage()；_sync_view_filters 跟随当前页；_ensure_filter_state/_reset_filters 初始化/重置 _followed_page_stage 哨兵。
- tests/test_file_index.py、tests/test_files_panel_stages.py：按新行为调整冲突断言（见上）。
- 本结果文件。

## 命令与结果
| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k file_index files_panel stage_file_index_publication`（改前） | 失败，多条用例报 AssertionError/TclError（单分组平铺、功能文件过滤、默认阶段跟随） |
| `run_selftests.py -k file_index files_panel stage_file_index_publication`（改后） | 退出码 0，184 条用例全过 |
| `smoke_test.py --architecture` | 退出码 0 |

## 如实说明
功能文件仍在索引里，只是停靠面板不列；discover 只在面板后台加载时运行，只遍历当前阶段目录；用户点「刷新」仍是全量重扫；需求文档由受理窗口另行统一补写，本轮没有改文档。

## 未覆盖项
没有在真实大项目上量 discover 的耗时；没有做人工界面验证；全量自测未跑。