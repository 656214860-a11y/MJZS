# R1346：O22 资产正典、变体与镜头引用提供变更影响视图

类型：功能轮（§3.1；本项为「建议」，本轮交付为实现＋回归）。承接 R1267 清单 O22（O01—O21 已完成）。中央轮次 1346。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k asset_impact asset_context asset_plan asset_detail asset_reference` 64/64；`test_todo_comment_snapshot`＋`test_unification_ratchet` 5/5；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O22 关闭，清单剩 O23—O48；1346 − 1341 = 5 ≥ 5，收口补一次干净 master 全量（结果见「收口安全全量」）。

## 目标（R1267 清单 O22）
- 依据：`stage_execution_service.py` 已有正典板、变体缩略图、资产计划、采用分镜等服务入口；`continuity_ledger.py` 已做漂移检查。
- 建议：修改发型、服装、场景光源、道具尺度时，区分全局正典修改与当前状态变体，展示引用镜头和需复核文件。禁止「一次编辑悄悄全项目换图」。
- 验收：改变体不覆盖正典；删除被引用资产给出引用列表；孤立资产可回收，被采用资产受保护。依赖 O18（已完成）、O39（未完成，属 storage_maintenance 子系统；回收／清理侧的强制执行留待 O39，本轮只做只读影响视图与保护标记）。

## 实现（`asset_plan.py`）
- `asset_impact(project, aid, *, episode_dir='')`：只读变更影响视图。返回 `aid`、`in_plan`（是否已在资产计划）、`adopted`／`orphan`／`protected`、`canon`（`board`＝`canonical_board`、`anchor`＝`character_anchor` 回退 `base_anchor`）、`variants`（`asset_contract.state_variants` 的 `state_id`/`name`）、`references`（`[{episode, shot, fields}]`，只统计采用分镜里的直接引用）、`files`（需复核的首帧文件，取采用镜头 `frame` 且文件真实存在）、`videos`（受影响且已生成视频的镜头编号，取自 `storyboard_catalog_service._generated_video_shots`）。全程 `plan_file`＋`read` 只读，不写盘、不改资产、不删文件。
- 非 `CHAR/LOC/PROP` 编号抛 `ValueError`（防止拿错编号做批量影响判断）。
- `deletion_references(project, aid, *, episode_dir='')`：删前引用清单，给引用镜头、需复核文件、`protected` 标记与一句人话 `summary`。
- `_adopted_storyboard_shots(project)`：只读遍历 `storyboard_adoption_contract.adopted` 的采用分镜，读不动或非 dict 就跳过。

## 实现（`asset_context.py`）
- `referencing_shots(shots, aid)`：与 `references(shot)` 同口径（先 `normalize_shot`），返回 `[{'id', 'fields'}]`，`fields` 说明命中字段；`_SHOT_REFERENCE_FIELDS` 固定「characters／props／first_frame_assets／location」四类引用位。未知资产命中为空。

## 实现（`stage_execution_service.py`）
- 新增 L3 门面 `asset_impact(project, aid, *, episode_dir='')` 与 `asset_deletion_references(...)`：桌面只经 L3 拿影响视图，L2 不直接对 UI 暴露。

## 实现（`asset_detail.py`）
- 详情页顶部说明追加只读影响提示：被几个采用镜头引用、需复核几个首帧、几段视频、几个状态变体，或「当前没有采用镜头引用（可回收）」。取不到影响就静默跳过（`except (OSError, ValueError)`），不阻断页面。
- 新增 `asset_impact_note(impact)` 纯函数（可单测）；未改任何控件生命周期与既有绑定。

## 验证
- `tests/test_asset_impact.py`（新）10 条：`ReferencingShotsTests`（命中字段命名、`location`/`props` 也可命中、未知资产不命中）、`AssetImpactTests`（受引用资产带镜头与首帧文件且 `protected`、孤立资产 `orphan` 可回收、`canon`/`variants` 只读回显、非法编号拒收、删除引用清单列出镜头并警示、孤立资产删除清单为空）、`VariantDoesNotTouchCanonTests`（写状态变体不覆盖正典键）。
- 定向 `-k asset_impact asset_context asset_plan asset_detail asset_reference` 64/64；注释快照＋统一棘轮 5/5（`asset_detail` 冻结关键词注释行号未平移）；架构门禁 312/312；默认冒烟 8/8，0 红。

## 收口安全全量
- 干净 master 工作树（`o07-fullsafe-master`，HEAD=75165e5）`run_selftests.py --all --safe` 第 1 次即绿：4610 条用例／410.3 秒／0 文件红（`test_desktop_startup_perf` 13.5 秒、`test_perf_baseline` 20.0 秒均已通过，未出现已知阈值抖动）；凭据刷新 round=1346、tree=3488e392，`last_full_safe_all_round` 刷到 1346。收口文档提交在绿凭据之后，文档树与凭据树不同树（同 O09/O10/O13/O17 口径）。

## 边界
- 影响视图「引用」只算采用分镜对资产的直接引用（`characters`／`props`／`location`／`first_frame_assets`）；`shot.costume_id` 视为状态变体选择，不计为对某项资产的引用，避免把换装当「引用了服装资产」。
- 只报告、不阻断：`asset_impact`／`deletion_references` 全程只读，不做删除、不加文件锁；回收／清理侧的强制执行属 O39。
- 删前保护只到「给引用清单并标 `protected`」，未改动 `storage_maintenance` 的删除语义（未命中 §5 删除语义升级项）。
- 未实发模型请求、未重启应用、未真实点击界面（`asset_detail` 三组 Tk 用例在 Tk 下已跑过）。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿；不在本轮修复。

## 已知抖动（归 O48）
- `test_desktop_startup_perf` 属耗时阈值断言，O05 两次全量里出现过抖动；本轮全量若再卡阈值，按用户 2026-10-12 策略定向复测 3 次取多数，记为已知抖动，不作本轮拦截条件。

[TASK_COMPLETE] 资产正典、变体与镜头引用提供变更影响视图：`asset_plan` 新增只读 `asset_impact`（正典 `canonical_board`／`character_anchor`、`state_variants`、被哪些采用镜头哪些字段引用、需复核首帧、受影响已生成视频、`orphan`／`protected`）与 `deletion_references`（删前引用清单＋警示），`asset_context.referencing_shots` 与 `references` 同口径，`stage_execution_service` 补 L3 门面，资产详情页顶部提示被引用/可回收；改变体不覆盖正典、删除受引用资产先给引用列表、孤立资产可回收（依赖 O18；O39 回收侧未完成）；新增 `test_asset_impact.py` 10 条，定向 64/64、注释快照＋统一棘轮 5/5、架构 312/312、默认冒烟 8/8，0 红；1346−1341=5≥5，收口补一次干净 master 全量。
