# R3149 结果（全量红修复第一切片：面板打开文件的测试替身兼容）

- 轮次类型：修复轮（分支 `codex/wip-R3148`）。

## 三问

1. **本轮属于 §3 哪种类型？** 修复轮（修 R3137 引入的回归）。
2. **测试跑了吗、三个基线过了吗？** 定向跑了。`test_writing_page_services` 已由红转绿；`test_script_workspace_results` 仍 3 条红（见下），本轮未跑冒烟与架构（小改动，下次合并轮 CI 覆盖）。
3. **欠账少了吗？** 少 1 项：`test_writing_page_services.test_open_script_file_uses_injected_open_path` 的 `SimpleNamespace` 无 `root` 属性回归已修。

## 改动

`ui/desktop_files_panel.py`：`open_script_file` 解析项目相对行 id 时改用 `getattr(self.page, 'root', None)`，无项目（测试替身）时按原样处理——保留「索引行可打开」的能力，同时不假定宿主一定有 `root`。

## 仍未解决的全量红（下一轮继续）

| 测试文件 | 现象 | 初步判断 |
| --- | --- | --- |
| `test_script_workspace_results`（3 条） | `no logs of level ERROR or higher triggered on script_workspace_service` | 断言依赖该模块在失败路径上打 ERROR；包化后模块名变为 `domain.script_workspace_service`，以及改名路径里我新增的索引更新失败只记 DEBUG——需逐条确认是「日志名变了」还是「该打的日志没打」 |
| `test_recycle_directories` | 待定位 | 疑与 R3122 保留期/清空改动有关 |
| `test_white_model_identity` | 重命名/移动保持同目录 | 疑为他车道既有红，需在干净 master 上复现确认 |
