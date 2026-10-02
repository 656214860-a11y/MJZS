# R440 结构治理轮（子场景：执行）：手工提示词导入暂存收敛

- **来源与范围**：执行 R418 J2/K 的下一类视频提示词入口，只迁移手工“导入提示词”的候选草稿发布；Agent 自动结果导入、视频生成与白模真实上传不在本轮范围。
- **改动**：新增 `video_prompt_publication.stage_import()`；它校验镜头与文本、原子写入候选 JSON，并在替换旧候选时保留历史副本。`app.App.import_prompt()` 只选择/解析文件、更新编辑框并委托该服务。
- **语义与失败恢复**：导入仍只暂存，不更新 `episode.json`，用户必须点击“保存提示词”才提交分镜。保存失败会恢复旧候选 JSON，并删除本轮新增历史副本与空目录。
- **测试**：扩展行为回归，覆盖暂存不改分镜及失败恢复；扩展静态门禁，禁止 `import_prompt()` 在委托后自行管理提示词产物名或写入。
- **验证**：`python -m unittest tests.test_video_prompt_publication tests.architecture.test_video_prompt_publication_boundary` **7/7**；`python smoke_test.py --architecture` **51/51**；`python smoke_test.py` **8/8**。全量安全基线仍为 R439 的 **3116/3116**；本轮后续自动工作继续前会按需要重新执行全量回归。
- **未触及**：主界面“齿轮 → 设置”入口保持不变；未改该 UI 路径，未调用白模真实上传。
