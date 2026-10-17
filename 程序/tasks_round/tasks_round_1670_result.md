# R1670 修复轮：按用户裁决落实阶段 10／11 的 ❓ 条目

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（用户对 R1663／R1664 结果文件 C 节逐条裁决为“修复”）。
2. **测试跑了吗？三个基线过了吗？** 定向（video／audio／subtitle／engine／stage_execution／service_return／agents_md／distribution_selfcheck／layers／keyframe／previs）672 条全绿；分支内默认冒烟 8/8；架构门禁全量与安全全量待五组合入后统一跑。
3. **project_status.md 的欠账少了吗？** 全量欠账 +1，合入后统一补跑。

## A 改动

- REQ-S10-21：视频下载、验收、采用版本后写出内容相同的 `videos.json` 与 `video_manifest.json`（`10视频生成/output/`，经 `write_dir` 与 `agent.core.save`）；写失败只记警告。
- REQ-S10-31：`video_task_state.shot_count_error` 实现“100 镜／项目”上限，已删除镜头不计数，`Studio.validate` 超限给明确报错。
- REQ-S11-24：标准库实现 ASS 导出，`export_srt` 成功后以同一文件名主干与同一校准轴再发布 `.ass`；ASS 写失败只记警告，不影响已发布的 SRT。
- REQ-S11-40：音频导入、TTS、字幕导出、对白脚本导出成功后刷新 `voice.json`、`subtitles.json`、`audio_manifest.json`（`11配音与字幕/output/`）。
- 测试：新增 `test_video_manifest_scope.py`、`test_audio_manifest_scope.py`；`test_audio_subtitle_scope` 的 S11-24／40 两条由“声明未实现”改为正向断言（规格变更，非弱化）；`test_video.py` 的 FakeStudio 补空 `publish_manifest`，`test_service_return_contract` 登记新公开名；`架构统一基数.json` 三个行号因插入代码顺延。
- 与 R1669 在 `architecture.md` 的阶段表同一段冲突，已手动合并（08／09 行取 R1669，10／11 行取本轮）。

## B 验证

- 定向 672 条 0 红。

## C 待用户拍板

- SKILL 文本（`skills/` 内）需补：`subtitle.exportAss` 与 SRT 同批产出、`videoManifest`／`audioManifest` 的真实落点；本轮未改 SKILL 文本。

## D 未做与局限

- 未跑架构门禁全量与安全全量，未做桌面界面手测。
