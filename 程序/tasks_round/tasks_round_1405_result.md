# R1405：剧本准备文件删除前提示定稿＋右键菜单改名

类型：修复轮（§3）。中央轮次：1405。执行者：Claude Code。

## 三个必答
- 起因：用户在剧本准备文件列表「批量删除」时删掉了已确认的项目设定（摄影侠，2026-10-12 01:51），之后点发送弹「项目设定文件已删除或修改，原确认失效」；删除前没有任何提示。右键三项命名（从本阶段重新创作／放弃未确认重写／作为确认输出文件）不易读懂。
- 测试：定向 `test_writing_restart`／`test_preparation_confirmation`／`test_writing_api`／`test_writing_restart_intent`／`test_writing_response_preservation` 全绿；`-k copy_rules ui_edges idea_chat` 全绿；架构 341/341；默认冒烟通过。
- 欠账：未命中 §5 → **不跑全量**。

## 改动
- `writing_api.py`：新增只读 `confirmed_preparation_files(project)`（采用版本与重写草稿中已确认文件 → 阶段名；记录缺失/损坏返回空）；三处重复的「前置阶段齐全且已确认」判断合并为 `_confirmed_prefix`，行为不变。
- `desktop.py`：单个/批量删除确认框在命中已定稿文件时追加警告并列出阶段与文件名；右键改名为「重写<阶段>」「放弃重写，恢复原稿」「设为<阶段>定稿」，弹窗与状态栏文案同步改为定稿/原稿口径。
- `tests/test_preparation_confirmation.py`：新增 2 条用例。`tests/test_writing_restart.py`：菜单名随契约同步，断言未动。

## 未做（建议）
- 无重写稿时隐藏「放弃重写，恢复原稿」。
- `restart_preparation(None)` 拆为独立的放弃函数；brief 指纹计算两处重复。

## 提交
- 本文件＋上述 4 个文件＋`project_status.md` 表头，一次提交（hash 见 git log）。用户本地未提交的 `idea_attachments.py`／`idea_chat.py`／`预设.json` 不在本次提交内。
