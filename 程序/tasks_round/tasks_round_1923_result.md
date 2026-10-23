# R1923 结果：结构治理轮（八维度清理 · 首批）

- 本轮类型：结构治理轮（瘦身）。分支 `codex/wip-slim-1`，从 master `4a65c2bd` 切出。
- 原则：不改行为；断言未动。

## 改动及等价理由

- `storyboard_selection.paths`：与 `storyboard_adoption_contract.paths` 函数体逐字等价（ast 归一化哈希相同，且两处 `resolve_source` 是同一个对象），改为从后者导入同名；`storyboard_selection.paths` 对外名字保留。
- `app.py`：播放按钮可用性的计算抽成模块级 `play_ready(app, selected)`，逻辑原样搬出。目的：`App` 类行数 1393→1388，修复 R1914 引入的 `architecture.test_complexity_ratchet.test_class_size_does_not_grow` 红（上限 1388）。

## 八维度摸底结论（仅扫描，未改）

- AI 废话：规则扫描无叙述性注释、无注释掉的代码、无占位符；命中均为业务文案，本维度无可做项。
- 去重：ast 归一化哈希找到 6 组完全重复的函数。已处理 1 组；`_require_gateway`（idea_chat／idea_transcript）被 `tests/architecture` 按源码文本固定为各模块自带，未动；`_configure_table_style`、`automatic_decision`、`child_environment`、`number` 留待人工确认。

## 测试

- `run_selftests.py -k storyboard_selection storyboard_adoption req_s04 storyboard_catalog complexity_ratchet video_prompt prompt_controls`：全绿。
- `--layer architecture --all` 本工作树 4 红：`complexity_ratchet` 已由本轮修；`test_agents_md`（缺 `维护记录/基准历史.json`）与 `test_skill_reference_injection`（缺外部 SKILL 文档）是工作树缺未入库文件，非本轮造成；`test_round_baselines`（状态页轮次头 1922 与结果文件号不连续）属 master 状态页，待合入后在 master 补记。
- `--all --safe` 未运行。

## 待人工确认
`_configure_table_style`（desktop_asset_pages／desktop_storyboard_page）、`automatic_assemble_decision`／`automatic_decision`、`child_environment`／`_worker_environment`、`episode_contract.number`／`writing_quality._number`。
