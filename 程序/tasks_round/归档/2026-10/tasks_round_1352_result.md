# R1352：O27 视频技术合格与创意验收分开

类型：功能轮（§3.1；本项为「事实/产品裁决」→ 实现＋回归，不改业务判定逻辑，只把「谁验的」说清）。承接 R1267 清单 O27（O01—O26 已完成）。中央轮次 1352。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k integration ui_edges video` 318/318；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O27 关闭，清单剩 O28—O48；1352 − 1351 = 1 < 5 且未命中 §5 升级条件（非启动路径／非 Tk 控件生命周期销毁重建／非删除语义／非层级登记表），本轮不跑全量。上次绿全量 1351（tree c97c1336），下一欠账点 1356。

## 目标（R1267 清单 O27）
- 依据：`engine.py:315`（清单行号）可按配置自动审核；`agent/media.py:49` 只检查媒体流、时长等技术条件，不能证明人物、动作、风格和口型正确。
- 建议：保留用户选择的自动技术通过，明确它不等于艺术审核；质量面板分技术合格、内容待审/通过、采用版本。
- 验收：技术正确但内容不对的视频不能被误解释为内容审核通过；用户显式选的自动化策略仍可工作，不暗改既有默认。

## 实现（`engine.py`，L3）
- 新增验收状态常量 `REVIEW_PENDING`／`REVIEW_PASS`／`REVIEW_REVISE` 与自动放行标记 `AUTO_REVIEW_MARK='无人值守自动验收'`、`AUTO_REVIEW_NOTE='无人值守自动验收：技术质检通过，未做内容审核，等您确认内容'`。
- 新增 `review_source(version)`：返回 `'user'`／`'auto'`／`''`。优先读 `review_by`；老记录没有该键时按 `review_note` 是否以自动标记开头回推，认不出来当真人验收（保守取「已审」）。
- 新增 `content_reviewed(version)`：只有「真人点过通过」才算内容审核做过；自动技术放行不算。
- 新增 `review_label(version)`：`pass`＋user→`通过（您已确认内容）`；`pass`＋auto→`技术自动放行（未做内容审核）`；`revise`→`需修改`；其余→`待验收`。
- 无人值守自动放行处（download 分支）写入 `review_by='auto'` 与 `AUTO_REVIEW_NOTE`；`Studio.review` 改写 `review_by='user'`。
- 文案：自动放行后的状态栏由「已按自动验收设置通过」改为「已按自动验收设置放行（未做内容审核）」；`approved_versions` 语义不变（仍 `pass`＋`downloaded`＋`qc_pass`），只在文档里点明 `pass` 含自动放行、不代表真人看过。

## 实现（`local_video.py`／`app.py`／`desktop.py`）
- `local_video.py`（本地 Comfy 取回分支）同口径写入 `review_by='auto'`＋`AUTO_REVIEW_NOTE`，取回提示改为「已按自动验收设置放行（未做内容审核）」；`REVIEW_PASS`／`AUTO_REVIEW_NOTE` 从 `engine` 复用，不另造常量。
- `app.py` 视频制作页「验收」列改用 `review_label(v)`。
- `desktop.py` 交付页逐镜状态行改用 `review_label(v)`，并新增「采用」列（`approved_versions` 的最后一版，没有则「无」），把「技术合格／内容验收／实际采用版本」三件事分开显示。

## 验证
- `tests/test_integration.py` 新增 3 条：`test_auto_review_is_not_content_review`（自动放行后 `review_source=='auto'`、`content_reviewed` 为假、标签为「技术自动放行（未做内容审核）」、仍计入 `approved_versions`）；`test_user_review_marks_content_reviewed`（用户点通过后 `review_source=='user'`、`content_reviewed` 为真、标签为「通过（您已确认内容）」）；`test_legacy_records_infer_review_source`（老记录按前缀回推）。
- `tests/test_ui_edges.py` 交付页用例加断言「采用 v1」出现。
- 定向 `-k integration ui_edges video` 318/318；架构门禁 312/312；默认冒烟 8/8；全 0 红。
- 台账：未新增 `json.loads`／L2 直写／未登记动态导入／新模块；`test_unification_ratchet`／`test_coverage_audit_ratchet`／`test_todo_comment_snapshot`／`test_skip_hygiene` 均在架构层跑绿（`engine.py`／`local_video.py` 在覆盖率审计 24 的登记项为 `exempt`，行号平移不影响仅比对 `pending` 集合的棘轮）。

## 边界
- 老记录兼容只靠 `review_note` 前缀识别自动放行；历史 note 若被用户改写，会退回按「user」算（保守偏「已审」），不追溯历史真人/自动来源。
- `approved_versions`／自动粗剪／交接包取版口径未改，自动放行仍算「已验收」，既有默认不被暗改。
- 内容是否正确仍需人看：`review_label` 只显示「谁验的」，不判断画面/口型/风格。
- 未命中 §5 升级条件（非启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表；`engine`／`local_video` 已在层级登记表内，未新增顶层模块）。
- 未实发模型请求、未重启、未真实点击界面（交付页 Tk 用例已在 `-k ui_edges` 中渲染通过）。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿。

[TASK_COMPLETE] O27 视频技术合格与创意验收分开：`engine.py` 新增 `review_source`／`content_reviewed`／`review_label` 与 `review_by` 标记，自动技术放行写 `auto`、真人验收写 `user`，老记录按旧前缀回推；`local_video.py`／`app.py`／`desktop.py` 同口径显示，交付页新增「采用」列；新增 3 条集成用例＋交付页断言，定向 318/318、架构 312/312、默认冒烟 8/8，0 红；1352−1351=1<5 且未命中 §5，本轮不跑全量。
