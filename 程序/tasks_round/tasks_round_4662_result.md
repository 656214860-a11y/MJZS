# R4662 结果
<!-- round-evidence: {"commit_base": "18798d976", "credential_hits": 0, "evidence_sha256": "22218d05f30bb6e9", "exit": 0, "failed": 0, "passed": 384, "round": 4662, "tests": "run_selftests.py -k test_ui_style_engine test_files_panel_stages test_desktop_compact_layout test_ui_batch3_shell test_ui_batch6_pages test_desktop_page_nav test_desktop_script_pages test_desktop_writing_page test_animatic_page test_board_assets_buttons test_media_page_buttons test_script_page_layout"} -->

- 轮次类型：功能轮。用户把主窗口最小尺寸定为 1024×600（方案 A），不改「工作区放不下时最小尺寸随首次窗口收缩」。
- 测试：跑了。默认冒烟 9/9 通过。定向重跑 `test_ui_style_engine`、`test_files_panel_stages`、`test_desktop_compact_layout`、`test_ui_batch3_shell`、`test_ui_batch6_pages`，共 258 条，0 红。架构门禁未单独跑，留给合并出口。全量未跑。
- 欠账：没有减少。本轮不改全量凭据。

## 契约

`DESKTOP_LAYOUT` 最小宽度 800→1024，高度仍为 600。默认尺寸仍是 1280×900。只改主窗口夹具；裸 Tk、弹窗和阶段面板的 800/880 尺寸不动。

接到 R4661 时，文件面板筛选条已改成单行（无类型框、排序框）。窄窗断言改为：1024×600 下分组按钮与搜索框仍同行，且不恢复已删除的下拉框。

## 验证

- 隐藏桌面：`run_selftests.py --serial -k` 上述五个文件，ALL TESTS PASSED。
- 默认冒烟：`smoke_test.py`，9 项通过、0 项失败。
- 架构门禁：未运行。
- 全量 `--all --safe`：未运行。
