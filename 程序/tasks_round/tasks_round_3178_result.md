# R3178 结果（UI 统一组件标准任务书 U2：固定图标画布）
<!-- round-evidence: {"commit_base": "72807cb0", "credential_hits": 0, "evidence_sha256": "f960de0672623fb8", "exit": 0, "failed": 0, "passed": 76, "round": 3178, "tests": "run_selftests.py -k nav_icon_size ui_icons test_video_ui"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮。仅处理任务书 U2 的 24×24 固定画布、全部导航图标重生、尺寸门禁、侧栏视觉核验。
2. **测试跑了吗、三个基线过了吗？** 默认冒烟 `smoke_test.py` 9/9；图标与视频页定向 76/76；侧栏布局与图标定向 18/18。恢复本机固定提交技能包后 `-k skill_reference_injection skills idea_chat` 320/320；规则预算门禁 5/5；临时截图脚本清理后覆盖率两项转绿。完整架构门禁复测 485 项、仅 `test_round_number_continuous` 1 红（本分支状态页 3176，结果文件最新 R3178 应为 3179；只允许 master 提交状态页，待合并轮同步后复验），其余 484 项绿。首次受影响回归 1462 条／9 文件红：空技能 gitlink 及返回图标 RGB；恢复依赖、保留原断言修复 RGB 后，`smoke_test.py --affected ui_tokens ui_icons build_nav_icons` 复测 **1462/1462、0 红、0 跳过**（串行 891.5 秒）。完整安全全量未运行、无本树绿凭据；架构唯一的分支状态页红灯留待 master 合并轮。
3. **欠账少了吗？** U2 没新增存量豁免；全部 `assets/nav/*.png` 固定为 24×24。历史全量欠账未清零。

## 改动和证据

- `ui_tokens.NAV_ICON_SIZE = 24` 对齐 `design_tokens.md` 的 `icon.nav.size`；`scripts/build_nav_icons.py` 在字体高采样后按透明边界约束字形、保留原墨水 RGB 与抗锯齿 alpha，居中放入固定画布；重生全部 26 张 PNG。原始图标中存在 27×28、28×26 等不统一尺寸；现文件头检查 26/26 为 24×24，alpha 边界在画布内。`back.png` 的既有主题色像素回归曾因缩放插值红（11,106,195 vs 15,111,192），改为重着色后不修改断言，视频页相关定向 76/76。
- `tests/architecture/test_nav_icon_size_boundary.py` 检查每个 PNG 的 IHDR，并以坏尺寸头样本自审，无豁免。首次红（原资产非固定画布），重生后绿色。`architecture.md` 同轮登记新增门禁；清单与测试文件一致性定向 3/3。
- 100% 与 125% 的真实 Tk `Desktop` 使用临时测试项目、隐藏桌面、窗口句柄抓图；只截 96px 侧栏，证据分别为 `tasks_round/evidence/R3178_sidebar_100.png` 与 `R3178_sidebar_125.png`。实测 `tk scaling` 约 1.332／1.664；13 个阶段图标与项目分组、设置图标在两档均按列对齐，未见裁边。含测试项目正文的完整窗口截图已从忽略的 `logs/` 清理，不入库。既有真 Tk 侧栏布局／按钮测试 18/18。
- 测试环境：本功能工作树的 3 个 gitlink 初始为空，且被忽略的 `维护记录/基准历史.json` 缺失；依仓库 `scripts/auto_full_safe.py` 的 `_fill_embedded_repos`／`_fill_ignored_inputs` 显式清单从本地主工作区补全。固定提交包检查 3 包／0 问题；补全仅作测试依赖，不暂存。恢复后技能引用／聊天／技能数定向 320/320，原环境红消失。
- 先前的 `logs/u2_capture.py` 临时脚本被覆盖率扫描误算作生产模块，使覆盖率基线 716≠715。按精确路径删掉本轮临时脚本与含测试项目正文的完整窗口截图，仅留裁剪侧栏图；原失败两项复测 2/2。未修改覆盖率基线或扫描断言。
- U0 文档补正：R3164 的 `AGENTS.md` 实际 16135 字节超出 `test_agent_doc_budget` 的 **16000** 字节门槛。将规则 34 压缩为一行等义指针，仍明确 token 取值与组件／门禁权威；当前 16000 字节，预算门禁 5/5。该补正与并行 U1 草稿同文，合入时只保留一次；R3164 原报告误勾选将在 U0 合并收口时如实更正。

## 尚待收口

- 受影响消费者回归已 1462/1462 通过；合并轮同步 `project_status.md` 后复验轮次连续性门禁。
- U2 仅在功能分支完成；整份任务书尚缺 U1 和 U3–U7，完整安全全量与合入 master 未执行。
- U1 草稿在另一工作树未提交，本轮不触碰；U3–U7 尚未执行。

## 提交

分支提交：本轮源码与定向／受影响消费者回归已过，架构唯一 `test_round_number_continuous` 须合并轮同步状态页后复验；提交 hash 以本分支 Git 日志为准。主干尚未合入，未宣称整份任务书完成。
