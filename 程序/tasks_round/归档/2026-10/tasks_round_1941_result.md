# R1941 结果（修复轮）：会员账号页引入的两条架构红

- 推荐线路「复制地址」改走共享复制入口 `Desktop.copy_text`（经 `prompt_window.copy_text`），不再直接写剪贴板；失败时由入口显示“复制失败：…”。
- `Desktop` 类行数回到 1302（压缩一处三行注释为两行），未抬高登记值；断言未动。
- 已运行：`--layer architecture --all`（`copy_entry_boundary`、`Desktop` 类行数转绿）；`-k account_security account_client account_page account_entry` 全绿。
- 未解决（非本车道）：`pet_ui_voice.py::PetVoiceMixin` 1127 行 > 上限 1119，来自 R1926（启动画面/三虎开机招呼），需该车道拆类。
- `test_round_number_continuous` 在本结果文件落地前为 1939≠1938，属领号时序，合入后复核。
