# 当前快照

## 2026-10-12：O13 完成，继续 O14

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O12 已完成，**O13 已完成（R1336）**，下一项 O14。
- O13（剧本准备把「对话、工作稿、正式采用」显示为明确状态）：`writing_api` 新增 `preparation_reply_state`／`preparation_reply_message`（一次回复唯一状态：已采用／阶段稿待确认／原始响应已保存／因版本变化未采用，含落点文件与下一步）；`_preparation_step` 在格式不合格／截断／正文为空／模型失败／版本变化各分支打状态＋原因标签，`saved` 文案点明 responses/ 归档不等于正式采用，取消后迟到的错误也带这句；桌面 `received` 三处状态栏改用同一判据。收口安全全量第 1 次 4542/4542、385.8 秒、0 红（凭据 tree d934dd21）。见 [R1336](../程序/tasks_round/tasks_round_1336_result.md)。
- 验证证据：O13 定向 `-k writing` 139/139、关联 `-k idea_inline_brief writing_response_preservation` 46/46、桌面 `-k ui_edges` 115/115、架构相关 22/22、默认冒烟 8/8，0 红；`desktop.py` 增 1 行，TODO 注释快照 desktop.py 行号 2748→2749。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；`1335` 已被其他车道领走，本轮 1336。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O14（P2，M）——历史／上下文／输出文件采用不同维度，界面应解释清楚（`tasks_round_1267_result.md` O14 条目）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1330；1336 收口已补跑，第 1 次即绿 4542/4542、385.8 秒、tree d934dd21，last_full 刷到 1336）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
