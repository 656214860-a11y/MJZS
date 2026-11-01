# R2285 合并后修复轮结果

- 轮次类型：修复轮（R2284 合并的后续）。合并带入 master 的四条直连分流使 `desktop_idea_chat.py` 超过体量上限 1113；新建 `desktop_direct_dispatch.py`（L4）收口为单一分流点，该文件降到 1111 行并把上限同步为 1111。
- 测试改动只同步 mock 路径：`test_image_direct`、`test_video_prompt_direct_api`、`test_storyboard_direct_api` 的 patch 目标改为各 `desktop_*_direct` 模块里的 run 函数。断言未动。
- 新增生产模块，已重跑覆盖率基线（348 模块／53 有覆盖）并同步 runbook §11；层级登记表与 architecture.md 已登记。
- 环境说明：本工作树的 `skills/00全流程SKILL/AIGC创作全流程` 子模块未实体化，写作／灵感相关 200 余条红皆为 `SKILL 引用缺失`，非本轮引入。
