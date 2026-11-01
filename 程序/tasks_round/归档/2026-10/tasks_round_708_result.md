# R708 结构治理轮（执行）结果：音频发布器由 L3 注入

来源：`架构模块接口统一.txt` 第一批第 3 项。范围限定为首个音频 L2 写服务；未修改用户项目数据。

## 完成内容

- `audio_import_service.import_audio()` 现要求调用方注入 `publish`，保留格式、非空和发布后尺寸校验；删除 L2 内的 `shutil.copy2()` 与临时复制发布分支。
- `stage_execution_service.import_stage_audio()` 作为 L3 编排入口，注入既有 `publish_stage_bytes()`；`desktop.import_audio()` 只调用该入口。
- 回归测试覆盖发布器注入、无效输入、UI 不直连 L2，以及 L3 注入语句的 AST 边界。既有发布校验与源文件保全断言未弱化。

## 验证

| 基线 | 结果 |
| --- | --- |
| 定向单元（audio import / L3 / 架构边界） | 11 条 / 0 红 |
| 受影响冒烟 | 9/9 |
| 默认冒烟 | 8/8 |
| 架构门禁 | 107/107 |
| 完整安全全量 | 3,415 条 / 0 红 / 753.3 秒 |

完整安全全量日志：`维护记录/r708_l3_audio_publisher_safe_all.log`。

## 架构结论

L2 不再自行选择音频成果发布路径；发布权和原子发布边界仍由 L3 持有。此为路线图第 3 项首批迁移，其他 L2 写服务留待后续独立轮次逐项迁移。

`[TASK_COMPLETE]`
