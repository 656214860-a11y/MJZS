# 当前快照

## 2026-10-12：O33 完成，继续 O34

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O32 已完成，**O33 已完成（R1358）**，下一项 O34（交付包可独立检查、剪映交接能力如实标注，P2／建议，M/L）。
- O33（剪辑／交付统一采用版本、粗剪覆盖率与可恢复成片清单）：`engine.py`（L3）新增采用版唯一口径 `adopted_edit_version`（已下载＋技术合格＋已验收的最后一条，且文件在、内容与验收摘要一致；返回 `unapproved`／`missing`／`replaced`／`unreadable`）与界面事实 `adoption_summary`；`auto_edit_ready` 与 `assemble` 收敛到同一取版口径；`assemble` 记粗剪覆盖率 `coverage={included,expected,duration,skipped}` 并透传 `_encode`；`publish_edit_bundle` 改为先原子落盘可恢复清单 `edit_bundle.json`（成片名＋`master_sha256`＋`output_spec`＋qc＋来源清单＋coverage），再写 `qc.json`／`edit_manifest.json`，新增只读 `read_edit_bundle`；编辑页 `assembled_message` 报「已包含 N/M 镜／总时长／跳过」；交付页逐镜「采用」列改用 `adoption_summary` 并标「最新 vY 未采用」。见 [R1358](../程序/tasks_round/tasks_round_1358_result.md)。
- 验证证据：`tests/test_edit_adoption.py`（新）7 条＋`test_editing_page_controller`／`test_integration`／`test_ui_edges` 改动；定向 11/11、关联 115/115＋27/27＋14/14＋98/98、架构 312/312、`test_copy_rules` 14/14、默认冒烟 8/8，0 红。1358 − 1356 = 2 < 5 且未命中 §5，本轮不跑全量。**上次绿全量：1356（tree 006d0295、4749/4749、425.3 秒、0 红），下一五轮欠账点 1361。**
- 环境观察（与本轮改动无关）：主树 `程序/desktop.py` 工作树为 LF，而 `.gitattributes` 钉 `程序/desktop.py text eol=crlf`，故主树 `test_line_endings` 的 victims 用例红；干净 master 工作树按 checkout 为 CRLF，同一用例 16/16 绿。提交后 blob 归一化，不影响产物。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（本次在干净 master 工作树 `o07-fullsafe-master` 领到 1358）；`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（现为 1359）。
- 下一步：O34（`handoff_service.py` 输出有序媒体／JSON／说明但非剪映原生草稿；交付包要列成片、字幕、音频、来源版本、技术 QC、人工结论、许可资料、摘要与缺项，并加离线包完整性校验；只交接媒体时如实写「素材交接包」）。可复用 O33 的 `read_edit_bundle` 做成片来源核对。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
