# R512 结构治理轮：字幕 SKILL 成果发布边界

## 完成内容

- `skill_tools._subtitle_generate()` 不再直接创建目录或调用行尾写入器；只生成 SRT 文本并委派 `subtitle_export_service.publish_srt_text()`。
- 发布服务统一负责目标路径的行尾校验和原子写入，保留 SKILL 的 `subtitle_file` / `output` 指定路径兼容性。
- 已在 `architecture.md` 与 R182 优化清单登记该增量；P0 的“全阶段统一写入”总项仍未完成。

## 范围与验证

- 修改：`subtitle_export_service.py`、`skill_tools.py`、`tests/test_subtitle_export_service.py`、`architecture.md`、`tasks_round/tasks_round_182_optimization_checklist.md`。
- 定向：`D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_subtitle_export_service -q`，6/6 通过。
- 默认冒烟：`D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`，8/8 通过。
- 未修改用户项目数据、任务成果、模型配置或密钥。

## 后续

- 继续按 R182 P0 顺序，把其余 UI、Agent、模型回调的正式成果写入迁移至对应阶段服务；每项保持可独立回归。
