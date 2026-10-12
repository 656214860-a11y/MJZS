# 当前快照

## 2026-10-12：O11 完成，继续 O12

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O10 已完成（O10 R1330，收口安全全量 4528/4528、tree 3281c7c7），**O11 已完成（R1333）**，下一项 O12。
- O11（人工确认只绑名称不绑内容）：`confirm_gates.content_digest` 给三条候选各带 sha1 摘要，`record(..., digest=)` 落摘要，`pending()` 变成「已确认且摘要还对得上」；摘要缺一边（旧记录／裸 key）按旧口径放行。写入路径三处都带摘要：资产详情页 `_pick`、连贯性页「采用推荐」`pick_gate`、`auto_decide_gates`。见 [R1333](../程序/tasks_round/tasks_round_1333_result.md)。
- 验证证据：O11 定向 101/101、接缝 172/172（ui_edges／stage_execution／stage_parallel）、架构相关 15/15、默认冒烟 8/8，0 红。O10 收口全量 [R1330](../程序/tasks_round/tasks_round_1330_result.md)（4528/4528、0 红，tree 3281c7c7）。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”（未跟踪 outputs/ 等），`content_tree()` 在脏树返回空，因此全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；在 `o07-fullsafe-master` 干净 worktree 领取。**每次在主树提交后，master ref 前移会让该 worktree 显示自己那几份文档为「已暂存改动」，领取前先 `git reset --hard HEAD` 即可**（那是同一 ref 的正常现象，不是别人的改动）。本轮 1333（1331／1332 被并行车道领走）。
- 下一步：O12（P1，M）——TTS 批次配置与缓存身份不完整（`tts_api.py:137/189/216` 逐句签名只绑台词／音色／速度，不含 provider／endpoint／模型身份；`307` 合成时重读设置；整轨签名也没覆盖全部接口身份）。验收“中途切配置不影响当前批次，新批次用新配置；只换模型／服务商就失效旧缓存；损坏音频不能续用”。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次且用 master 分支临时工作树取凭据；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1330，故 1335 起再跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
