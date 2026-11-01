# R439 修复：旧版资产历史恢复兼容

- **来源与阻塞**：R438 后的全量安全自检发现 `tests/test_asset_restore.py` 两项失败：旧项目仅有 `assets/characters/历史版本/` 留存时，`restore_latest_recycled_child()` 因回收站目录不存在而提前报“没有可恢复的删除记录”。
- **修复**：保留回收站清单优先；仅在没有匹配回收记录时，读取当前资产目录下 `历史版本/` 中同编号、允许后缀、非链接的最新文件并恢复。目标已存在即拒绝，绝不覆盖；新删除路径仍只经 `recycle_paths()`。
- **范围**：仅修改 `storage_maintenance.py` 的旧数据恢复兼容分支；未改 UI、生产设置入口、白模上传或用户项目数据。
- **验证**：`python -m unittest tests.test_asset_restore tests.test_recycle_restore tests.test_video_prompt_publication` **9/9**；`python smoke_test.py --architecture` **50/50**；`python smoke_test.py` **8/8**；`python run_selftests.py --all --safe` **3116/3116**，801.7 秒，0 个失败文件。
- **后续**：继续 R418 J2 的下一项：审计并逐步迁移视频提示词“历史导入”与 Agent 结果导入的可见成果发布入口；白模真实上传仍等待用户授权。
