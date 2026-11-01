# R434 结构治理轮（子场景：执行）：视频成果发布边界

- **来源与条目**：执行 `tasks_round/tasks_round_418_result.md` J/K 的下一成果族：视频用户可见片段与其 QC/状态索引；未处理内部提交台账、音频、剪辑/交付或白模真实上传。
- **改动**：`Studio.publish_downloaded_video()` 统一验证视频已经在工作集内完整存在，再写入 QC 报告和 `state.json` 中的已下载索引。云端 `Studio.poll()` 与本地 `LocalStudio.poll()` 均委托此入口。
- **失败语义**：下载失败不会发布索引；QC 失败/异常时保留完整视频并写入已下载状态及 QC 错误，后续不会将其当作未下载而覆盖。
- **测试**：`tests/test_video.py` 覆盖视频、QC、索引的发布顺序；`tests/architecture/test_video_publication_boundary.py` 锁定云端与本地轮询必须委托统一入口。
- **验证**：`python -m unittest tests.test_video tests.architecture.test_video_publication_boundary` **37/37** 通过；`python smoke_test.py --architecture` **43/43** 通过（15.388 秒）；`python smoke_test.py` **8/8** 通过。
- **后续**：按 R418 路线，下一成果族为音频/字幕；继续排除内部请求状态、配置/缓存及未授权白模真实上传。
