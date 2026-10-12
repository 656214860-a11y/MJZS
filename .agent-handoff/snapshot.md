# 当前快照

## 2026-10-12：O17 完成，继续 O18

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O16 已完成，**O17 已完成（R1341）**，下一项 O18。
- O17（剧本结构形式合格与内容完备分开）：`script_contract.structure_script` 标「本地规则提取（未调用模型）」＋「结构合法≠信息齐全」；角色卡加别名（只认原稿声明）与跨集 ID（`char-xxxxxxxx`，同名跨集稳定）；无对白标签／未知道具尺寸／回忆场景／同名特征矛盾保留出处或待确认；`review_structured_script` 只要求出处字段存在、不要求待确认填满。模板步骤／`stage_exec` detail／桌面说明／`skill_tools` 描述统一为「规则提取／规则校验（未调用模型）」。见 [R1341](../程序/tasks_round/tasks_round_1341_result.md)。
- 验证证据：O17 定向 `-k script_structure script_contract stage_templates` 71/71、`-k ui_edges` 全绿、`-k skills` 全绿、架构相关 35/35、`-k copy_rules` 14/14、默认冒烟 8/8，0 红；1341 − 1336 = 5 ≥ 5，收口补一次干净 master 全量。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；`1335`／`1337` 已被其他车道领走，本轮 1341；收口全量在干净 master 工作树 `run_selftests.py --all --safe`。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O18（P2，M/L）——来源账本从「仍在」升级为「仍是这个版本」（`tasks_round_1267_result.md` O18 条目）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1336；next 到 1341 再跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
