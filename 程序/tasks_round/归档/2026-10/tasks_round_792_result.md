# R792 结果｜结构治理轮（执行）

## 完成内容

- 迁移 `tts_api.py` 与 `cloud_video_service.py`：L2 的正式配置、音频和标记发布必须接受 L3 注入网关；缺少网关时明确拒绝，不再直连 `agent.core` 写入。
- `stage_execution_service` 提供 TTS 与云视频的唯一发布网关；桌面、云视频设置页与应用装配层只调用 L3 编排入口。用户数据格式、目标路径和授权语义保持不变。
- 第 3 项台账将 7 条记录保留并标记为 `migrated`：TTS 设置、完整音轨、逐句音轨及标记，云视频会话、工作区及工作室配置。pending `41 → 34`；第 4 项 `21 → 21`。
- 三条 `stage_execution_service.py` 既存裸 JSON 读取因前轮插入代码而变更行号，已仅重定位台账定位点（193/224/237 → 235/266/279），未新增或清除第 4 项债务。

## 验证

- `smoke_test.py`：8/8。
- `smoke_test.py --affected tts cloud_video`：9/9。最初以模块文件名作筛选未命中任何测试标签；已改用实际 `tts`／`cloud_video` 标签取得有效结果。
- `run_selftests.py -k "tts cloud_video unification_ratchet" --safe`：63 条／0 红。
- `smoke_test.py --architecture`：158/158（44.018 秒）；架构基线同步为 158。
- 按 §5：`792 - 791 = 1 < 3`，本轮不触发完整安全全量；`last_full_safe_all_round` 保持 791。

## 后续

按既定批次，下一轮迁移 `storyboard_storage.py`＋`video_lifecycle_service.py`。剩余量只作台账读数，不以点数机械折算轮数。

## Git

- 本轮未提交，commit hash：无。
