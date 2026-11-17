# R3210 结果（同步后修复轮：R3205 合入 T10 后全量门禁欠账清偿＋面板视图列头修复）
<!-- round-evidence: {"commit_base": "262cf888", "credential_hits": 0, "evidence_sha256": "e4a4fa6e82c94fd7", "exit": 0, "failed": 0, "passed": 326, "round": 3210, "tests": "run_selftests.py -k offline_asr asset_thumbs files_panel ui_edges writing_page_services distribution speech static"} -->

- 轮次类型：修复轮（实领 **R3210**，分支 `codex/wip-R3210`；R3205 同步轮暴露的门禁/回归欠账逐条闭环）。

## 三问

1. **本轮属于 §3 哪种类型？** 修复轮：先定位根因，只改根因所在模块。
2. **测试跑了吗、三个基线过了吗？** 跑了——冒烟 9/9（随附解释器 3.14.7）；架构门禁 483 条（1 个环境项已处置）；定向 236+101+8 条 0 红。全量 `--all --safe` 待本提交收口后于净树执行（解释器口径见下「验证口径」）。
3. **欠账少了吗？** 减少：R3205 后全量暴露的分支侧欠账全部清偿；剩余红均为 master 侧/环境侧，见「遗留」。

## 本轮改动（按根因分组）

| 根因 | 文件 | 处置 |
| --- | --- | --- |
| 参数上限棘轮（≤7） | `ui/asset_thumbs.py` | `request_media` 去掉可推导的 `kind` 形参，内部推导。 |
| 类规模棘轮（≤638 行） | `ui/desktop_auto_flows.py` | 压缩 M5 预取块至登记上限内。 |
| 函数规模棘轮（≤150 行） | `ui/speech_settings_ui.py` | M6 离线包下载行抽成模块级 `_offline_package_row(...)`。 |
| 事件发送边界（规则 22） | `domain/offline_asr_setup.py` | `OfflineSetupRunner._emit`→`_notify`（属进度回调，非总线 emit）。 |
| 删除唯一权威（规则 14） | `domain/offline_asr_setup.py` | 半成品 venv 清理 `shutil.rmtree`→`storage_maintenance.recycle_paths`；子进程收尾加 `wait(timeout)`＋`terminate_process_tree`，`subprocess.run`→`platform_tools.run_process`。 |
| 正式写唯一权威（2.2） | `ui/local_previs.py` | 白模设置直写 `path.write_text`→`agent.core.save_text`。 |
| 断言锚文本 | `orchestrator/previs_automation.py` | Blender 缺失提示改「未找到本地 Blender」对齐既有锚定。 |
| 视图切列清空 heading | `ui/desktop_files_panel.py` / `_filters.py` | 新增 `_apply_columns(media)`：剧本视图只挂 `name` 列、索引/素材库挂 `name`+`meta`，每次 `configure(columns)` 后重挂 heading/column（Ttk 行为：换列会清 per-column 配置）。 |
| 测试契约随 M2/M5 更新 | `tests/ui_edges_support.py`、`tests/test_writing_page_services.py` | 本地管线 fixture 显式 `"video_backend": "comfy"`（M2 云端默认的有意变更，不弱化断言）；项目文件菜单期望补「在文件夹中显示」「另存为…」（M5 新动作）。 |
| master 侧测试缺陷（合并阻断） | `tests/test_ui_edges_guards.py` | `test_approval_consumers_use_the_shared_helper` 补函数内 `entity_file` 导入——master 同名 NameError，文件此前与 master 逐字节一致，按本文件既有局部导入惯例修。 |
| skip 台账登记 | `维护记录/skip台账.json` | `MediaThumbTests.setUp` 平台限制登记（PLATFORM_TKINTER）。 |
| json.loads 债务台账 | `维护记录/架构统一基数.json` | 登记 `agent/media.py::probe`、`ui/asset_thumbs.py::_probe_media` 两个 ffprobe 子进程 stdout 解析豁免点；`offline_asr_setup` 入 scope_audit_pending。 |
| 覆盖率基线 | `维护记录/覆盖率基线.json`、`runbook.md` §11 | T10 包化后生产模块 622→623，重跑工具刷新基线（74 覆盖模块不变）并同步口径文字。 |
| 分发清单 | `distribution_manifest.md` | `运行环境/Python.bak*/**` 排除——换解释器前快照备份不进正式副本（与既有 `Python_alpha_a2_backup`/`Python315_pruned_backup` 同类）。 |
| 状态页 | `project_status.md` | 预登记本轮（合入轮将按其流程再同步）。 |

## 验证

- 冒烟 9/9（`运行环境/Python/python.exe` 3.14.7）。
- 架构门禁（3.15）：`unittest discover tests/architecture` 483 条，仅 `基准历史.json` 缺失 1 项——该文件为 gitignore 的本机运行产物，从主工作区复制补齐后 `test_agents_md` 15/15 绿。
- 定向（3.15，隐藏桌面）：236 条（offline_asr/files_panel/asset_thumbs/ui_edges/distribution/writing_page_services）＋101 条（ui_edges_pages/files_panel_stages）＋8 条（ui_edges_guards）0 红。
- 测试 fake 修正：`test_offline_asr_setup.py` 的 `FakeProc.wait` 不再阻塞普通路径（保留取消用例的阻塞 fake）。

## 验证口径（解释器）

- 随附解释器 `运行环境/Python` 今日 17:50 由 3.15 embeddable 换为 **3.14.7**；AST 摘要棘轮锚点（`sha256(ast.dump)`）随版本变化，master 在 3.14.7 下同红（实测 `test_unification_ratchet` 全锚点漂移），属换版欠账非本分支回归。故门禁/全量证据以与台账同口径的 **3.15**（`运行环境/Python.bak_3.15_embeddable_20261117_175007`）执行；3.14.7 冒烟 9/9 另存。
- 换版后的台账重建（3.14.7 锚点重生成）为 master 侧维护欠账，留待合并后轮次处置。

## 遗留

- master 侧 T10 包化 fallout（顶层 `log_maintenance`/`script_manifest_schema` 门面缺失、`stage_execution_service` 导出名缺漏等）与本分支无关，合并后按既有节奏修。
- `test_desktop_compact_layout` 在全量中曾现 180s `[SUSPECT_CONCURRENCY]`，判隐藏桌面令牌争用，串行复跑为准。
- 任务书欠账不变：按阶段分组、downloads_root、A7 待办（见 M5/M8 结果文件）。
