# L0–L5 制作链路集成 E 卡验收记录


## 实现位置

| 验收点 | 实现位置 | 口径 |
| --- | --- | --- |
| 提交输入指纹 | `domain/video_staleness.py`；`domain/video_source_evidence.py`；`orchestrator/engine.py`；`local_video.py` | 云端／本地提交时写入 `input_signature`；原 payload / graph `signature` 的既有语义保留。证据含后端、镜头画面字段、声音与白模开关、首帧 sha256、实际勾选参考资产编号与图片 sha256。 |
| 过期判定 | `domain/video_staleness.py`；`domain/storyboard_catalog_service.py` | 只读现算，不落“过期”状态，不自动重做；内部状态分 `missing / legacy_unknown / stale / current / revise / generating`。项目本地与云端工作集版本合并后取最新已下载版本。 |
| 资产使用情况状态契约 | `domain/asset_plan.py` | `asset_usage` 对外沿用原契约：最新成品为 `generated`；内部 `current` 只在边界处映射，不改调用签名。 |
| 历史无签名记录 | `domain/video_staleness.py`；`ui/video_progress.py`；`ui/asset_detail.py` | 无 `input_signature` 不强判过期、不冒充最新；显示「历史版本无法判定」，避免全量旧版误报为过期。 |
| 视频页状态展示 | `ui/video_progress.py`；`app.py` | 状态列在已下载任务上叠加「输入已过期」「历史版本无法判定」「视频文件缺失」；`app.video_display_state` 保持已使用导入路径与调用签名。 |
| 受影响列表 | `domain/asset_plan.py`；`ui/video_progress.py`；`ui/asset_detail.py` | 资产详情「使用情况」逐镜显示首帧三档与视频成品状态，并把「输入已变化的镜头视频」限定到该资产引用镜头。 |
| 批量重做入口 | `orchestrator/media_page_controller.py`；`app.py`；`orchestrator/engine.py` | 「批量需修改」复用既有 `review_many`；`App.review_checked_revise` 保持原调用签名，业务文本在媒体页控制器。之后仍由既有「批量生成勾选镜头」筛选可返工镜头。无自动重提。 |
| 规格09修正 | `docs/specs/09_资产数据生命周期.md` | §8、§9、§12、Q5 已按实现实况更新；原「持久过期标记」修正为「提交输入指纹落盘＋过期状态只读现算」。 |
| 结构门禁适配 | `ui/video_progress.py`；`orchestrator/media_page_controller.py`；`domain/video_source_evidence.py`；`domain/storyboard_storage.py` | 新展示与批量行为移至既有视频进度组件／媒体页控制器／视频来源证据模块；当前分镜来源解析下沉到既有无环存储快照模块，目录服务只作兼容转发；未调高 app、asset_detail、engine 的行数或类行数门槛。 |

## 回归测试位置

- `tests/test_video_staleness.py`：签名稳定、默认开关归一化、展示性字段不误报、提示词/首帧/资产图变化、云端与本地资产选择、历史无签名、缺失/过期/需修改/最新状态、受影响镜头列表。
- `tests/test_asset_impact.py`：`asset_usage` 的 `generated/stale/legacy_unknown/missing/generating` 状态与 `stale_videos`；其中 `test_current_signed_video_marked_generated` 锁定对外 `generated` 契约，过期列表限定本资产引用镜头。
- `tests/test_asset_detail.py`：资产详情使用情况块显示视频过期、历史无法判定、文件缺失与受影响列表。
- `tests/test_video_revision.py`：两端提交写入 `input_signature` 且本地指纹按实际上传回执逐字复算；旧 payload/graph `signature` 保留；「批量需修改」复用 `review_many`、保留高亮行回退提示；空目标拒绝；视频页状态文案。

## 验证记录

本轮按用户说明不由当前会话等待命令授权；定向回归、冒烟、架构门禁与 Control 复核结果待 Control 更新。当前会话未运行测试，不能声称测试通过。

建议命令（工作目录 `程序/`）：

```powershell
..\运行环境\Python\python.exe -B run_selftests.py -k video_staleness asset_impact video_revision asset_detail
..\运行环境\Python\python.exe -B smoke_test.py --affected video_staleness asset_plan storyboard_catalog_service keyframe_evidence engine local_video app asset_detail media_page_controller video_progress video_source_evidence
```

## 真实验收证据盘点（PRD §6／§10）

| 项目 | 项目内现状 | 结论与具体依赖 |
| --- | --- | --- |
| 授权样本 | `维护记录/基准脚本/business_quality_baseline.py` 只有 3 个初筛故事＋1 个留出故事的待执行模板；`程序/验收证据/` 不存在 | **缺失**。需要真实授权素材、授权范围记录、模型与版本、付费预算。模板故事本身不是授权样本证据。 |
| 独立评审 | 评测器支持两名不同评审者与分歧裁定，但模板 `reviewers` 为空 | **缺失**。需要两名真实评审身份、逐维评分、理由与分歧裁定记录。 |
| 留出集 | 脚本结构中有 `holdout` 故事「海边归还」 | **只有结构，无结果**。需要真实生成、首轮 attempt=1 证据、媒体摘要与评审结果。 |
| 120 秒样片 | 未找到 119–121 秒真实成片证据；历史 R1519/R1585 只记录 60.021 秒离线技术样例 | **缺失**。需要真实授权素材制作的 120 秒成片、FFprobe 时长、缺镜/黑帧、对白覆盖、音画偏差测量。 |
| 目标剪辑软件实机导入 | `orchestrator/engine.py::publish_edit_lists` 已发布 EDL/FCPXML/分轨清单；历史记录反复写明“真实剪辑软件导入待验收” | **缺失**。需要声明目标软件与版本、实际导入截图或日志、时间线完整性、字幕/分轨结果。 |
| 质量评测器 | `business_quality_baseline.py` 可生成 40 镜待执行表并校验媒体、双评、分歧、成本字段 | 可复用，但当前只证明评分规则；不证明生成质量、授权真实性或成片质量。 |
| 恢复探针 | `scripts/acceptance_recovery_probe.py` 存在，输出台账、供应商日志、强杀/重启证据；使用本地假供应商 | 可复用作离线恢复证据；不能替代真实供应商 429/断网/超时/账单证据。 |
| 实机导入流程 | `domain/edit_export.py`＋`engine.publish_edit_lists` 生成 EDL/FCPXML/分轨清单 | 导出侧实现存在；剪辑软件实机导入结果缺失。 |

## 边界与未满足项

1. 白模参考视频内容哈希未纳入本轮视频输入指纹；仅纳入 `upload_white_model` 开关。白模文件内容变化但开关不变时，本轮不会据此判视频过期。
2. 模型、供应商工作流、随机种子与 ComfyUI 工作流模板不纳入本指纹；本轮口径聚焦镜头内容、首帧与参考资产。
3. 资产文字设定只有已进入视频提示词或画面字段时才影响指纹；仅改资产清单文字不直接触发视频过期。
4. 过期状态只读现算，不写回版本记录；这是规格09已修正后的明确口径，不是漏做落盘标记。
5. 未执行真实付费服务、未读取账号凭据、未生成真实样片；`程序/验收证据/` 仍为空。

集成验证由 Control 使用随附解释器执行，命令、结果与真实环境边界见 [R4516 独立验收](tasks_round_4516_result.md)。
