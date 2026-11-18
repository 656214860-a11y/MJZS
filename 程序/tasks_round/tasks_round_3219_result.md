# R3219 合并轮结果
<!-- round-evidence: {"commit_base": "d29e1e83", "credential_hits": 0, "evidence_sha256": "a0a838da3678c02d", "exit": 0, "failed": 0, "passed": 0, "round": 3219, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮（功能分支内整合，非 master 合入；对应《UI统一组件标准任务书》U0/U2/U3 的落地整合）。
- 三问：测试跑了（定向门禁＋默认冒烟，明细见下）；三个基线——冒烟 9/9、架构门禁本轮实跑全绿、全量欠账无新增（未触发全量条件，凭据状态见 §5 口径）；`project_status.md` 欠账无变化（本分支不写状态页）。
- 合入：`dsh-82c63326-f006`（尖端 3710f972＝R3164 U0 标准文档＋R3178 U2 图标画布＋R3195 U3 图标门禁）到 `dsh-876e046e-e055`（基 d29e1e83，master@R3213）。
- 冲突：`程序/scripts/build_nav_icons.py` 唯一冲突已消解，保留两侧逻辑（主导航 `render_icons()` 固定画布 ＋ M3 `render_stage_file_icons()` 自动裁边）。
- 合并树修订（原未暂存，已并入本合并）：`design_tokens.md`、`build_nav_icons.py`、`ui_components.md`、任务书、`test_nav_icon_size_boundary.py` 按 2026-11-17 裁决 D11/D12 对齐——主导航 PNG（`render_icons()` 字形表，含 `project_files.png`）固定 24×24；M3 的 13 个 `<stage>_files.png` 复合图标维持裁边并豁免尺寸门禁；U1 明确只迁三处试点；U3 冻结范围含 14 个缺图 emoji 回退＋回收站/清空/素材库旧符号＋视频封面空态。
- 门禁修订：`tests/architecture/test_icon_source_boundary.py` 基线与豁免随 T10 包路径更新——`desktop_shared_menus.py`／`white_model.py` 实体迁 `ui/`（顶层为门面）、`ui_icons.py` 实体迁 `ui/ui_icons.py`；改前该门禁在合并树 2 红（3 条字形误报＋1 条 PNG 路径误报），改后 6/6 绿。属测试定位同步，断言口径未弱化（仍按 AST 计数、只减不增）。
- 验证：`run_selftests.py -k nav_icon icon_source ui_icons agent_doc module_size taskbook` → 31/31 绿；`-k token_boundary` → 7/7 绿；`smoke_test.py` → 9/9 绿（含 gui_hidden --probe）。
- 未跑全量：本轮为分支内整合，未涉启动路径／Tk 生命周期／删除语义／层级登记表；合 master 前按 §5 另行触发。
- U0/U2/U3 验收勾选以合并树实测为准，未逐条追认分支旧报告（U0 原报告曾把 16135 字节误判低于 16000 门禁，R3178 已修）；剩余 U1/U4/U5/U6/U7 未完成。
- 提交：见 git log（merge-ci-exit 证据）。
