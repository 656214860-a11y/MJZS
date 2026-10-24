# R1996 结果：总控包在线更新（功能轮）

## 做了什么
- 新增 `master_skill_update.py`（L4，无 Tk）：读 GitHub `manju-laoli-skill` main 最新提交；与上次已装提交不同才下载压缩包并逐文件比对（文本换行归一），按各阶段总控 SKILL 及其直接引用归类“每个阶段的变化”，新功能取自 README 更新日志中本机没有的条目。
- 用户确认后 `apply`：解压到旁路临时目录（防 zip-slip、限文件数/体积）、校验入口、旧包改名换入新包、旧包进回收站，记录 `data/总控包更新.json`，再对当前项目触发 `master_skill.sync`（指纹同步）。失败则旧包不动。
- 总控包目录带 `.git`（开发检出）时只提示、不覆盖。
- 新增 `desktop_master_update.py`（MasterUpdateMixin）：首帧后后台检查一次，有更新才弹确认窗；`desktop_automation_tick.py` 挂接；`master_skill.stage_skill_files` 公开。
- 同步登记：`_layers.py`（L4）、覆盖率基线、runbook、architecture。

## 三问
1. 本轮改了什么：见上；新增 3 个文件，改 7 个文件。
2. 怎么验证的：
   - `tests/test_master_skill_update.py` 8/8 通过（注入 fetch，不联网）。
   - 默认 `smoke_test.py` 8/8 通过。
   - `smoke_test.py --architecture` 406 项，剩 4 条红，均非本轮引入：Desktop 类行数 1303>1302（HEAD 同样）、round_number_continuous、skill_reference_injection、agents_md 性能历史文件（工作树环境）。
   - `run_selftests.py -k master_skill`：`test_master_skill.py` 1 条红（`script-forging` 缺失），原因是本工作树没有嵌套仓库 `skills/01 剧本准备SKILL/剧本锻造/`；主检出 master 上同一文件 18/18 通过。
   - 真实联网只读检测一次（缓存放临时目录）：本机 V7.4.20 → 远端 V7.4.26，新增 12、修改 50、删除 1，摘要正常生成；该检出带 `.git`，按设计仅提示。
3. 未运行：`--all --safe` 全量；真实覆盖更新的端到端（只在临时目录单测过）；Tk 确认弹窗的人工点击。
- 断言未动；未 push；未提交 `project_status.md`（非 master 分支）。

## 已知局限
- 没有手动“检查更新”按钮，用户选择暂不更新后下次启动才再提示。
- 摘要里新功能原文偏长，已截断到 220 字/条。
