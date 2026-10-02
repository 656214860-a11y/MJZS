# R433 结构治理轮（子场景：执行）：首帧关联发布边界

- **来源与条目**：执行 `tasks_round/tasks_round_418_result.md` 的 J/K 中“按阶段成果族收敛写入链”的下一条：首帧用户可见媒体与分镜关联；未处理批次请求记录、视频、音频、剪辑/交付或未授权白模上传。
- **范围**：只改 `keyframe_import.py`、首帧定向测试、一个架构门禁、`AGENTS.md` 基线和 `project_status.md`；所有测试仅使用临时目录。
- **改动**：新增 `publish_frame_reference()`，在已用唯一文件名安全发布首帧媒体后，重读并校验镜头签名、备份分镜 JSON，再用既有原子 `agent.core.save()` 更新 `frame` 关联。`register()` 不再直接更新关联，只负责输入校验、独占媒体发布和委托。
- **失败语义**：关联保存失败时，原分镜 JSON 由原子写入保持不变；已独占发布的新图按原有“生成图已保留”语义保留，便于用户恢复，绝不删除旧首帧或覆盖既有素材。
- **测试**：`tests/test_keyframe.py` 增加保存失败回归，验证旧 JSON 原字节未变且新图存在；`tests/architecture/test_keyframe_reference_publication_boundary.py` 锁定 `register()` 必须先发布媒体再委托关联发布，且不得直接 `save()`。
- **验证**：`python -m unittest tests.test_keyframe tests.architecture.test_keyframe_reference_publication_boundary` **31/31** 通过；`python smoke_test.py --architecture` **42/42** 通过（15.218 秒）；`python smoke_test.py` **8/8** 通过。
- **后续**：按 R418 整改路线，下一成果族为视频；继续排除内部任务清单、配置/缓存与未授权白模真实上传。
