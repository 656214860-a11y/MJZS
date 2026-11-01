# R435 结构治理轮（子场景：执行）：逐句配音发布边界

- **来源与条目**：执行 `tasks_round/tasks_round_418_result.md` J/K 的音频/字幕成果族；仅处理逐句 MP3 和可续跑时间轴，未处理设置、密钥、请求网络或后期剪辑。
- **改动**：新增 `tts_api.publish_line()`，先用既有原子二进制写入发布 MP3，再原子更新 `时间轴.json`；`run_lines()` 的成功路径只能委托这一入口。
- **失败语义**：时间轴索引保存异常时，旧索引保持原字节，已完整保存的单句音频保留，不会误删除用户成果。
- **测试**：`tests/test_tts.py` 覆盖索引保存失败的旧索引保留；`tests/architecture/test_tts_publication_boundary.py` 锁定成功路径必须经发布入口。本次改测试因契约变更，断言未动。
- **验证**：`python -m unittest tests.test_tts tests.test_subtitles tests.architecture.test_tts_publication_boundary` **69/69** 通过；`python smoke_test.py --architecture` **44/44** 通过（15.324 秒）；`python smoke_test.py` **8/8** 通过。
- **后续**：按 R418 路线，下一成果族为后期剪辑/交付；继续忽略未授权白模真实上传。
