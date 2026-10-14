# R1434 结果：剧本准备交付改为本机绝对路径并沿用已有文件

- 轮次类型：缺陷修复（小）。用户需求：模型输出直接写到项目设定／大纲／角色卡／剧本对应文件，用户手改后模型读取该文件重新生成。
- 范围：`idea_document_paths.delivery_document_path()`（新增）、`workflow_tasks._agent_delivery_contract()`、`tests/test_idea_download_import.py`、`ci_clean.cmd`（在干净工作树跑安全全量的本地 CI 入口）。

## 内容

- 交付清单由项目相对路径改为本机绝对路径：Claude Desktop 等桌面应用不以项目目录为工作目录，相对路径会落进其沙盒、只能以下载交付。
- 设定／大纲／角色卡／剧本：本模型该类已有文件就沿用最新一份（跨天、重试不再换到新的 创意_日期 批次），没有才用当日新路径。
- 任务书要求修改或重新生成前先读取该路径当前内容（含用户手改），完成后覆盖写回；无法访问本机文件时提示连接项目文件夹，仍只能下载时沿用同名，由 R1431 的下载收件箱收回。

## 测试

- Linux：`test_idea_download_import`（新增跨天沿用用例）8 项、`test_download_inbox` 5 项通过；对真实项目只读核对四类目标路径正确。
- 未运行：Windows 随附解释器全量（需在干净工作树经 `ci_clean.cmd` 补跑）。
