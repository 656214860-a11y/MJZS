# R438 结构治理轮（子场景：执行）：视频提示词发布入口收敛

- **来源与条目**：执行 `tasks_round/tasks_round_418_result.md` J2（阶段写入入口清单并逐类迁移）和 K（为迁移补行为失败回归与窄静态门禁）。本轮只处理手工保存与切镜自动保存；导入历史文件、Agent 结果导入、配置/缓存和未授权白模真实上传均未触及。
- **改动**：新增 `video_prompt_publication.publish()`，集中发布 `video_prompts/<镜头>.json`、同名文本、镜头目录的“当前提示词.txt”及 `episode.json`。`app.App.save_prompt()` / `flush_prompt()` 只负责界面输入和调用该服务。
- **失败语义**：服务先保留四个目标的原字节；任何一次发布失败，按反序恢复已有内容并受控清理本轮新文件，内存 `studio.episode` 只在全部成功后更新。
- **测试**：新增行为回归 `tests/test_video_prompt_publication.py`（全量发布、首项写入失败恢复）；新增 `tests/architecture/test_video_prompt_publication_boundary.py`，锁定两条 UI 保存路径只能委托服务且可见产物名只归服务所有。
- **验证**：`python -m unittest tests.test_video_prompt_publication tests.test_video_ui.FlushPromptTests` **7/7** 通过；`python smoke_test.py --architecture` **50/50** 通过；`python smoke_test.py` **8/8** 通过。组合后的跨层全量安全自检由 R439 完成，为 **3116/3116** 通过。
- **后续**：继续按 R418 J2 清单处理仍独立的提示词导入/Agent 结果导入路径，或先做其服务归属审计；白模真实上传继续等待用户授权。
