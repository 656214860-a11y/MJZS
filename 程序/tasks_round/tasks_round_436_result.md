# R436 结构治理轮（子场景：执行）：后期剪辑成片发布边界

- **来源与条目**：执行 `tasks_round/tasks_round_418_result.md` J/K 的后期剪辑/交付成果族；仅处理 `MASTER.mp4`、其 QC 报告与剪辑清单，继续排除配置、请求状态、缓存和未授权白模真实上传。
- **改动**：`Studio._encode()` 先把拼接成片编码到同目录唯一临时 MP4，完成 FFmpeg 可读性检查与技术 QC 后，才以 `agent.core.replace()` 原子替换正式 `MASTER.mp4`；随后统一经 `Studio.publish_edit_bundle()` 写入 `qc.json` 与 `edit_manifest.json`。
- **失败语义**：编码或核验失败时，旧正式成片不会被半份输出覆盖，临时 MP4 会受控清理；成片发布前禁止登记 QC/清单。QC 不通过仍保留完整成片及报告，沿用既有可诊断语义。
- **测试**：新增 `tests/architecture/test_edit_publication_boundary.py`，锁定临时编码、原子替换和集中索引登记的边界；本次增测对应新发布契约，未削弱既有断言。
- **验证**：`python -m unittest tests.test_integration.PartialAssembleTests tests.architecture.test_edit_publication_boundary` **6/6** 通过；`python smoke_test.py --architecture` **46/46** 通过（15.287 秒）；`python smoke_test.py` **8/8** 通过。
- **后续**：R418 的阶段成果发布主链已覆盖至剪辑；如继续执行，应先按 J/K 盘点交付阶段是否存在尚未收口的用户可见成果，再决定是否新增变更。真实白模上传仍等待用户授权。
