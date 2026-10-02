# 第 181 轮：剧本创作契约轮

## 结论

剧本准备阶段的运行提示词、工作流测试与新建的 `brief_creation.md` 简报入口已统一到当前阶段契约：本阶段只交付自然语言剧本，结构化剧本不得越级写入下一阶段。

## 改动

- 迁移 `tests/test_workflow.py` 两条过时断言：
  - 旧断言要求“禁止直接返回剧本”，与当前“自然语言剧本是本阶段唯一交付物”矛盾；改为验证自然语言剧本产物契约和后续阶段写入禁令。
  - 旧断言要求已废弃的“唯一识别规范原稿文件”文案；改为验证唯一允许的内部落盘位置 `script_raw.md`。
- 复验剧本、资产、阶段路径、阶段命令与工作流契约；未改变生产工作流语义。

## 验证

- `python -m unittest tests.test_asset_contract tests.test_script_contract tests.test_stage_path_service tests.test_stage_command_contract tests.test_workflow`：149 项通过。
- `python smoke_test.py --affected script_contract workflow stage_path_service`：9 项冒烟检查通过；定向门禁 119 项通过。

## 未纳入本轮

- 架构治理检查仍报告历史遗留的大范围分层依赖、根模块循环及路径文字直写；这些涉及多个模块迁移，不能用放宽契约测试掩盖。本轮未将其标记为已解决。
